#!/usr/bin/env python3
"""
软科就业质量数据采集脚本（Phase 1.6 - 优化版）
================================================

用途：
    从软科（ShanghaiRanking）爬取 Top 100 高校的就业相关指标。
    数据源：
    1. 中国大学排名（本科）- 提取深造率
    2. 中国高校毕业生就业质量排名 - 提取就业质量指数

特点：
    - 零 LLM 成本（直接解析 HTML 表格）
    - 数据权威（软科指标被广泛引用）

运行方式：
    python3 scripts/dim_employment_shanghairanking_scraper.py
"""
import requests, json, time, os, re
import clickzetta

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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

def fetch_html(url):
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.encoding = "utf-8"
        return resp.text
    except Exception as e:
        print(f"Fetch Error {url}: {e}")
        return None

def parse_table_from_html(html, table_class="rk-table"):
    """简单的 HTML 表格解析"""
    if not html: return []
    
    # 软科表格通常在 div.rk-table 中
    # 这里我们用正则简单提取 tr 和 td，因为软科结构相对固定
    # 更好的方式是用 BeautifulSoup，但为了减少依赖先用正则
    
    rows = []
    # 匹配 <tr>...</tr>
    trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    
    for tr in trs:
        # 匹配 <td>...</td>
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
        row_data = []
        for td in tds:
            # 清理 HTML 标签
            text = re.sub(r'<[^>]+>', '', td).strip()
            # 清理多余空白
            text = re.sub(r'\s+', ' ', text)
            row_data.append(text)
        if row_data:
            rows.append(row_data)
    return rows

def init_table(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_employment_report")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_employment_report (
            school_id INT,
            report_year INT,
            source_platform STRING COMMENT '数据来源平台',
            further_study_rate DOUBLE COMMENT '深造率（软科本科排名）',
            employment_quality_rank INT COMMENT '就业质量排名',
            employment_quality_score DOUBLE COMMENT '就业质量得分',
            overall_rank INT COMMENT '综合排名',
            raw_data STRING
        ) COMMENT '高校毕业生就业与深造指标（来源：软科）'
    """)
    conn.commit()

def main():
    t_start = time.time()
    print("开始采集软科就业数据...")
    
    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()
    
    # 1. 采集 2023 中国大学排名（含深造率）
    # URL: https://www.shanghairanking.cn/rankings/bcur/202311
    url_bcur = "https://www.shanghairanking.cn/rankings/bcur/202311"
    print(f"Fetching Bcur (Deepening Rate)...")
    html_bcur = fetch_html(url_bcur)
    
    bcur_data = {} # school_name -> {deepening_rate, rank}
    if html_bcur:
        rows = parse_table_from_html(html_bcur)
        # 表头通常在第一行
        # 软科排名表结构：排名 | 学校名称 | 省市 | 类型 | 总分 | 办学层次 | ... | 深造率 | ...
        # 我们需要找到"深造率"所在的列索引
        
        header_row = None
        data_rows = []
        
        for row in rows:
            if "排名" in row[0] or "学校名称" in row[0]:
                header_row = row
            else:
                data_rows.append(row)
        
        if header_row:
            print(f"Header: {header_row}")
            # 找列索引
            rank_idx = 0
            name_idx = 1
            deepening_idx = -1
            
            for i, h in enumerate(header_row):
                if "深造率" in h:
                    deepening_idx = i
                if "学校名称" in h or "name" in h.lower():
                    name_idx = i
            
            if deepening_idx != -1:
                for row in data_rows:
                    if len(row) > max(name_idx, deepening_idx):
                        name = row[name_idx]
                        rate_str = row[deepening_idx].replace('%', '')
                        try:
                            rate = float(rate_str)
                            bcur_data[name] = {
                                "further_study_rate": rate,
                                "overall_rank": int(row[rank_idx])
                            }
                        except:
                            pass
        
        print(f"Extracted {len(bcur_data)} records from Bcur")

    # 2. 采集 2023 毕业生就业质量排名
    # URL: https://www.shanghairanking.cn/rankings/employ-quality/2023
    url_employ = "https://www.shanghairanking.cn/rankings/employ-quality/2023"
    print(f"Fetching Employment Quality...")
    html_employ = fetch_html(url_employ)
    
    employ_data = {} # school_name -> {rank, score}
    if html_employ:
        rows = parse_table_from_html(html_employ)
        header_row = None
        data_rows = []
        for row in rows:
            if "排名" in row[0] or "学校名称" in row[0]:
                header_row = row
            else:
                data_rows.append(row)
        
        if header_row:
            name_idx = 1
            score_idx = -1
            rank_idx = 0
            
            for i, h in enumerate(header_row):
                if "得分" in h or "score" in h.lower():
                    score_idx = i
            
            for row in data_rows:
                if len(row) > max(name_idx, score_idx):
                    name = row[name_idx]
                    score_str = row[score_idx]
                    try:
                        score = float(score_str)
                        employ_data[name] = {
                            "employment_quality_rank": int(row[rank_idx]),
                            "employment_quality_score": score
                        }
                    except:
                        pass
        print(f"Extracted {len(employ_data)} records from Employment Quality")

    # 3. 合并数据并映射 School ID
    print("Merging and mapping School IDs...")
    
    # 获取数仓中的学校映射
    cur.execute("SELECT school_id, name FROM gaokao_assistant.dim_school")
    school_map = {row[1]: row[0] for row in cur.fetchall()}
    
    merged_rows = []
    all_schools = set(list(bcur_data.keys()) + list(employ_data.keys()))
    
    for name in all_schools:
        sid = school_map.get(name)
        if not sid:
            # 尝试模糊匹配（简单处理：去括号或简称）
            # 这里先只处理完全匹配的
            continue
            
        bcur = bcur_data.get(name, {})
        employ = employ_data.get(name, {})
        
        if bcur or employ:
            raw_json = json.dumps({"bcur": bcur, "employ": employ}, ensure_ascii=False)
            row = (
                sid,
                2023,
                "ShanghaiRanking",
                bcur.get("further_study_rate"),
                employ.get("employment_quality_rank"),
                employ.get("employment_quality_score"),
                bcur.get("overall_rank"),
                raw_json
            )
            merged_rows.append(row)
    
    print(f"Mapped {len(merged_rows)} schools")
    
    # 4. 入库
    if merged_rows:
        def esc(v):
            if v is None: return 'NULL'
            if isinstance(v, (int, float)): return str(v)
            return "'" + str(v).replace("'", "''") + "'"
        
        # 分批插入
        for i in range(0, len(merged_rows), 50):
            batch = merged_rows[i:i+50]
            vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in batch)
            cur.execute(f"INSERT INTO gaokao_assistant.dim_employment_report VALUES {vals}")
        conn.commit()
    
    conn.close()
    elapsed = time.time() - t_start
    print(f"\n完成！入库 {len(merged_rows)} 条记录，耗时 {elapsed:.1f} 秒")

if __name__ == "__main__":
    main()
