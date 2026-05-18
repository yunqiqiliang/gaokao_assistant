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
            int(''.join(c for c in str(d.get("ruanke_rank") or '0') if c.isdigit()) or 0),
            d.get("qs_rank") or None,
            d.get("motto") or None,
            d.get("address") or None,
            d.get("site") or None,
        )

        # dim_school_rank 行（多条）—— 只用 rank.json 接口（info.json 里的 rank 是 dict 不是列表）
        rank_rows = []
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
    except Exception as e:
        import traceback
        print(f'ERROR school_id={school_id}: {e}')
        traceback.print_exc()
        return None, None, None


def init_tables(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_school")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_school (
            school_id        INT     COMMENT '高校ID，与 fact_admission_history.school_id 关联（如清华=140，北大=31，复旦=132，上交=125，浙大=114，西交=330）',
            name             STRING  COMMENT '高校全称（如清华大学）',
            province_name    STRING  COMMENT '高校所在省份（如北京、上海）',
            city_name        STRING  COMMENT '高校所在城市（如北京市、上海市）',
            type_name        STRING  COMMENT '院校类型，按学科特色分类：综合类/理工类/师范类/财经类/医药类/农林类/政法类/语言类/艺术类/体育类/民族类',
            school_nature    STRING  COMMENT '办学性质：公办/民办/中外合作办学。API 原始字段名为 school_nature_name',
            level_name       STRING  COMMENT '办学层次：本科/专科（高职）',
            f985             INT     COMMENT '是否 985 工程院校（1=是，0=否）。全国共 39 所',
            f211             INT     COMMENT '是否 211 工程院校（1=是，0=否）。全国共 116 所，含全部 985',
            dual_class       STRING  COMMENT '双一流建设类别：双一流A类/双一流B类/NULL=非双一流。共 147 所双一流高校',
            num_subject      INT     COMMENT '国家一级重点学科数（教育部评定）。清华=21，北大=18，浙大=14',
            num_master       INT     COMMENT '一级学科硕士点数量',
            num_doctor       INT     COMMENT '一级学科博士点数量',
            num_academician  INT     COMMENT '两院院士数量（中国科学院+中国工程院在校）。清华=89，北大=76',
            ruanke_rank      INT     COMMENT '软科中国大学综合排名。0=未上榜或排名500+。每年更新，以采集时数据为准',
            qs_rank          STRING  COMMENT 'QS 世界大学排名。字符串类型，因部分学校排名为区间（如 501-510）。NULL=未上榜',
            motto            STRING  COMMENT '校训',
            address          STRING  COMMENT '学校地址',
            site             STRING  COMMENT '招生官网 URL'
        ) COMMENT '高校基本信息维度表。含院校类型/985/211/双一流/软科排名/QS排名/院士数/校训等19个字段。数据来源：gaokao.cn school/info.json 接口'
    """)

    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_school_rank")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_school_rank (
            school_id   INT    COMMENT '高校ID，关联 dim_school.school_id',
            rank_name   STRING COMMENT '榜单名称。共6类：软科综合/校友会综合/QS世界/US世界/泰晤士（大陆）/人气值排名',
            rank        STRING COMMENT '排名值（字符串，部分榜单含区间如 501-600 或 1000+）'
        ) COMMENT '高校多榜单排名明细表。每所学校最多6条，覆盖软科综合/校友会综合/QS世界/US世界/泰晤士（大陆）/人气值排名。数据来源：gaokao.cn school/rank.json 接口'
    """)

    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_school_special")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_school_special (
            school_id          INT    COMMENT '高校ID，关联 dim_school.school_id',
            special_id         STRING COMMENT '专业ID（教育部专业目录编码，如建筑学=241，计算机科学与技术=080901）',
            name               STRING COMMENT '专业名称（标准名称，不含方向备注）',
            xueke_rank         STRING COMMENT '教育部学科评估排名（第几名）。来源：教育部第四轮学科评估（2017年）',
            xueke_rank_score   STRING COMMENT '教育部学科评估等级：A+（前2%）/A（2-5%）/A-（5-10%）/B+（10-20%）/B（20-30%）/B-（30-40%）/C+/C/C-',
            ruanke_rank        STRING COMMENT '软科中国最好学科排名（该专业在全国的排名位次）',
            ruanke_level       STRING COMMENT '软科学科等级（A+/A/A-/B+/B/B-/C+/C/C-，与教育部评估格式一致）',
            nation_first_class INT    COMMENT '国家级一流本科专业建设点（教育部双万计划）：1=是，2=否。全国约1万个国家级一流专业点',
            nation_feature     INT    COMMENT '国家特色专业（教育部本科教学工程，早于双万计划）：1=是，2=否',
            limit_year         STRING COMMENT '标准学制：四年/五年（建筑学、医学等）/三年（专科）'
        ) COMMENT '高校专业评级维度表。含教育部学科评估等级（A+~C-）、软科学科排名、国家一流专业/特色专业标识。注意：基于2017年第四轮学科评估，第五轮（2022年）结果尚未更新。数据来源：gaokao.cn school/special/list.json 接口'
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
                if sid:  # 全量2784所
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
    def esc(v):
        if v is None:
            return 'NULL'
        if isinstance(v, int):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    def insert_rows(cur, table, rows):
        if not rows:
            return
        # 每批500行
        for i in range(0, len(rows), 500):
            batch = rows[i:i+500]
            vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in batch)
            cur.execute(f"INSERT INTO {table} VALUES {vals}")

    insert_rows(cur, "gaokao_assistant.dim_school", school_rows)
    conn.commit()
    insert_rows(cur, "gaokao_assistant.dim_school_rank", rank_rows_all)
    conn.commit()
    insert_rows(cur, "gaokao_assistant.dim_school_special", special_rows_all)
    conn.commit()
    conn.close()

    print(f"完成！dim_school: {len(school_rows)} 行, dim_school_rank: {len(rank_rows_all)} 行, dim_school_special: {len(special_rows_all)} 行, 错误: {errors}")


if __name__ == "__main__":
    main()
