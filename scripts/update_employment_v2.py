#!/usr/bin/env python3
import os, clickzetta, httpx, re, time

ENV_PATH = "/Users/liangmo/Documents/GitHub/gaokao_assistant/.env"
def load_env():
    with open(ENV_PATH) as f:
        for line in f:
            if '=' in line and not line.startswith('#'): k, v = line.split('=', 1); os.environ[k.strip()] = v.strip()

load_env()
print("Connecting to DB...")
conn = clickzetta.connect(service=os.environ["CZ_SERVICE"], instance=os.environ["CZ_INSTANCE"], workspace=os.environ["CZ_WORKSPACE"], username=os.environ["CZ_USERNAME"], password=os.environ["CZ_PASSWORD"], vcluster="default", schema="gaokao_assistant")
cur = conn.cursor()

cur.execute("SELECT school_id, name, ruanke_rank FROM dim_school WHERE ruanke_rank > 0 ORDER BY ruanke_rank ASC LIMIT 100")
schools = cur.fetchall()
print(f"Processing Top {len(schools)} schools.")

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://html.duckduckgo.com/html/"
updated = 0

for sid, name, rank in schools:
    print(f"🔍 {name} (Rank {rank})...", flush=True)
    try:
        resp = httpx.post(url, headers=headers, data={"q": f"{name} 2023 就业质量报告 总体就业率"}, timeout=5)
        if resp.status_code == 200:
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            for s in snippets:
                clean = re.sub(r'<[^>]+>', '', s)
                emp_match = re.search(r'(?:总体|本科)?.*?(?:就业|毕)业(?:去向落实率|率).*?(\d+\.?\d*)\s*%', clean)
                if not emp_match: emp_match = re.search(r'(?:去向落实率).*?(\d+\.?\d*)\s*%', clean)
                study_match = re.search(r'(?:升学率|深造率|国内升学).*?(\d+\.?\d*)\s*%', clean)
                if emp_match:
                    emp_rate = float(emp_match.group(1))
                    study_rate = float(study_match.group(1)) if study_match else None
                    print(f"   ✅ Found: Emp={emp_rate}%, Study={study_rate}%", flush=True)
                    if 50 < emp_rate < 99.9:
                        cur.execute(f"SELECT count(*) FROM dim_employment_report WHERE school_id={sid}")
                        exists = cur.fetchone()[0] > 0
                        if exists:
                            cur.execute(f"UPDATE dim_employment_report SET employment_rate={emp_rate}, further_study_rate={study_rate if study_rate else 'further_study_rate'}, source_platform='Official_Report_2023' WHERE school_id={sid}")
                        else:
                            cur.execute(f"INSERT INTO dim_employment_report (school_id, report_year, employment_rate, further_study_rate, source_platform) VALUES ({sid}, 2023, {emp_rate}, {study_rate if study_rate else 'NULL'}, 'Official_Report_2023')")
                        conn.commit()
                        updated += 1
                    break
    except Exception as e:
        print(f"   ❌ Error: {e}", flush=True)
    time.sleep(0.5)

print(f"✅ Done. Updated {updated} schools.")
conn.close()
