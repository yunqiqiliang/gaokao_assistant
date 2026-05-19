#!/usr/bin/env python3
"""
高校投档线数据采集脚本
========================

用途：
    从 gaokao.cn school/info.json 的 pro_type_min 字段提取
    各高校在各省份各年的最低投档线数据，写入 ClickZetta Lakehouse。

数据来源：
    https://static-data.gaokao.cn/www/2.0/school/{school_id}/info.json
    → pro_type_min 字段（含2023/2024/2025年数据）

前置条件：
    1. pip install clickzetta-connector
    2. /tmp/university_info.csv（学校列表，含学校抓取编码列）
    3. ClickZetta 连接参数（环境变量）

运行方式：
    python3 fact_school_province_score_scraper.py

耗时：约 5-10 分钟（2784所学校，16线程）

注意事项：
    - pro_type_min 数据结构：{province_id: [{year: 2025, type: {type_code: score}}, ...]}
    - type_code 含义：1=理科, 2=文科, 3=综合改革, 2073=物理类, 2074=历史类
    - 部分省份部分年份数据缺失（正常现象）
"""
import urllib.request, json, csv, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
import clickzetta

WORKERS = 16
BASE = "https://static-data.gaokao.cn/www/2.0"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.gaokao.cn/"}

PROVINCE_NAMES = {
    '11': '北京', '12': '天津', '13': '河北', '14': '山西', '15': '内蒙古',
    '21': '辽宁', '22': '吉林', '23': '黑龙江',
    '31': '上海', '32': '江苏', '33': '浙江', '34': '安徽', '35': '福建',
    '36': '江西', '37': '山东',
    '41': '河南', '42': '湖北', '43': '湖南', '44': '广东', '45': '广西', '46': '海南',
    '50': '重庆', '51': '四川', '52': '贵州', '53': '云南', '54': '西藏',
    '61': '陕西', '62': '甘肃', '63': '青海', '64': '宁夏', '65': '新疆',
}

TYPE_NAMES = {
    '1': '理科', '2': '文科', '3': '综合改革',
    '2073': '物理类', '2074': '历史类',
}


def make_conn():
    return clickzetta.connect(
        service=os.environ["CZ_SERVICE"],
        instance=os.environ["CZ_INSTANCE"],
        workspace=os.environ["CZ_WORKSPACE"],
        username=os.environ["CZ_USERNAME"],
        password=os.environ["CZ_PASSWORD"],
        vcluster=os.environ.get("CZ_VCLUSTER", "default"),
        schema="gaokao_assistant",
    )


def fetch_province_scores(school_id):
    """从 info.json 提取 pro_type_min 数据"""
    url = f"{BASE}/school/{school_id}/info.json"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("code") != "0000":
            return []
        d = data["data"]
        pro_type_min = d.get("pro_type_min", {})
        if not pro_type_min:
            return []

        rows = []
        for province_id, year_list in pro_type_min.items():
            if not isinstance(year_list, list):
                continue
            for year_entry in year_list:
                year = year_entry.get("year")
                type_dict = year_entry.get("type", {})
                if not isinstance(type_dict, dict):
                    continue
                for type_code, score_str in type_dict.items():
                    try:
                        score = int(score_str)
                    except (ValueError, TypeError):
                        continue
                    rows.append((
                        int(school_id),
                        str(province_id),
                        int(year),
                        str(type_code),
                        score,
                        int(year),  # data_year = year
                    ))
        return rows
    except Exception as e:
        import traceback
        print(f'  ERROR school_id={school_id}: {e}')
        traceback.print_exc()
        return []


def init_table(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.fact_school_province_score")
    cur.execute("""
        CREATE TABLE gaokao_assistant.fact_school_province_score (
            school_id       INT     COMMENT '高校ID，关联 dim_school.school_id',
            province_id     STRING  COMMENT '生源省份代码（11=北京, 44=广东等）',
            year            INT     COMMENT '招生年份',
            type_code       STRING  COMMENT '招生类型编码（1=理科, 2=文科, 3=综合改革, 2073=物理类, 2074=历史类）',
            min_score       INT     COMMENT '最低投档分数',
            data_year       INT     COMMENT '数据年份（与year一致）'
        ) COMMENT '高校在各省份各年的最低投档线。数据来自gaokao.cn school/info.json的pro_type_min字段。含2023-2025年数据。type_code映射：1理科/2文科/3综合改革/2073物理类/2074历史类'
    """)
    conn.commit()
    print("fact_school_province_score 表已创建")


def main():
    t_start = time.time()

    # 读取学校列表
    schools = []
    with open('/tmp/university_info.csv') as f:
        for row in csv.DictReader(f):
            try:
                sid = row['学校抓取编码'].strip()
                if sid:
                    schools.append(sid)
            except:
                pass
    print(f"待采集: {len(schools)} 所学校的投档线数据")

    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()

    all_rows = []
    errors = 0
    total_scores = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fetch_province_scores, sid): sid for sid in schools}
        for i, future in enumerate(as_completed(futures), 1):
            rows = future.result()
            if rows:
                all_rows.extend(rows)
                total_scores += len(rows)
            else:
                errors += 1
            if i % 100 == 0:
                print(f"  进度 {i}/{len(schools)}, 已采集 {total_scores:,} 条投档线记录")

    # 批量写入
    def esc(v):
        if v is None:
            return 'NULL'
        if isinstance(v, int):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    batch_size = 1000
    for i in range(0, len(all_rows), batch_size):
        batch = all_rows[i:i+batch_size]
        vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in batch)
        cur.execute(f"INSERT INTO gaokao_assistant.fact_school_province_score VALUES {vals}")

    conn.commit()
    conn.close()

    elapsed = time.time() - t_start
    print(f"\n完成！投档线记录: {total_scores:,} 条，错误: {errors} 所学校，耗时 {elapsed/60:.1f} 分钟")

    # 打印数据统计
    print("\n数据覆盖：")
    conn = make_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT school_id) FROM gaokao_assistant.fact_school_province_score")
    school_cnt = cur.fetchone()[0]
    cur.execute("SELECT year, COUNT(*) FROM gaokao_assistant.fact_school_province_score GROUP BY year ORDER BY year")
    for year, cnt in cur.fetchall():
        print(f"  {year}年: {cnt:,} 条")
    cur.execute("SELECT type_code, COUNT(*) FROM gaokao_assistant.fact_school_province_score GROUP BY type_code ORDER BY type_code")
    for tc, cnt in cur.fetchall():
        name = TYPE_NAMES.get(str(tc), str(tc))
        print(f"  类型 {tc} ({name}): {cnt:,} 条")
    conn.close()

    # 更新表注释
    update_table_comment(total_scores)


def update_table_comment(total_rows):
    conn = make_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(DISTINCT school_id), MIN(year), MAX(year) FROM gaokao_assistant.fact_school_province_score")
        school_cnt, yr_min, yr_max = cur.fetchone()
    except:
        school_cnt, yr_min, yr_max = 0, 2023, 2025

    comment = (
        f"高校在各省份各年的最低投档线。当前 {total_rows:,} 条，覆盖 {school_cnt} 所高校、{yr_min}-{yr_max}年。"
        f"数据来自gaokao.cn school/info.json的pro_type_min字段。"
        f"type_code映射：1=理科, 2=文科, 3=综合改革, 2073=物理类, 2074=历史类。"
        f"部分省份部分年份数据缺失属正常现象。"
    )
    safe = comment.replace("'", "''")
    cur.execute(f"ALTER TABLE gaokao_assistant.fact_school_province_score SET COMMENT '{safe}'")
    conn.commit()
    conn.close()
    print("表注释已更新")


if __name__ == "__main__":
    main()
