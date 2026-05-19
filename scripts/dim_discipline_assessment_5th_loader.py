#!/usr/bin/env python3
"""
第五轮学科评估数据加载脚本
===========================

背景：
    教育部第五轮学科评估（2022年）结果各校只收到自己的，未统一公布。
    本脚本用于加载从多源汇总整理后的第五轮学科评估数据。

数据准备：
    将汇总好的数据保存为 CSV 文件：/tmp/discipline_assessment_5th.csv
    格式：school_id,discipline_name,assessment_level,confidence,source
    示例：
        140,计算机科学与技术,A+,confirmed,清华大学官网新闻
        31,数学,A,confirmed,北京大学研究生院

    confidence 取值：
        - confirmed: 从学校官网/教育部公示直接确认
        - estimated: 从多源交叉验证估算（置信度较低）

运行方式：
    python3 dim_discipline_assessment_5th_loader.py

注意：
    - 此脚本是数据加载器，不是爬虫
    - 数据需要人工从多源（各校官网新闻、媒体报道、民间整理）汇总
    - 可以多次运行，脚本会先清空表再重新加载
"""
import csv, time, os
import clickzetta


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
    cur.execute("DROP TABLE IF EXISTS gaokao_assistant.dim_discipline_assessment_5th")
    cur.execute("""
        CREATE TABLE gaokao_assistant.dim_discipline_assessment_5th (
            school_id           INT     COMMENT '高校ID，关联 dim_school.school_id',
            discipline_name     STRING  COMMENT '学科名称（如计算机科学与技术、数学）',
            assessment_level    STRING  COMMENT '评估等级：A+/A/A-/B+/B/B-/C+/C/C-',
            confidence          STRING  COMMENT '置信度：confirmed（已确认）/estimated（估算）',
            source              STRING  COMMENT '数据来源（学校官网/新闻报道/民间整理等）'
        ) COMMENT '第五轮学科评估（2022年）结果。因教育部未统一公布，数据来自多源汇总。confidence字段标识数据可靠性'
    """)
    conn.commit()
    print("dim_discipline_assessment_5th 表已创建")


def load_csv(conn, csv_path):
    cur = conn.cursor()
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                school_id = int(row['school_id'].strip())
                discipline = row.get('discipline_name', '').strip()
                level = row.get('assessment_level', '').strip()
                confidence = row.get('confidence', 'estimated').strip()
                source = row.get('source', '').strip()
                if school_id and discipline and level:
                    rows.append((school_id, discipline, level, confidence or 'estimated', source))
            except Exception as e:
                print(f"  跳过无效行: {row} -- {e}")

    if not rows:
        print("CSV 文件为空或格式不正确")
        return 0

    # 批量写入
    def esc(v):
        if v is None:
            return 'NULL'
        if isinstance(v, int):
            return str(v)
        return "'" + str(v).replace("'", "''") + "'"

    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        vals = ', '.join('(' + ', '.join(esc(c) for c in row) + ')' for row in batch)
        cur.execute(f"INSERT INTO gaokao_assistant.dim_discipline_assessment_5th VALUES {vals}")

    conn.commit()
    return len(rows)


def update_comment(total):
    conn = make_conn()
    cur = conn.cursor()
    comment = (
        f"第五轮学科评估（2022年）结果，当前 {total:,} 条。"
        f"因教育部未统一公布完整结果，数据来自多源汇总。"
        f"confidence字段：confirmed=已确认，estimated=估算。"
        f"数据持续更新中。"
    )
    safe = comment.replace("'", "''")
    cur.execute(f"ALTER TABLE gaokao_assistant.dim_discipline_assessment_5th SET COMMENT '{safe}'")
    conn.commit()
    conn.close()


def main():
    csv_path = '/tmp/discipline_assessment_5th.csv'

    if not os.path.exists(csv_path):
        print(f"数据文件不存在: {csv_path}")
        print("\n请先准备 CSV 文件，格式：")
        print("  school_id,discipline_name,assessment_level,confidence,source")
        print("\n示例：")
        print("  140,计算机科学与技术,A+,confirmed,清华大学官网新闻")
        print("  31,数学,A,confirmed,北京大学研究生院")
        return

    print(f"加载数据: {csv_path}")
    conn = make_conn()
    init_table(conn)
    total = load_csv(conn, csv_path)
    conn.close()

    if total > 0:
        update_comment(total)
        print(f"\n完成！加载 {total:,} 条第五轮学科评估记录")
    else:
        print("未加载任何数据")


if __name__ == "__main__":
    main()
