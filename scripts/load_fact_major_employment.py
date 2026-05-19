#!/usr/bin/env python3
\"\"\"
Gaokao Data Warehouse: Fact Major Employment Loader
=============================================
Generates major-specific salary and employment data.
Model: School Base Salary * Industry Coefficient.
Usage: python3 scripts/load_fact_major_employment.py
\"\"\"
import os
import clickzetta

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_DIR, ".env")

def load_env():
    with open(ENV_PATH) as f:
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

    # 1. Create Table
    print("Creating table fact_major_employment...")
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.fact_major_employment")
    cur.execute(\"\"\"
        CREATE TABLE gaokao_assistant.fact_major_employment (
            school_id INT,
            major_name STRING,
            category_name STRING,
            avg_salary INT,
            employment_rate DOUBLE,
            source_platform STRING,
            PRIMARY KEY (school_id, major_name)
        ) COMMENT '高校分专业就业质量数据（预估模型）'
    \"\"\")

    # 2. Fetch Data
    cur.execute("SELECT school_id, avg_salary, further_study_rate FROM gaokao_assistant.dim_employment_report")
    schools = cur.fetchall()
    cur.execute("SELECT major_name, category_name FROM gaokao_assistant.dim_major_category")
    majors = cur.fetchall()

    # Coefficients (Salary Mult, Employment Rate Delta)
    coeffs = {
        '计算机类': (1.35, 0.00), '电子信息类': (1.30, 0.00), '临床医学类': (1.20, 0.00),
        '电气类': (1.25, 0.00), '土木类': (0.70, -0.08), '建筑类': (0.80, -0.06)
        # ... (Full list in actual code)
    }
    default_coeff = (1.00, -0.02)

    # Insert logic here ...
    print("Done.")
    conn.close()

if __name__ == "__main__":
    run()
