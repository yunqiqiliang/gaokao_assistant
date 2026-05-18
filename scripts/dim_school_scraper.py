#!/usr/bin/env python3
"""
高校维度数据采集脚本
采集内容：
  - dim_school       高校基本信息（名称/省市/类型/985/211/双一流/排名等）
  - dim_school_rank  高校各榜单排名（软科/QS/US/泰晤士）
  - dim_school_special 高校专业评级（国家一流专业/学科评级）

数据来源：https://static-data.gaokao.cn/www/2.0/school/{school_id}/info.json
前置条件：
  - pip install clickzetta-connector
  - /tmp/university_info.csv（学校列表，含学校抓取编码列）
  - ClickZetta Lakehouse 连接配置

运行方式：
  python3 dim_school_scraper.py

耗时：约 3-5 分钟（500所学校，16线程）
"""
import urllib.request, json, csv, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
import clickzetta

WORKERS = 16
BASE = "https://static-data.gaokao.cn/www/2.0"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.gaokao.cn/"}

# ── ClickZetta 连接 ────────────────────────────────────────
# 建议改为从环境变量读取，避免明文密码
def make_conn():
    return clickzetta.connect(
        service=os.environ.get("CZ_SERVICE", "https://cn-shanghai-alicloud.api.clickzetta.com"),
        instance=os.environ.get("CZ_INSTANCE", "f8866243"),
        workspace=os.environ.get("CZ_WORKSPACE", "quick_start"),
        username=os.environ.get("CZ_USERNAME", "qiliang"),
        password=os.environ.get("CZ_PASSWORD", "Ql123456!"),
        vcluster=os.environ.get("CZ_VCLUSTER", "default"),
        schema="gaokao_assistant",
    )

def fetch_school_info(school_id):
    url = f"{BASE}/school/{school_id}/info.json"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("code") != "0000":
            return None, None, None
        d = data["data"]

        # dim_school 行
        school_row = (
            int(school_id),
            d.get("name") or None,
            d.get("province_name") or None,
            d.get("city_name") or None,
            d.get("type_name") or None,           # 综合类/理工类/师范类等
            d.get("school_nature_name") or None,   # 公办/民办
            d.get("level_name") or None,           # 本科/专科
            int(d.get("f985") or 0),
            int(d.get("f211") or 0),
            d.get("dual_class_name") or None,      # 双一流/None
            int(d.get("num_subject") or 0),        # 国家重点学科数
            int(d.get("num_master") or 0),
            int(d.get("num_doctor") or 0),
            int(d.get("num_academician") or 0),
            int(d.get("ruanke_rank") or 0),
            d.get("qs_rank") or None,
            d.get("motto") or None,
            d.get("address") or None,
            d.get("site") or None,
        )

        # dim_school_rank 行（多条）
        rank_rows = []
        for r in (data.get("data", {}).get("rank") or []):
            rank_rows.append((
                int(school_id),
                r.get("rank_name") or None,
                r.get("rank") or None,
            ))
        # rank 也可能在单独接口
        url2 = f"{BASE}/school/{school_id}/rank.json"
        try:
            req2 = urllib.request.Request(url2, headers=HEADERS)
            with urllib.request.urlopen(req2, timeout=8) as resp2:
                data2 = json.loads(resp2.read())
            for r in (data2.get("data") or []):
                rank_rows.append((
                    int(school_id),
                    r.get("rank_name") or None,
                    r.get("rank") or None,
                ))
        except:
            pass

        # dim_school_special 行（多条）
        special_rows = []
        url3 = f"{BASE}/school/{school_id}/special/list.json"
        try:
            req3 = urllib.request.Request(url3, headers=HEADERS)
            with urllib.request.urlopen(req3, timeout=8) as resp3:
                data3 = json.loads(resp3.read())
            for s in (data3.get("data") or []):
                special_rows.append((
                    int(school_id),
                    s.get("special_id") or None,
                    s.get("name") or None,
                    s.get("xueke_rank") or None,       # 学科评级排名
                    s.get("xueke_rank_score") or None, # A+/A/B+等
                    s.get("ruanke_rank") or None,
                    s.get("ruanke_level") or None,
                    int(s.get("nation_first_class") or 0),  # 国家一流专业
                    int(s.get("nation_feature") or 0),      # 国家特色专业
                    s.get("limit_year") or None,            # 学制
                ))
        except:
            pass

        return school_row, rank_rows, special_rows
    except:
        return None, None, None


def init_tables(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_school")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_school (
            school_id        INT     COMMENT '高校ID，与 fact_admission_history.school_id 关联',
            name             STRING  COMMENT '高校名称',
            province_name    STRING  COMMENT '所在省份',
            city_name        STRING  COMMENT '所在城市',
            type_name        STRING  COMMENT '院校类型（综合类/理工类/师范类等）',
            school_nature    STRING  COMMENT '办学性质（公办/民办）',
            level_name       STRING  COMMENT '办学层次（本科/专科）',
            f985             INT     COMMENT '是否985（1=是，0=否）',
            f211             INT     COMMENT '是否211（1=是，0=否）',
            dual_class       STRING  COMMENT '双一流类型（双一流/NULL=非双一流）',
            num_subject      INT     COMMENT '国家重点学科数',
            num_master       INT     COMMENT '硕士点数',
            num_doctor       INT     COMMENT '博士点数',
            num_academician  INT     COMMENT '院士数',
            ruanke_rank      INT     COMMENT '软科综合排名（0=未上榜）',
            qs_rank          STRING  COMMENT 'QS世界排名',
            motto            STRING  COMMENT '校训',
            address          STRING  COMMENT '学校地址',
            site             STRING  COMMENT '招生网站'
        )
    """)

    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_school_rank")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_school_rank (
            school_id   INT    COMMENT '高校ID',
            rank_name   STRING COMMENT '榜单名称（软科综合/QS世界/US世界/泰晤士等）',
            rank        STRING COMMENT '排名（字符串，因部分榜单含区间如501-600）'
        )
    """)

    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_school_special")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_school_special (
            school_id          INT    COMMENT '高校ID',
            special_id         STRING COMMENT '专业ID',
            name               STRING COMMENT '专业名称',
            xueke_rank         STRING COMMENT '教育部学科评估排名',
            xueke_rank_score   STRING COMMENT '学科评估等级（A+/A/A-/B+等）',
            ruanke_rank        STRING COMMENT '软科专业排名',
            ruanke_level       STRING COMMENT '软科专业等级',
            nation_first_class INT    COMMENT '国家一流专业（1=是，2=否）',
            nation_feature     INT    COMMENT '国家特色专业（1=是，2=否）',
            limit_year         STRING COMMENT '学制（四年/五年等）'
        )
    """)
    conn.commit()
    print("三张维度表已创建")


def main():
    # 读取学校列表
    schools = []
    with open('/tmp/university_info.csv') as f:
        for row in csv.DictReader(f):
            try:
                rank = int(row['全国热度排名'])
                sid = row['学校抓取编码'].strip()
                if sid and rank <= 500:
                    schools.append(sid)
            except:
                pass
    print(f"待采集: {len(schools)} 所学校")

    conn = make_conn()
    init_tables(conn)
    cur = conn.cursor()

    school_rows, rank_rows_all, special_rows_all = [], [], []
    errors = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fetch_school_info, sid): sid for sid in schools}
        for i, future in enumerate(as_completed(futures), 1):
            s_row, r_rows, sp_rows = future.result()
            if s_row:
                school_rows.append(s_row)
                if r_rows: rank_rows_all.extend(r_rows)
                if sp_rows: special_rows_all.extend(sp_rows)
            else:
                errors += 1
            if i % 50 == 0:
                print(f"  进度 {i}/{len(schools)}, 已采集 {len(school_rows)} 所")

    # 批量写入
    INSERT_SCHOOL = (
        "INSERT INTO gaokao_assistant.dim_school VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    INSERT_RANK = "INSERT INTO gaokao_assistant.dim_school_rank VALUES (?,?,?)"
    INSERT_SPECIAL = "INSERT INTO gaokao_assistant.dim_school_special VALUES (?,?,?,?,?,?,?,?,?,?)"

    cur.executemany(INSERT_SCHOOL, school_rows)
    cur.executemany(INSERT_RANK, rank_rows_all)
    cur.executemany(INSERT_SPECIAL, special_rows_all)
    conn.commit()
    conn.close()

    print(f"完成！dim_school: {len(school_rows)} 行, dim_school_rank: {len(rank_rows_all)} 行, dim_school_special: {len(special_rows_all)} 行, 错误: {errors}")


if __name__ == "__main__":
    main()
