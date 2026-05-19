#!/usr/bin/env python3
"""
Gaokao Data Warehouse: Top 50 Quality Restoration Script
=============================================
Restores high-quality employment data for the Top 50 schools.
This script is used to fix issues where Top 1000 generic templates
overwrote the carefully curated Top 50 data.
Run this AFTER running dim_top1000_expansion.py to ensure high-priority data is accurate.
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

    # High Quality Data Map (Top 50 curated data)
    # Format: school_id -> (further_study_rate, avg_salary, top_employers)
    top_50_data = {
        140: (82.0, 13000, "国家电网, 华为, 中国航天, 科研院所"),
        31: (85.0, 12500, "科研院所, 国家机关, 金融机构"),
        114: (68.0, 11500, "华为, 阿里巴巴, 国家电网, 吉利"),
        125: (66.0, 12000, "华为, 国家电网, 上汽, 中国商飞"),
        132: (76.0, 12000, "金融机构, 华为, 腾讯, 咨询"),
        111: (70.0, 11000, "华为, 国家电网, 科研院所"),
        66: (83.0, 11500, "科研院所, 华为, 科大讯飞"),
        127: (65.0, 11000, "华为, 腾讯, 国家电网, 中建"),
        42: (60.0, 10500, "国家电网, 华为, 中建, 腾讯"),
        330: (60.0, 10500, "国家电网, 华为, 中国电气装备"),
        104: (55.0, 10000, "华为, 腾讯, 南方电网, 医院"),
        47: (65.0, 12500, "中国航天, 华为, 航空工业"),
        143: (62.0, 12000, "兵器工业, 华为, 车辆工程"),
        60: (60.0, 11000, "国家电网, 中建, 华为"),
        73: (58.0, 11500, "中建, 上汽, 华为, 房地产"),
        99: (55.0, 10000, "华为, 国家电网, 医院"),
        109: (65.0, 11000, "国家电网, 华为, 中建, 运营商"),
        59: (55.0, 10500, "金融机构, 华为, 选调"),
        126: (50.0, 10000, "国家电网, 华为, 选调"),
        122: (48.0, 9500, "一汽, 国家电网, 华为"),
        284: (40.0, 11000, "华为, 腾讯, 大疆, 平安"),
        105: (55.0, 10500, "华为, 广汽, 南方电网"),
        661: (65.0, 11500, "华为, 中兴, 研究所"),
        52: (60.0, 10000, "教育系统, 华为, 选调"),
        32: (55.0, 13500, "中国移动, 华为, 腾讯, 运营商"),
        35: (62.0, 11500, "航天科技, 华为, 中建"),
        37: (50.0, 12000, "华为, 中兴, 研究所"),
        130: (60.0, 12000, "银行, 四大, 证券公司"),
        46: (70.0, 12500, "国家机关, 银行, 券商"),
        566: (65.0, 12000, "银行, 四大, 部委"),
        144: (50.0, 10000, "宝武钢铁, 华为, 研究所"),
        136: (55.0, 10500, "外交部, 外企, 媒体"),
    }

    print(f"Restoring {len(top_50_data)} high-quality records...")
    
    ops = []
    for sid, (rate, sal, emp) in top_50_data.items():
        # Delete existing to handle duplicates/overwrites
        ops.append(f"DELETE FROM gaokao_assistant.dim_employment_report WHERE school_id = {sid}")
        
        # Insert high quality
        emp_esc = emp.replace("'", "''")
        ops.append(f"""
            INSERT INTO gaokao_assistant.dim_employment_report 
            VALUES ({sid}, 2023, {rate}, 96.0, {sal}, '{emp_esc}', 'Restored_HighQuality_v2')
        """)

    try:
        for op in ops:
            cur.execute(op)
        conn.commit()
        print("✅ Restoration complete.")
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    
    conn.close()

if __name__ == "__main__":
    run()
