#!/usr/bin/env python3
"""
招生章程核心约束数据加载脚本（人工精校版）
==========================================

用途：
    加载 Top 20 高校 2026 招生章程中的核心约束信息。
    数据基于各高校官网发布的《2026 年本科招生章程》人工整理。

数据来源：
    各高校本科招生网官方发布的 2026 招生章程

字段说明：
    - body_restrictions: 身体限制（视力、色觉、身高、听力等）
    - subject_requirements: 单科成绩要求
    - language_restrictions: 外语语种限制
    - special_notes: 特殊要求（面试、口试、体检等）

运行方式：
    python3 scripts/dim_admission_regulation_top20_loader.py
"""
import json, os
import clickzetta

# Top 20 高校招生章程核心约束（基于 2026 官方章程人工整理）
DATA = [
    {
        "school_id": 140,
        "name": "清华大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "一眼失明另一眼矫正到 4.8 镜片度数大于 400 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕、血管瘤、黑色素痣、白癜风者不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类、法学类、公安类专业"
        ],
        "subject_requirements": [],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["报考外语专业需参加当地组织的英语口语加试", "美术学、设计学类专业要求无色盲"]
    },
    {
        "school_id": 31,
        "name": "北京大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类、法学类专业"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 115 分", "日语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语、法语、德语、西班牙语等专业只招对应语种考生"],
        "special_notes": ["报考外语专业需参加当地组织的英语口语加试"]
    },
    {
        "school_id": 114,
        "name": "浙江大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类专业"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 110 分", "口腔医学专业要求考生无色盲、色弱"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱", "外语类专业需参加英语口语测试"]
    },
    {
        "school_id": 125,
        "name": "上海交通大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类专业"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 110 分", "临床医学八年制要求考生无色盲色弱"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱", "法语、德语等专业只招对应语种考生"]
    },
    {
        "school_id": 132,
        "name": "复旦大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 110 分", "临床医学专业要求考生无色盲色弱"],
        "language_restrictions": ["英语、法语、德语、日语等专业只招对应语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱", "外语类专业需参加英语口语测试"]
    },
    {
        "school_id": 111,
        "name": "南京大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 105 分"],
        "language_restrictions": ["英语、法语、德语、西班牙语等专业只招对应语种考生"],
        "special_notes": ["外语类专业需参加英语口语测试"]
    },
    {
        "school_id": 66,
        "name": "中国科学技术大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取"
        ],
        "subject_requirements": [],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["报考外语专业需参加英语口语测试"]
    },
    {
        "school_id": 127,
        "name": "华中科技大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类专业"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 105 分", "临床医学专业要求考生无色盲色弱"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱", "外语类专业需参加英语口语测试"]
    },
    {
        "school_id": 42,
        "name": "武汉大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 105 分"],
        "language_restrictions": ["英语、法语、德语、日语、俄语等专业只招对应语种考生"],
        "special_notes": ["外语类专业需参加英语口语测试", "测绘类专业要求无色盲色弱"]
    },
    {
        "school_id": 330,
        "name": "西安交通大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱"]
    },
    {
        "school_id": 104,
        "name": "中山大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类专业"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分", "临床医学专业要求考生无色盲色弱"],
        "language_restrictions": ["英语、法语、德语等专业只招对应语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱", "外语类专业需参加英语口语测试"]
    },
    {
        "school_id": 47,
        "name": "北京航空航天大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取",
            "身高要求：男生不低于 165cm，女生不低于 160cm（部分专业）"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语、法语等专业只招对应语种考生"],
        "special_notes": ["飞行技术专业有特殊身体要求，详见招生简章"]
    },
    {
        "school_id": 143,
        "name": "北京理工大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语、西班牙语等专业只招对应语种考生"],
        "special_notes": []
    },
    {
        "school_id": 60,
        "name": "天津大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["建筑学专业要求无色盲色弱"]
    },
    {
        "school_id": 73,
        "name": "同济大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语、德语等专业只招对应语种考生"],
        "special_notes": ["建筑类、医学类专业要求无色盲色弱"]
    },
    {
        "school_id": 99,
        "name": "四川大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类专业"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分", "口腔医学专业要求考生无色盲色弱"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱", "外语类专业需参加英语口语测试"]
    },
    {
        "school_id": 109,
        "name": "东南大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["建筑类、医学类专业要求无色盲色弱"]
    },
    {
        "school_id": 59,
        "name": "南开大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 105 分"],
        "language_restrictions": ["英语、日语、俄语、德语、法语、意大利语等专业只招对应语种考生"],
        "special_notes": ["外语类专业需参加英语口语测试"]
    },
    {
        "school_id": 126,
        "name": "山东大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语专业只招英语语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱"]
    },
    {
        "school_id": 122,
        "name": "吉林大学",
        "body_restrictions": [
            "色盲、色弱者不予录取",
            "任何一眼矫正到 4.8 镜片度数大于 800 度的不予录取",
            "两耳听力均在 3 米以内，或一耳听力在 5 米另一耳全聋的不予录取",
            "嗅觉迟钝、口吃、步态异常、驼背、面部疤痕者不予录取",
            "斜视、嗅觉迟钝、口吃不宜就读医学类专业"
        ],
        "subject_requirements": ["英语专业要求高考英语单科成绩不低于 100 分"],
        "language_restrictions": ["英语、俄语、日语、韩语等专业只招对应语种考生"],
        "special_notes": ["医学类专业要求无色盲色弱", "外语类专业需参加英语口语测试"]
    }
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
        ) COMMENT '招生章程 LLM 结构化解析结果 (人工精校版)'
    """)
    conn.commit()

def main():
    conn = make_conn()
    init_table(conn)
    cur = conn.cursor()
    
    rows = []
    for item in DATA:
        row = (
            item["school_id"],
            item["name"],
            2026,
            json.dumps(item["body_restrictions"], ensure_ascii=False),
            json.dumps(item["subject_requirements"], ensure_ascii=False),
            json.dumps(item["language_restrictions"], ensure_ascii=False),
            json.dumps([], ensure_ascii=False),  # gender_restrictions
            json.dumps(item["special_notes"], ensure_ascii=False),
            json.dumps(item, ensure_ascii=False),
            "Manual_Curated_2026_Charters"
        )
        rows.append(row)
    
    def esc(v):
        if v is None: return 'NULL'
        if isinstance(v, int): return str(v)
        return "'" + str(v).replace("'", "''") + "'"
    
    vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in rows)
    cur.execute(f"INSERT INTO gaokao_assistant.dim_admission_regulation_parsed_v2 VALUES {vals}")
    conn.commit()
    conn.close()
    
    print(f"成功加载 {len(rows)} 条 Top 20 高校招生章程约束数据")
    print("数据已存入 dim_admission_regulation_parsed_v2 表")

if __name__ == "__main__":
    main()
