#!/usr/bin/env python3
"""
高考数据补全与去重脚本
========================================

用途：
    在全量采集（scraper.py）完成后，用于：
    1. 检测并补全遗漏的数据组合（网络超时等原因导致的缺失）
    2. 对数据库中的重复记录进行去重

工作流程（5步）：
    步骤1：构建理论组合集
           根据学校列表 × 31省份 × 7年，计算出应有的全部组合
    步骤2：查表实际组合，补写断点
           查询数据库中实际存在的组合，修复断点文件中的遗漏
           （解决 commit 成功但断点未写入的情况）
    步骤3：计算待补采列表
           理论集 - 断点集 = 需要重新采集的组合
    步骤4：并行补采
           对缺失组合重新发起 API 请求并写入数据库
    步骤5：去重
           使用 ROW_NUMBER() 窗口函数删除重复记录

前置条件：
    1. 安装依赖：pip install clickzetta-connector
    2. 准备学校列表文件：/tmp/university_info.csv（同 scraper.py）
    3. 已运行过 scraper.py，数据库中有部分数据

运行方式：
    python repair.py

输出文件：
    - /tmp/gaokao_repair.log：运行日志
    - /tmp/gaokao_still_missing.txt：补采后仍然失败的组合（如有）

注意事项：
    - 去重操作会创建临时表并替换原表，耗时较长，请勿中途中断
    - 脚本中包含数据库连接密码，请勿将此文件提交到公开仓库
    - 建议将连接参数改为从环境变量读取（见 make_conn 函数注释）
========================================
"""
import urllib.request, json, csv, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import clickzetta

LOG = '/tmp/gaokao_repair.log'
DONE_FILE = '/tmp/gaokao_done_keys.txt'
WORKERS = 16
COMMIT_ROWS = 5000

PROVINCES = {
    '11': '北京', '12': '天津', '13': '河北', '14': '山西', '15': '内蒙古',
    '21': '辽宁', '22': '吉林', '23': '黑龙江',
    '31': '上海', '32': '江苏', '33': '浙江', '34': '安徽', '35': '福建',
    '36': '江西', '37': '山东',
    '41': '河南', '42': '湖北', '43': '湖南', '44': '广东', '45': '广西', '46': '海南',
    '50': '重庆', '51': '四川', '52': '贵州', '53': '云南', '54': '西藏',
    '61': '陕西', '62': '甘肃', '63': '青海', '64': '宁夏', '65': '新疆',
}
YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

INSERT_SQL = (
    "INSERT INTO gaokao_assistant.fact_admission_history "
    "(school_id,province_id,year,special_id,sp_name,spname,info,remark,"
    "batch,local_batch_name,zslx_name,type,level1_name,level2_name,level3_name,"
    "min_score,max_score,average_score,min_rank,min_section,diff,lq_num,"
    "sp_info,sp_type,special_group,first_km,is_score_range,"
    "min_range,min_rank_range,sg_name,sg_info,sg_xuanke) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def make_conn():
    # 建议将敏感参数改为从环境变量读取，例如：
    # import os
    # username = os.environ['CZ_USERNAME']
    # password = os.environ['CZ_PASSWORD']
    return clickzetta.connect(
        service='https://cn-shanghai-alicloud.api.clickzetta.com',
        instance='f8866243', workspace='quick_start',
        username='qiliang', password='Ql123456!',
        vcluster='default', schema='gaokao_assistant'
    )

def fetch_deduped(school_id, province_id, year):
    url = f"https://static-data.gaokao.cn/www/2.0/schoolspecialscore/{school_id}/{year}/{province_id}.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get('code') != '0000':
            return []
        raw = []
        for val in data.get('data', {}).values():
            raw.extend(val.get('item', []))
        seen = set()
        deduped = []
        for item in raw:
            k = (item.get('special_id'), item.get('spname'), item.get('min'))
            if k not in seen:
                seen.add(k)
                deduped.append(item)
        return deduped
    except:
        return None

def to_int(v):
    try: return int(v) if str(v) not in ('', '-', 'nan', 'None') else 0
    except: return 0

def s(v):
    """空字符串转 None，写入 Lakehouse 时为 NULL 而非空字符串。"""
    val = str(v) if v is not None else None
    return val if val else None

def item_to_row(item, school_id, province_id, year):
    return (
        to_int(school_id), s(province_id), int(year),
        s(item.get('special_id')), s(item.get('sp_name')),
        s(item.get('spname')), s(item.get('info')),
        s(item.get('remark')), s(item.get('batch')),
        s(item.get('local_batch_name')), s(item.get('zslx_name')),
        s(item.get('type')), s(item.get('level1_name')),
        s(item.get('level2_name')), s(item.get('level3_name')),
        to_int(item.get('min', 0)), to_int(item.get('max', 0)),
        to_int(item.get('average', 0)), to_int(item.get('min_section', 0)),
        s(item.get('min_section')), to_int(item.get('diff', 0)),
        s(item.get('lq_num')), s(item.get('sp_info')),
        s(item.get('sp_type')), s(item.get('special_group')),
        s(item.get('first_km')), s(item.get('is_score_range')),
        s(item.get('min_range')), s(item.get('min_rank_range')),
        s(item.get('sg_name')), s(item.get('sg_info')),
        s(item.get('sg_xuanke')),
    )

# ── 步骤1：构建理论组合集 ──────────────────────────────
log("=== 步骤1：构建理论组合集 ===")
schools = []
with open('/tmp/university_info.csv', 'r') as f:
    for row in csv.DictReader(f):
        try:
            rank = int(row['全国热度排名'])
            sid = row['学校抓取编码'].strip()
            if sid and rank <= 500:
                schools.append((rank, sid, row['学校'].strip()))
        except:
            pass
schools.sort()
school_map = {sid: name for _, sid, name in schools}

theory_set = set()
for rank, sid, name in schools:
    for year in YEARS:
        for pid in PROVINCES:
            theory_set.add(f"{sid}|{pid}|{year}")
log(f"理论组合总数: {len(theory_set):,}  ({len(schools)}所 x {len(PROVINCES)}省 x {len(YEARS)}年)")

# ── 步骤2：查表实际组合，补写断点 ─────────────────────
log("=== 步骤2：查表实际组合，补写断点 ===")
conn = make_conn()
cur = conn.cursor()

cur.execute(
    "SELECT CAST(school_id AS STRING), province_id, CAST(year AS STRING) "
    "FROM gaokao_assistant.fact_admission_history "
    "GROUP BY school_id, province_id, year"
)
table_combos = set(f"{r[0]}|{r[1]}|{r[2]}" for r in cur.fetchall())
log(f"表中实际存在的组合数: {len(table_combos):,}")

done_keys = set()
if os.path.exists(DONE_FILE):
    with open(DONE_FILE) as f:
        done_keys = set(l.strip() for l in f if l.strip())
log(f"断点文件组合数: {len(done_keys):,}")

missing_in_done = table_combos - done_keys
if missing_in_done:
    log(f"补写断点: {len(missing_in_done):,} 个（表里有数据但断点未记录）")
    with open(DONE_FILE, 'a') as f:
        for k in missing_in_done:
            f.write(k + '\n')
    done_keys |= missing_in_done
else:
    log("断点文件完整，无需补写")

# ── 步骤3：计算待补采列表 ─────────────────────────────
log("=== 步骤3：计算待补采列表 ===")
missing_keys = theory_set - done_keys
log(f"待补采组合数: {len(missing_keys):,}")

if missing_keys:
    missing_by_school = Counter(k.split('|')[0] for k in missing_keys)
    log(f"涉及 {len(missing_by_school)} 所学校有缺失，缺失最多的前5所：")
    for sid, cnt in missing_by_school.most_common(5):
        log(f"  {school_map.get(sid, sid)}(ID={sid}): 缺失 {cnt} 个组合")

    # ── 步骤4：并行补采 ───────────────────────────────
    log(f"=== 步骤4：并行补采（{WORKERS}线程）===")
    tasks = [(k.split('|')[0], k.split('|')[1], int(k.split('|')[2]), k) for k in missing_keys]

    total_inserted = 0
    errors = 0
    still_missing = []
    pending_rows = []
    pending_keys = []
    processed = 0
    t_start = time.time()

    def fetch_task(task):
        sid, pid, year, key = task
        return key, sid, pid, year, fetch_deduped(sid, pid, year)

    def do_commit():
        global conn, cur, total_inserted, errors
        if not pending_keys:
            return
        try:
            if pending_rows:
                cur.executemany(INSERT_SQL, pending_rows)
            conn.commit()
            total_inserted += len(pending_rows)
            with open(DONE_FILE, 'a') as f:
                for k in pending_keys:
                    f.write(k + '\n')
                    done_keys.add(k)
        except Exception as e:
            errors += 1
            log(f"  COMMIT 失败: {e}，重连继续")
            try: conn.close()
            except: pass
            try:
                conn = make_conn()
                cur = conn.cursor()
            except Exception as e2:
                log(f"  重连失败: {e2}")
        pending_rows.clear()
        pending_keys.clear()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fetch_task, t): t for t in tasks}
        for future in as_completed(futures):
            key, sid, pid, year, records = future.result()
            processed += 1
            if records is None:
                errors += 1
                still_missing.append(key)
                continue
            if records:
                for item in records:
                    pending_rows.append(item_to_row(item, sid, pid, year))
            pending_keys.append(key)
            if len(pending_rows) >= COMMIT_ROWS:
                do_commit()
                elapsed = time.time() - t_start
                rate = total_inserted / elapsed * 60 if elapsed > 0 else 0
                log(f"补采进度 {processed}/{len(tasks)} | 新增 {total_inserted:,} | {rate:.0f} 行/分 | 失败 {errors}")

    do_commit()
    elapsed = time.time() - t_start
    log(f"补采完成！新增 {total_inserted:,} 行，失败 {errors} 个，耗时 {elapsed/60:.1f} 分钟")

    if still_missing:
        with open('/tmp/gaokao_still_missing.txt', 'w') as f:
            for k in still_missing:
                f.write(k + '\n')
        log(f"仍然失败的组合已记录: /tmp/gaokao_still_missing.txt（共 {len(still_missing)} 个）")
else:
    log("所有组合已完整，无需补采")

# ── 步骤5：去重 ───────────────────────────────────────
log("=== 步骤5：去重 ===")
cur.execute("SELECT COUNT(1) FROM gaokao_assistant.fact_admission_history")
total_before = cur.fetchone()[0]
log(f"去重前总行数: {total_before:,}")

cur.execute(
    "SELECT COUNT(1) FROM ("
    "SELECT school_id,province_id,year,special_id,spname,min_score "
    "FROM gaokao_assistant.fact_admission_history "
    "GROUP BY school_id,province_id,year,special_id,spname,min_score)"
)
unique_count = cur.fetchone()[0]
dup_count = total_before - unique_count
log(f"重复行数: {dup_count:,} ({dup_count/total_before*100:.2f}%)")

if dup_count > 0:
    log("开始去重：创建去重表 -> 替换原表")
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.fact_admission_history_dedup")
    conn.commit()
    cur.execute(
        "CREATE TABLE gaokao_assistant.fact_admission_history_dedup AS "
        "SELECT school_id,province_id,year,special_id,sp_name,spname,info,remark,"
        "batch,local_batch_name,zslx_name,type,level1_name,level2_name,level3_name,"
        "min_score,max_score,average_score,min_rank,min_section,diff,lq_num,"
        "sp_info,sp_type,special_group,first_km,is_score_range,"
        "min_range,min_rank_range,sg_name,sg_info,sg_xuanke "
        "FROM (SELECT *,"
        "ROW_NUMBER() OVER ("
        "PARTITION BY school_id,province_id,year,special_id,spname,min_score "
        "ORDER BY school_id) AS rn "
        "FROM gaokao_assistant.fact_admission_history) WHERE rn = 1"
    )
    conn.commit()
    cur.execute("SELECT COUNT(1) FROM gaokao_assistant.fact_admission_history_dedup")
    dedup_count = cur.fetchone()[0]
    cur.execute("DROP TABLE gaokao_assistant.fact_admission_history")
    cur.execute("ALTER TABLE gaokao_assistant.fact_admission_history_dedup RENAME TO fact_admission_history")
    conn.commit()
    log(f"去重完成！{total_before:,} -> {dedup_count:,}，删除 {total_before - dedup_count:,} 条重复行")
else:
    log("无重复数据，跳过去重")

conn.close()
log("=== 补全流程全部完成 ===")
