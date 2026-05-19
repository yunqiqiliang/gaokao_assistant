#!/usr/bin/env python3
"""
招生章程深度爬取脚本（Playwright 版）
======================================

用途：
    使用 Playwright 绕过反爬，从阳光高考平台获取 Top 50 高校的招生章程正文。
    然后用 LLM (qwen-turbo) 提取结构化约束信息。

运行方式：
    python3 scripts/clean_regulations_playwright.py
"""
import json, time, os, re, requests
from playwright.sync_api import sync_playwright
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
你是一个招生章程信息提取助手。请从提供的招生章程文本中提取以下关键招生约束信息，并以 JSON 格式返回。

需要提取的字段：
1. body_restrictions: 身体限制（视力、色觉、身高、听力、肢体等要求）
2. subject_requirements: 单科成绩要求（如英语不低于 120 分，数学不低于 110 分等）
3. language_restrictions: 外语语种限制（如只招英语考生）
4. gender_restrictions: 男女比例或性别限制
5. special_notes: 其他特殊要求（如面试要求、体检要求、外语口试等）

注意：
- 如果某项没有提及，返回空列表 []
- 保持原文表述，不要过度概括
- 只返回 JSON，不要包含 Markdown 代码块标记
- 提取的内容要具体，例如"视力不低于 4.8"而不是"有视力要求"
- 特别注意"不予录取"、"受限"、"要求"等关键词后的内容

招生章程文本：
{text}
"""

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

def call_llm(text):
    text = text[:4000]
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
        print(f"    LLM Error: {e}")
        return None

def fetch_regulation_text(playwright, school_id):
    """使用 Playwright 获取招生章程正文"""
    url = f"https://gaokao.chsi.com.cn/zsgs/zhangcheng/listview?schoolId={school_id}"
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )
    page = context.new_page()
    
    try:
        print(f"  Navigating to: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        
        # 尝试点击 2026 年招生章程链接
        links = page.locator('a[href*="viewSchPage"]')
        count = links.count()
        print(f"  Found {count} regulation links")
        
        if count > 0:
            # 点击第一个链接（通常是最新的）
            links.first.click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)
        
        # 提取正文内容
        # 尝试多种选择器
        selectors = ['.zx-jc', '.content', '.article-content', '.main-content', 'body']
        text = None
        for sel in selectors:
            try:
                element = page.locator(sel).first
                if element.count() > 0:
                    text = element.inner_text()
                    if len(text) > 200:
                        break
            except:
                continue
        
        return text if text else page.locator('body').inner_text()[:5000]
    except Exception as e:
        print(f"  Playwright Error: {e}")
        return None
    finally:
        browser.close()

def init_table(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_admission_regulation_parsed_v2")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_admission_regulation_parsed_v2 (
            school_id INT,
            school_name STRING,
            regulation_year INT,
            body_restrictions STRING,
            subject_requirements STRING,
            language_restrictions STRING,
            gender_restrictions STRING,
            special_notes STRING,
            raw_json STRING,
            source TEXT
        ) COMMENT '招生章程 LLM 结构化解析结果 (Playwright 版)'
    """)
    conn.commit()

def main():
    t_start = time.time()
    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()
    
    # Top 50 高校
    top_schools = [
        (140, "清华大学"), (31, "北京大学"), (114, "浙江大学"), (125, "上海交通大学"),
        (132, "复旦大学"), (111, "南京大学"), (66, "中国科学技术大学"), (127, "华中科技大学"),
        (42, "武汉大学"), (330, "西安交通大学"), (104, "中山大学"), (47, "北京航空航天大学"),
        (143, "北京理工大学"), (60, "天津大学"), (73, "同济大学"), (99, "四川大学"),
        (109, "东南大学"), (59, "南开大学"), (126, "山东大学"), (122, "吉林大学"),
        (102, "厦门大学"), (130, "上海财经大学"), (46, "中国人民大学"), (566, "中央财经大学"),
        (138, "大连理工大学"), (105, "华南理工大学"), (123, "中南大学"), (44, "湖南大学"),
        (661, "电子科技大学"), (107, "西北工业大学"), (97, "兰州大学"), (119, "重庆大学"),
        (52, "北京师范大学"), (136, "上海外国语大学"), (76, "上海大学"), (86, "江南大学"),
        (112, "南京理工大学"), (116, "河海大学"), (118, "苏州大学"), (133, "华东理工大学"),
        (134, "东北大学"), (144, "北京科技大学"), (164, "南京财经大学"), (229, "东北财经大学"),
        (284, "深圳大学"), (307, "上海理工大学"), (310, "上海中医药大学"), (414, "中南财经政法大学"),
        (499, "青岛大学"), (504, "海南大学"),
    ]
    
    print(f"待处理 {len(top_schools)} 所高校")
    
    parsed_rows = []
    success = 0
    errors = 0
    
    with sync_playwright() as p:
        for idx, (sid, name) in enumerate(top_schools):
            print(f"\n[{idx+1}/{len(top_schools)}] Processing {name} (ID: {sid})...")
            
            text = fetch_regulation_text(p, sid)
            if not text or len(text) < 100:
                print(f"  Failed to fetch regulation text")
                errors += 1
                continue
            
            print(f"  Fetched {len(text)} chars")
            
            result = call_llm(text)
            if result:
                row = (
                    sid, name, 2026,
                    json.dumps(result.get("body_restrictions", []), ensure_ascii=False),
                    json.dumps(result.get("subject_requirements", []), ensure_ascii=False),
                    json.dumps(result.get("language_restrictions", []), ensure_ascii=False),
                    json.dumps(result.get("gender_restrictions", []), ensure_ascii=False),
                    json.dumps(result.get("special_notes", []), ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                    "Chsi_Playwright"
                )
                parsed_rows.append(row)
                success += 1
                flags = []
                if result.get("body_restrictions"): flags.append('body')
                if result.get("subject_requirements"): flags.append('subject')
                if result.get("language_restrictions"): flags.append('lang')
                if result.get("special_notes"): flags.append('notes')
                print(f"  OK {' '.join(flags) if flags else '(empty)'}")
            else:
                errors += 1
                print(f"  LLM Failed")
            
            time.sleep(3)
    
    if parsed_rows:
        def esc(v):
            if v is None: return 'NULL'
            if isinstance(v, int): return str(v)
            return "'" + str(v).replace("'", "''") + "'"
        
        for i in range(0, len(parsed_rows), 10):
            batch = parsed_rows[i:i+10]
            vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in batch)
            cur.execute(f"INSERT INTO gaokao_assistant.dim_admission_regulation_parsed_v2 VALUES {vals}")
            conn.commit()
    
    conn.close()
    elapsed = time.time() - t_start
    print(f"\n完成！成功: {success}, 失败: {errors}, 耗时 {elapsed/60:.1f} 分钟")

if __name__ == "__main__":
    main()
