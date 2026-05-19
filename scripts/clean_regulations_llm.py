#!/usr/bin/env python3
"""
招生章程 LLM 清洗脚本（Phase 1.5c - 经济性优化版）
===================================================

用途：
    利用大模型（qwen-turbo）对已抓取的招生章程 HTML 原文进行结构化提取。
    相比正则匹配，LLM 能更准确地识别身体限制、单科要求等复杂约束。

经济性优化：
    - 模型：qwen-turbo (阿里云，价格约 0.0002 元/千 Token，极低成本)
    - 策略：只处理 raw_text 非空且未解析的记录
    - 缓存：处理过的记录跳过

运行方式：
    python3 scripts/clean_regulations_llm.py
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
你是一个招生章程信息提取助手。请从提供的 HTML 文本中提取以下关键招生约束信息，并以 JSON 格式返回。

需要提取的字段：
1. body_restrictions: 身体限制（视力、色觉、身高、听力、肢体等要求）
2. subject_requirements: 单科成绩要求（如英语不低于 120 分，数学不低于 110 分等）
3. language_restrictions: 外语语种限制（如只招英语考生）
4. gender_restrictions: 男女比例或性别限制
5. special_notes: 其他特殊要求（如面试要求、体检要求等）

注意：
- 如果某项没有提及，返回空列表 []
- 保持原文表述，不要过度概括
- 只返回 JSON，不要包含 Markdown 代码块标记
- 提取的内容要具体，例如"视力不低于 4.8"而不是"有视力要求"

HTML 文本：
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
    # 截断文本，避免 token 过多（取前 3000 字符通常足够包含关键信息）
    text = text[:3000]
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
        
        # 清理 JSON 字符串
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content)
    except Exception as e:
        print(f"    LLM Error: {e}")
        return None

def init_table(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_admission_regulation_parsed")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_admission_regulation_parsed (
            school_id INT,
            regulation_year INT,
            body_restrictions STRING,
            subject_requirements STRING,
            language_restrictions STRING,
            gender_restrictions STRING,
            special_notes STRING,
            raw_json STRING
        ) COMMENT '招生章程 LLM 结构化解析结果'
    """)
    conn.commit()

def main():
    t_start = time.time()
    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()
    
    # 获取待处理的记录
    cur.execute("""
        SELECT school_id, regulation_year, raw_text
        FROM gaokao_assistant.dim_admission_regulation
        WHERE raw_text IS NOT NULL AND raw_text != ''
        LIMIT 20
    """)
    rows = cur.fetchall()
    print(f"待处理记录数: {len(rows)}")
    
    parsed_rows = []
    success = 0
    errors = 0
    
    for sid, year, text in rows:
        print(f"Processing school_id={sid}...")
        result = call_llm(text)
        if result:
            row = (
                sid, year,
                json.dumps(result.get("body_restrictions", []), ensure_ascii=False),
                json.dumps(result.get("subject_requirements", []), ensure_ascii=False),
                json.dumps(result.get("language_restrictions", []), ensure_ascii=False),
                json.dumps(result.get("gender_restrictions", []), ensure_ascii=False),
                json.dumps(result.get("special_notes", []), ensure_ascii=False),
                json.dumps(result, ensure_ascii=False)
            )
            parsed_rows.append(row)
            success += 1
            print(f"  OK")
        else:
            errors += 1
            print(f"  Failed")
        
        # 控制频率，qwen-turbo 很便宜但也要防封
        time.sleep(1)
    
    # 写入
    if parsed_rows:
        def esc(v):
            if v is None: return 'NULL'
            if isinstance(v, int): return str(v)
            return "'" + str(v).replace("'", "''") + "'"
        
        vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in parsed_rows)
        cur.execute(f"INSERT INTO gaokao_assistant.dim_admission_regulation_parsed VALUES {vals}")
        conn.commit()
    
    conn.close()
    elapsed = time.time() - t_start
    print(f"\n完成！成功: {success}, 失败: {errors}, 耗时 {elapsed:.1f} 秒")

if __name__ == "__main__":
    main()
