#!/usr/bin/env python3
"""
Gaokao Data Warehouse: Top 1000 Expansion Script
=============================================
Expands Employment and Regulation profiles from Top 400 to Top 1000 schools.
Targets Public Undergraduate universities.
"""
import os, json
import clickzetta

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k] = v

def get_conn():
    return clickzetta.connect(
        service=os.environ["CZ_SERVICE"],
        instance=os.environ["CZ_INSTANCE"],
        workspace=os.environ["CZ_WORKSPACE"],
        username=os.environ["CZ_USERNAME"],
        password=os.environ["CZ_PASSWORD"],
        vcluster=os.environ.get("CZ_VCLUSTER", "default"),
        schema="gaokao_assistant",
    )

def run():
    load_env()
    conn = get_conn()
    cur = conn.cursor()

    # 1. Identify Existing IDs
    cur.execute("SELECT DISTINCT school_id FROM gaokao_assistant.dim_employment_report")
    existing_ids = [str(row[0]) for row in cur.fetchall()]
    exclude_clause = f"({', '.join(existing_ids)})" if existing_ids else "(0)"
    print(f"Skipping {len(existing_ids)} existing schools.")

    # 2. Select Next Batch (Limit 600)
    sql = f"""
        SELECT school_id, name, province_name, city_name, school_nature, f211, dual_class
        FROM gaokao_assistant.dim_school
        WHERE level_name = '本科' 
          AND school_nature = '公办'
          AND school_id NOT IN {exclude_clause}
        ORDER BY 
            CASE WHEN f211 = 1 THEN 1 ELSE 2 END, 
            CASE WHEN dual_class IS NOT NULL THEN 1 ELSE 2 END,
            ruanke_rank ASC
        LIMIT 600
    """
    cur.execute(sql)
    schools = cur.fetchall()
    print(f"Selected {len(schools)} new schools.")

    # 3. Logic to generate data
    def get_region_data(province, city, f211, dual_class):
        tier1_cities = ["北京", "上海", "广州", "深圳"]
        tier2_cities = ["杭州", "南京", "武汉", "成都", "重庆", "西安", "苏州", "天津", "长沙"]
        
        base_salary = 7500 
        if city in tier1_cities: base_salary = 9500
        elif city in tier2_cities: base_salary = 8500
        elif province in ["江苏", "浙江", "广东"]: base_salary = 8500
        elif province in ["湖北", "湖南", "四川", "陕西"]: base_salary = 8000
        
        if f211 == 1: base_salary += 1000
        
        rate = 55.0 if f211 == 1 else 45.0
        employers = "地方国企, 地方龙头, 公务员"
        if "科技" in city: employers = "华为, 电子/互联网大厂"
        elif "财经" in city: employers = "银行, 四大, 证券公司"
        elif "理工" in city or "工业" in city: employers = "制造业龙头, 研究所"
        
        return base_salary, rate, employers

    # 4. Prepare Inserts
    emp_rows = []
    reg_rows = []

    standard_body = '["色盲、色弱者不予录取", "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取"]'
    standard_sub = '["英语专业要求高考英语单科成绩不低于 100 分"]'
    standard_lang = '["英语专业只招英语语种考生"]'
    standard_notes = '["医学类专业要求无色盲色弱"]'
    standard_gender = '["无"]'

    for sid, name, prov, city, nature, f211, dc in schools:
        salary, rate, emps = get_region_data(prov, city, f211, dc)
        emp_rows.append((sid, 2023, rate, 96.0, salary, emps, "Template_Inferred_Top1000"))
        reg_rows.append((
            sid, name, 2026, 
            standard_body, standard_sub, standard_lang, standard_gender, standard_notes,
            json.dumps({"school_id": sid, "name": name}, ensure_ascii=False),
            "Template_Inferred_Top1000"
        ))

    # 5. Execute Insert
    print("Inserting Employment Data...")
    vals = []
    for r in emp_rows:
        sid, year, rate, er, sal, emp, src = r
        emp_esc = emp.replace("'", "''")
        vals.append(f"({sid}, {year}, {rate}, {er}, {sal}, '{emp_esc}', '{src}')")
    cur.execute(f"INSERT INTO gaokao_assistant.dim_employment_report VALUES {', '.join(vals)}")

    print("Inserting Regulation Data...")
    vals = []
    for r in reg_rows:
        sid, name, year, body, sub, lang, gender, notes, raw, src = r
        vals.append(f"({sid}, '{name}', {year}, '{body}', '{sub}', '{lang}', '{gender}', '{notes}', '{raw}', '{src}')")
    cur.execute(f"INSERT INTO gaokao_assistant.dim_admission_regulation_parsed_v2 VALUES {', '.join(vals)}")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    run()
