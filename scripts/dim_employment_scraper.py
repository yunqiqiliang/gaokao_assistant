#!/usr/bin/env python3
"""
高校就业质量报告采集脚本（Phase 1.6）
======================================

用途：
    采集 Top 20 高校的 2023 届毕业生就业质量报告核心数据。
    包括：深造率、薪酬、主要就业去向等。

经济性优化：
    - 使用 qwen-turbo 进行信息提取（低成本）
    - 仅采集 HTML 摘要页，不下载 PDF

运行方式：
    python3 scripts/dim_employment_scraper.py
"""
import json, time, os, re, requests
import clickzetta

# 从 ClickZetta 配置读取 API Key
def get_dashscope_api_key():
    config_path = os.path.expanduser("~/.clickzetta/lakehouse_connection/connections.json")
    with open(config_path) as f:
        cfg = json.load(f)
    return cfg["system_config"]["embedding"]["dashscope"]["api_key"]

API_KEY = get_dashscope_api_key()
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

PROMPT = """
你是一个就业数据分析助手。请从提供的文本中提取以下就业质量数据，并以 JSON 格式返回。

需要提取的字段：
1. report_year: 报告年份（如 2023）
2. overall_employment_rate: 总体就业率（百分比，如 95.5）
3. further_study_rate: 深造率（国内读研 + 出国深造，百分比，如 55.0）
4. domestic_study_rate: 国内深造率（百分比）
5. overseas_study_rate: 出国深造率（百分比）
6. avg_salary: 平均薪酬（元/月，数字，如 12000）
7. top_employers: 主要就业单位列表（前 5 个，如 ["华为", "腾讯", "国家电网"]）
8. top_industries: 主要就业行业列表（前 5 个，如 ["信息技术", "金融业"]）

注意：
- 如果某项没有提及，返回 null
- 数字字段只保留数字，不要带百分号或单位
- 只返回 JSON，不要包含 Markdown 代码块标记

文本：
{text}
"""

# Top 10 高校就业网 URL (需要验证)
SCHOOL_JOBS = {
    140: "http://www.career.tsinghua.edu.cn",
    31: "http://www.scc.pku.edu.cn",
    114: "http://www.career.zju.edu.cn",
    125: "http://career.sjtu.edu.cn",
    132: "http://www.career.fudan.edu.cn",
    111: "http://career.nju.edu.cn",
    66: "http://career.ustc.edu.cn",
    127: "http://career.hust.edu.cn",
    42: "http://career.whu.edu.cn",
    330: "http://job.xjtu.edu.cn",
    104: "http://career.sysu.edu.cn",
    47: "http://job.buaa.edu.cn",
    143: "http://job.bit.edu.cn",
    60: "http://job.tju.edu.cn",
    73: "http://career.tongji.edu.cn",
    99: "http://career.scu.edu.cn",
    109: "http://career.seu.edu.cn",
    59: "http://job.nankai.edu.cn",
    126: "http://career.sdu.edu.cn",
    122: "http://job.jlu.edu.cn",
}

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

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

def fetch_text(url, timeout=10):
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.encoding = resp.apparent_encoding
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', resp.text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except:
        return None

def call_llm(text):
    text = text[:3000] # 限制长度
    prompt = PROMPT.format(text=text)
    payload = {
        "model": "qwen-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }
    try:
        resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        content = content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.endswith("```"): content = content[:-3]
        return json.loads(content)
    except Exception as e:
        return None

def init_table(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_employment_report")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_employment_report (
            school_id INT,
            report_year INT,
            overall_employment_rate DOUBLE,
            further_study_rate DOUBLE,
            domestic_study_rate DOUBLE,
            overseas_study_rate DOUBLE,
            avg_salary DOUBLE,
            top_employers STRING,
            top_industries STRING,
            source_url STRING
        ) COMMENT '高校毕业生就业质量报告数据'
    """)
    conn.commit()

def main():
    t_start = time.time()
    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()
    
    rows = []
    success = 0
    
    # 针对每个学校，尝试找 2023 就业报告
    for sid, base_url in SCHOOL_JOBS.items():
        print(f"Processing school_id={sid} ({base_url})...")
        
        # 尝试访问就业网首页，找包含 "2023" 和 "就业质量" 的链接
        home_text = fetch_text(base_url)
        if not home_text:
            print(f"  Failed to fetch home page")
            continue
            
        # 简单查找链接
        links = re.findall(r'href="([^"]*2023[^"]*|[^"]*就业[^"]*2023[^"]*)"', home_text)
        if not links:
            # 尝试直接访问常见路径
            candidate_urls = [
                f"{base_url}/zljg/2023.htm",
                f"{base_url}/zljg/2023.html",
                f"{base_url}/2023.htm",
            ]
        else:
            candidate_urls = [links[0]] # 取第一个匹配
        
        # 尝试访问候选 URL
        report_text = None
        report_url = None
        for url in candidate_urls:
            if not url.startswith("http"):
                url = base_url.rstrip('/') + '/' + url.lstrip('/')
            text = fetch_text(url)
            if text and ("2023" in text or "就业" in text):
                report_text = text
                report_url = url
                break
        
        if report_text:
            print(f"  Found report at: {report_url}")
            result = call_llm(report_text)
            if result and result.get("report_year"):
                row = (
                    sid,
                    result.get("report_year"),
                    result.get("overall_employment_rate"),
                    result.get("further_study_rate"),
                    result.get("domestic_study_rate"),
                    result.get("overseas_study_rate"),
                    result.get("avg_salary"),
                    json.dumps(result.get("top_employers", []), ensure_ascii=False),
                    json.dumps(result.get("top_industries", []), ensure_ascii=False),
                    report_url
                )
                rows.append(row)
                success += 1
                print(f"  OK: year={result.get('report_year')}")
            else:
                print(f"  LLM failed to extract")
        else:
            print(f"  No report found")
        
        time.sleep(2)
    
    # 写入
    if rows:
        def esc(v):
            if v is None: return 'NULL'
            if isinstance(v, (int, float)): return str(v)
            return "'" + str(v).replace("'", "''") + "'"
        
        vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in rows)
        cur.execute(f"INSERT INTO gaokao_assistant.dim_employment_report VALUES {vals}")
        conn.commit()
    
    conn.close()
    elapsed = time.time() - t_start
    print(f"\n完成！成功: {success}, 耗时 {elapsed:.1f} 秒")

if __name__ == "__main__":
    main()
