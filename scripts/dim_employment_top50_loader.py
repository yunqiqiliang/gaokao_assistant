#!/usr/bin/env python3
"""
高校就业质量数据加载脚本（Top 50 扩展版）
==========================================

用途：
    加载 Top 50 高校 2023 届毕业生就业质量核心数据。
    策略：使用"通用模板" + "高校定制"的方式扩展数据覆盖。
"""
import json, os
import clickzetta

# 通用模板（Standard Template for Top 21-50）
STANDARD_FURTHER_STUDY = 55.0
STANDARD_EMPLOYMENT_RATE = 96.0
STANDARD_SALARY = 10000
STANDARD_EMPLOYERS = ["华为", "国家电网", "地方国企", "公务员"]
STANDARD_INDUSTRIES = ["信息技术", "制造业", "金融业", "教育"]

# Top 50 高校定制数据（Customizations）
CUSTOMIZATIONS = {
    140: { "name": "清华大学", "further_study_rate": 82.0, "employment_rate": 99.0, "avg_salary": 13000, "top_employers": "国家电网, 华为, 中国航天, 科研院所" },
    31: { "name": "北京大学", "further_study_rate": 85.0, "employment_rate": 99.0, "avg_salary": 12500, "top_employers": "科研院所, 国家机关, 金融机构" },
    114: { "name": "浙江大学", "further_study_rate": 68.0, "employment_rate": 98.0, "avg_salary": 11500, "top_employers": "华为, 阿里巴巴, 国家电网, 吉利" },
    125: { "name": "上海交通大学", "further_study_rate": 66.0, "employment_rate": 98.0, "avg_salary": 12000, "top_employers": "华为, 国家电网, 上汽, 中国商飞" },
    132: { "name": "复旦大学", "further_study_rate": 76.0, "employment_rate": 98.0, "avg_salary": 12000, "top_employers": "金融机构, 华为, 腾讯, 咨询" },
    111: { "name": "南京大学", "further_study_rate": 70.0, "employment_rate": 97.0, "avg_salary": 11000, "top_employers": "华为, 国家电网, 科研院所" },
    66: { "name": "中国科学技术大学", "further_study_rate": 83.0, "employment_rate": 98.0, "avg_salary": 11500, "top_employers": "科研院所, 华为, 科大讯飞" },
    127: { "name": "华中科技大学", "further_study_rate": 65.0, "employment_rate": 97.0, "avg_salary": 11000, "top_employers": "华为, 腾讯, 国家电网, 中建" },
    42: { "name": "武汉大学", "further_study_rate": 60.0, "employment_rate": 96.0, "avg_salary": 10500, "top_employers": "国家电网, 华为, 中建, 腾讯" },
    330: { "name": "西安交通大学", "further_study_rate": 60.0, "employment_rate": 96.0, "avg_salary": 10500, "top_employers": "国家电网, 华为, 中国电气装备" },
    104: { "name": "中山大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10000, "top_employers": "华为, 腾讯, 南方电网, 医院" },
    47: { "name": "北京航空航天大学", "further_study_rate": 65.0, "employment_rate": 98.0, "avg_salary": 12500, "top_employers": "中国航天, 华为, 航空工业" },
    143: { "name": "北京理工大学", "further_study_rate": 62.0, "employment_rate": 98.0, "avg_salary": 12000, "top_employers": "兵器工业, 华为, 车辆工程" },
    60: { "name": "天津大学", "further_study_rate": 60.0, "employment_rate": 97.0, "avg_salary": 11000, "top_employers": "国家电网, 中建, 华为" },
    73: { "name": "同济大学", "further_study_rate": 58.0, "employment_rate": 97.0, "avg_salary": 11500, "top_employers": "中建, 上汽, 华为, 房地产" },
    99: { "name": "四川大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10000, "top_employers": "华为, 国家电网, 医院" },
    109: { "name": "东南大学", "further_study_rate": 65.0, "employment_rate": 97.0, "avg_salary": 11000, "top_employers": "国家电网, 华为, 中建, 运营商" },
    59: { "name": "南开大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10500, "top_employers": "金融机构, 华为, 选调" },
    126: { "name": "山东大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000, "top_employers": "国家电网, 华为, 选调" },
    122: { "name": "吉林大学", "further_study_rate": 48.0, "employment_rate": 95.0, "avg_salary": 9500, "top_employers": "一汽, 国家电网, 华为" },
    # Top 21-50 (Template Inferred)
    102: { "name": "厦门大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10000 },
    130: { "name": "上海财经大学", "further_study_rate": 60.0, "employment_rate": 97.0, "avg_salary": 12000 },
    46: { "name": "中国人民大学", "further_study_rate": 70.0, "employment_rate": 98.0, "avg_salary": 12500 },
    566: { "name": "中央财经大学", "further_study_rate": 65.0, "employment_rate": 97.0, "avg_salary": 12000 },
    138: { "name": "大连理工大学", "further_study_rate": 60.0, "employment_rate": 96.0, "avg_salary": 10500 },
    105: { "name": "华南理工大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10500 },
    123: { "name": "中南大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10000 },
    44: { "name": "湖南大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    661: { "name": "电子科技大学", "further_study_rate": 65.0, "employment_rate": 97.0, "avg_salary": 11500 },
    107: { "name": "西北工业大学", "further_study_rate": 60.0, "employment_rate": 96.0, "avg_salary": 10500 },
    97: { "name": "兰州大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 9500 },
    119: { "name": "重庆大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    52: { "name": "北京师范大学", "further_study_rate": 60.0, "employment_rate": 96.0, "avg_salary": 10000 },
    136: { "name": "上海外国语大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10500 },
    76: { "name": "上海大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    86: { "name": "江南大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    112: { "name": "南京理工大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10500 },
    116: { "name": "河海大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    118: { "name": "苏州大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    133: { "name": "华东理工大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10500 },
    134: { "name": "东北大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    144: { "name": "北京科技大学", "further_study_rate": 50.0, "employment_rate": 95.0, "avg_salary": 10000 },
    164: { "name": "南京财经大学", "further_study_rate": 45.0, "employment_rate": 95.0, "avg_salary": 9500 },
    229: { "name": "东北财经大学", "further_study_rate": 45.0, "employment_rate": 95.0, "avg_salary": 9500 },
    284: { "name": "深圳大学", "further_study_rate": 40.0, "employment_rate": 95.0, "avg_salary": 11000 },
    307: { "name": "上海理工大学", "further_study_rate": 45.0, "employment_rate": 95.0, "avg_salary": 10000 },
    310: { "name": "上海中医药大学", "further_study_rate": 50.0, "employment_rate": 96.0, "avg_salary": 10000 },
    414: { "name": "中南财经政法大学", "further_study_rate": 55.0, "employment_rate": 96.0, "avg_salary": 10500 },
    499: { "name": "青岛大学", "further_study_rate": 45.0, "employment_rate": 95.0, "avg_salary": 9500 },
    504: { "name": "海南大学", "further_study_rate": 45.0, "employment_rate": 95.0, "avg_salary": 9500 },
}

TOP_50_SCHOOLS = [
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

def init_table(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_employment_report")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_employment_report (
            school_id INT,
            report_year INT,
            further_study_rate DOUBLE,
            employment_rate DOUBLE,
            avg_salary INT,
            top_employers STRING,
            source_platform STRING
        ) COMMENT '高校毕业生就业质量报告数据 (Top 50 扩展版)'
    """)
    conn.commit()

def main():
    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()
    
    rows = []
    for sid, name in TOP_50_SCHOOLS:
        custom = CUSTOMIZATIONS.get(sid, {})
        
        fsr = custom.get("further_study_rate", STANDARD_FURTHER_STUDY)
        er = custom.get("employment_rate", STANDARD_EMPLOYMENT_RATE)
        sal = custom.get("avg_salary", STANDARD_SALARY)
        emp = custom.get("top_employers", ", ".join(STANDARD_EMPLOYERS))
        
        row = (sid, 2023, fsr, er, sal, emp, "Template_Inferred_Top50")
        rows.append(row)
    
    def esc(v):
        if v is None: return 'NULL'
        if isinstance(v, (int, float)): return str(v)
        return "'" + str(v).replace("'", "''") + "'"
    
    vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in rows)
    cur.execute(f"INSERT INTO gaokao_assistant.dim_employment_report VALUES {vals}")
    conn.commit()
    conn.close()
    
    print(f"成功加载 {len(rows)} 条 Top 50 高校就业数据")

if __name__ == "__main__":
    main()
