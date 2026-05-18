#!/usr/bin/env python3
"""
高考全量数据采集脚本 - v7
========================================

用途：
    采集全国热度前 500 所高校在 2018-2024 年间、面向全国 31 省份的
    专业录取历史数据，写入 ClickZetta Lakehouse。

数据来源：
    gaokao.cn 静态 API
    URL 格式：https://static-data.gaokao.cn/www/2.0/schoolspecialscore/{school_id}/{year}/{province_id}.json

前置条件：
    1. 安装依赖：pip install clickzetta-connector
    2. 准备学校列表文件：/tmp/university_info.csv
       - 必须包含列：全国热度排名、学校抓取编码、学校
       - 只采集"全国热度排名 <= 500"的学校
    3. 配置 ClickZetta 连接参数（见 make_conn 函数）

运行方式：
    python scraper.py

断点续传：
    - 已完成的采集任务记录在 /tmp/gaokao_done_keys.txt
    - 中断后重新运行会自动跳过已完成的任务
    - 如需全量重采，删除该文件后重新运行

日志：
    实时日志输出到终端，同时写入 /tmp/gaokao_scraper.log

性能：
    - 16 线程并行采集
    - 每积累 5000 行提交一次，减少数据库压力
    - commit 失败后自动重连，不影响整体进度

注意事项：
    - 脚本中包含数据库连接密码，请勿将此文件提交到公开仓库
    - 建议将连接参数改为从环境变量读取（见 make_conn 函数注释）
========================================
"""
import urllib.request, json, csv, time, os, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import clickzetta

LOG = '/tmp/gaokao_scraper.log'
DONE_FILE = '/tmp/gaokao_done_keys.txt'
WORKERS = 16
COMMIT_ROWS = 5000  # 每积累5000行 commit 一次

PROVINCES = {
    '11': '北京', '12': '天津', '13': '河北', '14': '山西', '15': '内蒙古',
    '21': '辽宁', '22': '吉林', '23': '黑龙江',
    '31': '上海', '32': '江苏', '33': '浙江', '34': '安徽', '35': '福建',
    '36': '江西', '37': '山东',
    '41': '河南', '42': '湖北', '43': '湖南', '44': '广东', '45': '广西', '46': '海南',
    '50': '重庆', '51': '四川', '52': '贵州', '53': '云南', '54': '西藏',
    '61': '陕西', '62': '甘肃', '63': '青海', '64': '宁夏', '65': '新疆',
}
DEFAULT_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

INSERT_SQL = """INSERT INTO gaokao_assistant.fact_admission_history
(school_id,province_id,year,special_id,sp_name,spname,info,remark,
 batch,local_batch_name,zslx_name,type,level1_name,level2_name,level3_name,
 min_score,max_score,average_score,min_rank,min_section,diff,lq_num,
 sp_info,sp_type,special_group,first_km,is_score_range,
 min_range,min_rank_range,sg_name,sg_info,sg_xuanke)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def load_done():
    if not os.path.exists(DONE_FILE):
        return set()
    with open(DONE_FILE) as f:
        return set(l.strip() for l in f if l.strip())

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

def make_conn():
    return clickzetta.connect(
        service=os.environ['CZ_SERVICE'],
        instance=os.environ['CZ_INSTANCE'],
        workspace=os.environ['CZ_WORKSPACE'],
        username=os.environ['CZ_USERNAME'],
        password=os.environ['CZ_PASSWORD'],
        vcluster='default', schema='gaokao_assistant'
    )

def parse_args():
    parser = argparse.ArgumentParser(
        description='高考录取历史数据采集脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例：
  # 采集全部年份（默认 2018-2024）
  python3 scraper.py

  # 只采集 2025 年新数据
  python3 scraper.py --years 2025

  # 采集多个年份
  python3 scraper.py --years 2024 2025

  # 从头全量重采（忽略断点）
  python3 scraper.py --reset
'''
    )
    parser.add_argument(
        '--years', type=int, nargs='+', default=None,
        metavar='YEAR',
        help='指定采集年份，可传多个，如 --years 2025 或 --years 2024 2025。默认采集全部年份（2018-2024）'
    )
    parser.add_argument(
        '--reset', action='store_true',
        help='忽略断点文件，从头全量重采（慎用，会重复采集已有数据）'
    )
    return parser.parse_args()

args = parse_args()
YEARS = args.years if args.years else DEFAULT_YEARS

schools = []
with open('/tmp/university_info.csv', 'r') as f:
    for row in csv.DictReader(f):
        try:
            rank = int(row['全国热度排名'])
            sid = row['学校抓取编码'].strip()
            if sid:  # 全量2784所
                schools.append((rank, sid, row['学校'].strip()))
        except: pass
schools.sort()

done_keys = set() if args.reset else load_done()
log(f"学校: {len(schools)} 所，年份: {YEARS}，省份: 31")
log(f"断点: 已完成 {len(done_keys):,} 个组合，继续采集")

tasks = []
for rank, sid, name in schools:
    for year in YEARS:
        for pid in PROVINCES:
            key = f"{sid}|{pid}|{year}"
            if key not in done_keys:
                tasks.append((rank, sid, name, pid, year, key))

log(f"待处理任务: {len(tasks):,} 个，启动 {WORKERS} 线程")

conn = make_conn()
cur = conn.cursor()
log("SDK 连接成功")

total_inserted = 0
errors = 0
pending_rows = []
pending_keys = []
processed = 0
t_start = time.time()

def fetch_task(task):
    rank, sid, name, pid, year, key = task
    records = fetch_deduped(sid, pid, year)
    return key, sid, pid, year, records

def do_commit():
    global conn, cur, total_inserted, errors, pending_rows, pending_keys
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
        log(f"  COMMIT 失败({len(pending_rows)}行): {e} — 重连继续")
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
            continue

        if records:
            for item in records:
                pending_rows.append(item_to_row(item, sid, pid, year))
        pending_keys.append(key)

        if len(pending_rows) >= COMMIT_ROWS:
            do_commit()
            elapsed = time.time() - t_start
            rate = total_inserted / elapsed * 60 if elapsed > 0 else 0
            log(f"进度 {processed}/{len(tasks)} | 入库 {total_inserted:,} | {rate:.0f} 行/分 | 错误 {errors}")

do_commit()

try: conn.close()
except: pass

elapsed = time.time() - t_start
log(f"完成！新增入库 {total_inserted:,}，错误 {errors}，耗时 {elapsed/60:.1f} 分钟")
