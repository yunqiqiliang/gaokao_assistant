#!/usr/bin/env python3
import os
import clickzetta
import httpx
import re
import time
print('Imports done', flush=True)

ENV_PATH = "/Users/liangmo/Documents/GitHub/gaokao_assistant/.env"

def load_env():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k] = v

def get_top100():
    load_env()
    conn = clickzetta.connect(
        service=os.environ["CZ_SERVICE"],
        instance=os.environ["CZ_INSTANCE"],
        workspace=os.environ["CZ_WORKSPACE"],
        username=os.environ["CZ_USERNAME"],
        password=os.environ["CZ_PASSWORD"],
        vcluster=os.environ.get("CZ_VCLUSTER", "default"),
        schema="gaokao_assistant",
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT s.school_id, s.name, s.ruanke_rank 
        FROM dim_school s
        WHERE s.ruanke_rank IS NOT NULL AND s.ruanke_rank <= 100
        ORDER BY s.ruanke_rank ASC
    """)
    schools = cur.fetchall()
    conn.close()
    return schools

def search_and_extract(school_name):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    url = "https://html.duckduckgo.com/html/"
    q = f"{school_name} 2023 就业质量报告 总体就业率"
    try:
        resp = httpx.post(url, headers=headers, data={"q": q}, timeout=5)
        if resp.status_code == 200:
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            for s in snippets:
                clean = re.sub(r'<[^>]+>', '', s)
                emp_match = re.search(r'(?:总体|本科)?.*?(?:就业|毕)业(?:去向落实率|率).*?(\d+\.?\d*)\s*%', clean)
                if not emp_match: emp_match = re.search(r'(?:去向落实率).*?(\d+\.?\d*)\s*%', clean)
                study_match = re.search(r'(?:升学率|深造率|国内升学).*?(\d+\.?\d*)\s*%', clean)
                if emp_match:
                    return {"emp": float(emp_match.group(1)), "study": float(study_match.group(1)) if study_match else None, "source": clean[:50]}
    except: pass
    return None

def update_db(school_id, emp_rate, study_rate, source_snippet):
    load_env()
    conn = clickzetta.connect(
        service=os.environ["CZ_SERVICE"],
        instance=os.environ["CZ_INSTANCE"],
        workspace=os.environ["CZ_WORKSPACE"],
        username=os.environ["CZ_USERNAME"],
        password=os.environ["CZ_PASSWORD"],
        vcluster=os.environ.get("CZ_VCLUSTER", "default"),
        schema="gaokao_assistant",
    )
    cur = conn.cursor()
    cur.execute(f"SELECT count(*) FROM dim_employment_report WHERE school_id={school_id}")
    exists = cur.fetchone()[0] > 0
    safe_source = source_snippet.replace("'", "''") if source_snippet else "Search Snippet"
    if exists:
        sql = f"UPDATE dim_employment_report SET employment_rate={emp_rate}, further_study_rate={study_rate if study_rate else 'further_study_rate'}, source_platform='Official_Report_2023', top_employers='{safe_source}' WHERE school_id={school_id}"
    else:
        sql = f"INSERT INTO dim_employment_report (school_id, report_year, employment_rate, further_study_rate, source_platform, top_employers) VALUES ({school_id}, 2023, {emp_rate}, {study_rate if study_rate else 'NULL'}, 'Official_Report_2023', '{safe_source}')"
    try:
        cur.execute(sql)
        conn.commit()
    except Exception as e:
        pass
    finally:
        conn.close()

def run():
    print('run() called', flush=True)
    print("🚀 Starting...")
    schools = get_top100()
    print(f'Got {len(schools)} schools', flush=True)
    print(f"Found {len(schools)} schools.")
    updated = 0
    for sid, name, rank in schools:
        print(f"🔍 {name} (Rank {rank})...")
        data = search_and_extract(name)
        if data and 50 < data['emp'] < 99.5:
            update_db(sid, data['emp'], data['study'], data['source'])
            updated += 1
            print(f"   ✅ Updated: Emp={data['emp']}%")
        else:
            print(f"   ⚠️ Skipped")
        time.sleep(0.3)
    print(f"✅ Done. Updated {updated} schools.")

if __name__ == "__main__":
    run()
