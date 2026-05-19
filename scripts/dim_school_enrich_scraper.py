#!/usr/bin/env python3
"""
高校信息增强采集脚本
====================

用途：
    从 gaokao.cn school/info.json 采集当前 dim_school 表中缺失的高价值字段，
    写入新增的维度表和扩展现有表。

新增数据：
    1. dim_dual_class          — 双一流学科列表（从 dualclass 字段）
    2. dim_school_enriched     — 高校增强信息（保研率、联系方式、校区等）

数据来源：
    https://static-data.gaokao.cn/www/2.0/school/{school_id}/info.json

前置条件：
    1. pip install clickzetta-connector
    2. /tmp/university_info.csv
    3. ClickZetta 连接参数（环境变量）

运行方式：
    python3 dim_school_enrich_scraper.py

耗时：约 5-10 分钟（2784所学校，16线程）
"""
import urllib.request, json, csv, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
import clickzetta

WORKERS = 16
BASE = "https://static-data.gaokao.cn/www/2.0"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.gaokao.cn/"}


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


def fetch_school_enrich(school_id):
    """从 info.json 提取增强字段"""
    url = f"{BASE}/school/{school_id}/info.json"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("code") != "0000":
            return [], [], []
        d = data["data"]

        # 1. 双一流学科列表
        dualclass_rows = []
        for dc in (d.get("dualclass") or []):
            dualclass_rows.append((
                int(school_id),
                dc.get("class") or None,
            ))

        # 2. 校区/分校区信息
        fenxiao_rows = []
        for fx in (d.get("fenxiao") or []):
            fx_name = fx.get("fx_name") or ""
            for yx in (fx.get("yuanxi") or []):
                fenxiao_rows.append((
                    int(school_id),
                    fx_name,
                    yx.get("id") or None,
                    yx.get("name") or None,
                ))

        # 3. 学校增强信息（单行）
        enriched_row = (
            int(school_id),
            float(d.get("recommend_master_rate") or 0),
            d.get("phone") or None,
            d.get("email") or None,
            int(d.get("num_lab") or 0),
            d.get("num_library") or None,
            d.get("content") or None,
            # label_list 转为 JSON 字符串存储
            json.dumps(d.get("label_list") or [], ensure_ascii=False) if d.get("label_list") else None,
            # xueke_rank 汇总转为 JSON
            json.dumps(d.get("xueke_rank") or {}, ensure_ascii=False) if d.get("xueke_rank") else None,
        )

        return dualclass_rows, fenxiao_rows, enriched_row
    except Exception as e:
        import traceback
        print(f'  ERROR school_id={school_id}: {e}')
        traceback.print_exc()
        return [], [], []


def init_tables(conn):
    cur = conn.cursor()

    # 双一流学科表
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_dual_class")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_dual_class (
            school_id           INT     COMMENT '高校ID，关联 dim_school.school_id',
            discipline_name     STRING  COMMENT '双一流建设学科名称（如计算机科学、数学、物理学等）'
        ) COMMENT '高校双一流建设学科列表。数据来自gaokao.cn school/info.json的dualclass字段。每所学校可能有多个双一流学科'
    """)

    # 校区表
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_campus")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_campus (
            school_id       INT     COMMENT '高校ID',
            campus_name     STRING  COMMENT '校区名称（如校本部、分校区）',
            college_id      STRING  COMMENT '院系ID',
            college_name    STRING  COMMENT '院系名称'
        ) COMMENT '高校校区和院系信息。数据来自gaokao.cn school/info.json的fenxiao字段'
    """)

    # 学校增强信息表
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_school_enriched")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_school_enriched (
            school_id               INT     COMMENT '高校ID，关联 dim_school.school_id',
            recommend_master_rate   DOUBLE  COMMENT '保研率（百分比，如70.00表示70%）',
            phone                   STRING  COMMENT '招生联系电话',
            email                   STRING  COMMENT '招生联系邮箱',
            num_lab                 INT     COMMENT '实验室数量',
            num_library             STRING  COMMENT '图书馆藏书量',
            content                 STRING  COMMENT '学校简介',
            label_list              STRING  COMMENT '学校标签JSON数组（如985/211/强基/C9/机械五虎等）',
            xueke_rank_summary      STRING  COMMENT '学科评估汇总JSON（如{"A+":21,"A":8}）'
        ) COMMENT '高校增强信息维度表。含保研率/联系方式/简介/标签/学科评估汇总。数据来自gaokao.cn school/info.json'
    """)

    conn.commit()
    print("三张增强表已创建")


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
    print(f"待采集: {len(schools)} 所学校的增强信息")

    conn = make_conn()
    init_tables(conn)
    cur = conn.cursor()

    dualclass_all = []
    fenxiao_all = []
    enriched_all = []
    errors = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fetch_school_enrich, sid): sid for sid in schools}
        for i, future in enumerate(as_completed(futures), 1):
            dc_rows, fx_rows, e_row = future.result()
            if e_row:
                dualclass_all.extend(dc_rows)
                fenxiao_all.extend(fx_rows)
                enriched_all.append(e_row)
            else:
                errors += 1
            if i % 100 == 0:
                print(f"  进度 {i}/{len(schools)}, 已采集 {len(enriched_all)} 所学校")

    # 批量写入
    def esc(v):
        if v is None:
            return 'NULL'
        if isinstance(v, (int, float)):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    def insert_rows(cur, table, rows):
        if not rows:
            return
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in batch)
            cur.execute(f"INSERT INTO {table} VALUES {vals}")

    insert_rows(cur, "gaokao_assistant.dim_dual_class", dualclass_all)
    conn.commit()
    print(f"dim_dual_class: {len(dualclass_all)} 条")

    insert_rows(cur, "gaokao_assistant.dim_campus", fenxiao_all)
    conn.commit()
    print(f"dim_campus: {len(fenxiao_all)} 条")

    insert_rows(cur, "gaokao_assistant.dim_school_enriched", enriched_all)
    conn.commit()
    print(f"dim_school_enriched: {len(enriched_all)} 条")

    conn.close()
    elapsed = time.time() - t_start
    print(f"\n完成！耗时 {elapsed/60:.1f} 分钟，错误: {errors}")

    update_table_comments()


def update_table_comments():
    conn = make_conn()
    cur = conn.cursor()
    counts = {}
    for t in ['dim_dual_class', 'dim_campus', 'dim_school_enriched']:
        try:
            cur.execute(f"SELECT COUNT(1) FROM gaokao_assistant.{t}")
            counts[t] = cur.fetchone()[0]
        except:
            counts[t] = 0

    comments = {
        'dim_dual_class': f"高校双一流建设学科列表，当前 {counts['dim_dual_class']:,} 条。数据来自gaokao.cn school/info.json的dualclass字段。",
        'dim_campus': f"高校校区和院系信息，当前 {counts['dim_campus']:,} 条。数据来自gaokao.cn school/info.json的fenxiao字段。",
        'dim_school_enriched': f"高校增强信息，当前 {counts['dim_school_enriched']:,} 所。含保研率/联系方式/简介/标签/学科评估汇总。数据来自gaokao.cn school/info.json。",
    }
    for table, comment in comments.items():
        safe = comment.replace("'", "''")
        cur.execute(f"ALTER TABLE gaokao_assistant.{table} SET COMMENT '{safe}'")
    conn.commit()
    conn.close()
    print("表注释已更新")


if __name__ == "__main__":
    main()
