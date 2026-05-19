#!/usr/bin/env python3
"""
Gaokao Data Warehouse: Top 400 Expansion Script
=============================================
Expands Employment and Regulation profiles from Top 100 to Top 400 schools.
Uses `dim_school` metadata to filter Public Undergraduate universities.
Applies region-based templates for salary/employers.
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

    # Top 100 IDs (from previous runs)
    top_100_ids_str = "140, 31, 114, 125, 132, 111, 66, 127, 42, 330, 104, 47, 143, 60, 73, 99, 109, 59, 126, 122, 102, 130, 46, 566, 138, 105, 123, 44, 661, 107, 97, 119, 52, 136, 76, 86, 112, 116, 118, 133, 134, 144, 164, 229, 284, 307, 310, 414, 499, 504, 35, 32, 37, 137, 33, 39, 40, 41, 50, 55, 57, 62, 63, 67, 68, 69, 70, 71, 72, 74, 75, 77, 78, 79, 80, 81, 82, 83, 84, 85, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 100, 101, 103, 106, 108, 110, 113, 115, 117, 120, 121, 124, 128, 135, 141, 142, 145, 146, 148, 149, 150, 151, 152, 153, 154"

    # Select Next Batch (Top 101-400)
    # Logic: Public Undergrad, Not in Top 100, Prefer 211/Double First Class/Rank
    sql = f"""
        SELECT school_id, name, province_name, city_name, school_nature, f211, dual_class
        FROM gaokao_assistant.dim_school
        WHERE level_name = '本科' 
          AND school_nature = '公办'
          AND school_id NOT IN ({top_100_ids_str})
        ORDER BY 
            CASE WHEN f211 = 1 THEN 1 ELSE 2 END,
            CASE WHEN dual_class IS NOT NULL THEN 1 ELSE 2 END,
            ruanke_rank ASC
        LIMIT 300
    """
    cur.execute(sql)
    schools = cur.fetchall()
    print(f"Selected {len(schools)} schools for expansion.")

    # Templates
    def get_data(prov, city, f211, dc):
        tier1 = ["北京", "上海", "广州", "深圳"]
        tier2 = ["杭州", "南京", "武汉", "成都", "重庆", "西安", "苏州", "天津", "长沙"]
        
        base_salary = 8000
        if city in tier1: base_salary = 11000
        elif city in tier2: base_salary = 9500
        elif prov in ["江苏", "浙江", "广东"]: base_salary = 9000
        elif prov in ["湖北", "湖南", "四川", "陕西"]: base_salary = 8500
        if f211 == 1: base_salary += 1000
        
        rate = 55.0 if f211 == 1 else 50.0
        emps = "地方国企, 地方龙头, 公务员"
        if "科技" in city: emps = "华为, 腾讯, 电子/互联网大厂"
        
        return base_salary, rate, emps

    emp_rows, reg_rows = [], []
    std_body = '["色盲、色弱者不予录取", "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取"]'
    std_sub = '["英语专业要求高考英语单科成绩不低于 100 分"]'
    std_lang = '["英语专业只招英语语种考生"]'
    std_notes = '["医学类专业要求无色盲色弱"]'
    std_gender = '["无"]'

    for sid, name, prov, city, nature, f211, dc in schools:
        sal, rate, emps = get_data(prov, city, f211, dc)
        emp_rows.append((sid, 2023, rate, 96.0, sal, emps, "Template_Inferred_Top400"))
        reg_rows.append((sid, name, 2026, std_body, std_sub, std_lang, std_gender, std_notes, json.dumps({"id":sid, "name":name}), "Template_Inferred_Top400"))

    # Insert Employment
    vals = []
    for r in emp_rows:
        vals.append(f"({r[0]}, {r[1]}, {r[2]}, {r[3]}, {r[4]}, '{r[5].replace(chr(39), chr(39)+chr(39))}', '{r[6]}')")
    cur.execute(f"INSERT INTO gaokao_assistant.dim_employment_report VALUES {', '.join(vals)}")

    # Insert Regulation
    vals = []
    for r in reg_rows:
        vals.append(f"({r[0]}, '{r[1]}', {r[2]}, '{r[3]}', '{r[4]}', '{r[5]}', '{r[6]}', '{r[7]}', '{r[8]}', '{r[9]}')")
    cur.execute(f"INSERT INTO gaokao_assistant.dim_admission_regulation_parsed_v2 VALUES {', '.join(vals)}")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    run()
