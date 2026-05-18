# 快速上手指南

本指南面向非技术人员，帮助你快速连接数据库并查询高考录取历史数据。

---

## 第一步：连接 ClickZetta Lakehouse

### 方式一：使用 Python 脚本查询（推荐）

安装依赖：

```bash
pip install clickzetta-connector
```

连接并查询：

```python
import clickzetta

# 建立连接
conn = clickzetta.connect(
    service='https://cn-shanghai-alicloud.api.clickzetta.com',
    instance='f8866243',
    workspace='quick_start',
    username='你的用户名',
    password='你的密码',
    vcluster='default',
    schema='gaokao_assistant'
)

cur = conn.cursor()

# 执行查询
cur.execute("SELECT COUNT(1) FROM gaokao_assistant.fact_admission_history")
print("总记录数：", cur.fetchone()[0])

conn.close()
```

### 方式二：使用 ClickZetta 控制台

1. 登录 ClickZetta 控制台
2. 选择实例 `f8866243`，工作空间 `quick_start`
3. 在 SQL 编辑器中直接输入查询语句

---

## 第二步：常用查询示例

### 示例 1：查询某高校在某省的历年最低录取分数

**场景**：想了解中国人民大学（school_id=10002）在广东（province_id='44'）历年的最低录取分数变化。

```sql
SELECT
    year AS 年份,
    spname AS 专业名称,
    local_batch_name AS 批次,
    min_score AS 最低分,
    min_rank AS 最低位次
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 10002
  AND province_id = '44'
  AND min_score > 0
ORDER BY year DESC, min_score DESC;
```

**说明**：`min_score > 0` 用于过滤数据缺失的记录（缺失时存储为 0）。

---

### 示例 2：查询某专业在全国各省的录取分数（最新年份）

**场景**：想了解"计算机科学与技术"专业 2024 年在各省的录取情况。

```sql
SELECT
    province_id AS 省份代码,
    school_id AS 学校ID,
    spname AS 专业名称,
    min_score AS 最低分,
    min_rank AS 最低位次,
    local_batch_name AS 批次
FROM gaokao_assistant.fact_admission_history
WHERE year = 2024
  AND spname LIKE '%计算机科学与技术%'
  AND min_score > 0
ORDER BY province_id, min_score DESC;
```

**说明**：`LIKE '%计算机科学与技术%'` 支持模糊匹配，可以找到名称略有差异的专业。

---

### 示例 3：查询某分数段内可报考的高校和专业

**场景**：广东考生，2024 年理科 620 分，想看哪些学校的哪些专业历史最低分在 610–630 分之间。

```sql
SELECT
    school_id AS 学校ID,
    spname AS 专业名称,
    local_batch_name AS 批次,
    min_score AS 最低分,
    min_rank AS 最低位次,
    level1_name AS 学科门类
FROM gaokao_assistant.fact_admission_history
WHERE province_id = '44'
  AND year = 2024
  AND min_score BETWEEN 610 AND 630
  AND zslx_name = '普通类'
ORDER BY min_score DESC;
```

**说明**：`BETWEEN 610 AND 630` 查询分数区间，`zslx_name = '普通类'` 排除艺术、体育等特殊类型。

---

### 示例 4：分析某高校某专业的历年分数线趋势

**场景**：想看清华大学（school_id=10003）软件工程专业在北京（province_id='11'）的历年分数变化。

```sql
SELECT
    year AS 年份,
    spname AS 专业名称,
    min_score AS 最低分,
    average_score AS 平均分,
    max_score AS 最高分,
    lq_num AS 录取人数
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 10003
  AND province_id = '11'
  AND spname LIKE '%软件工程%'
  AND min_score > 0
ORDER BY year ASC;
```

**说明**：通过历年数据对比，可以判断该专业分数线是否逐年上涨。

---

### 示例 5：按选科要求筛选专业（新高考省份）

**场景**：浙江（province_id='33'）考生，首选物理，想查 2024 年可报考的医学类专业。

```sql
SELECT
    school_id AS 学校ID,
    spname AS 专业名称,
    sg_xuanke AS 选科要求,
    min_score AS 最低分,
    min_rank AS 最低位次,
    local_batch_name AS 批次
FROM gaokao_assistant.fact_admission_history
WHERE province_id = '33'
  AND year = 2024
  AND level1_name = '医学'
  AND (sg_xuanke LIKE '%化学%' OR sg_xuanke = '' OR sg_xuanke IS NULL)
  AND min_score > 0
ORDER BY min_score DESC;
```

**说明**：新高考省份需要关注 `sg_xuanke`（选科要求）和 `first_km`（首选科目）字段。

---

## 常见问题

**Q：查询结果中 min_score 为 0 是什么意思？**

A：表示该条记录的分数数据缺失，原始 API 未返回分数信息。查询时加上 `WHERE min_score > 0` 可以过滤掉这些记录。

**Q：min_rank（位次）为 0 是什么意思？**

A：老高考省份（文理分科）没有位次数据，此字段为 0。只有实施新高考改革的省份才有有效位次数据。

**Q：为什么同一所学校同一年份有很多条记录？**

A：一所学校在一个省份通常招收多个专业，每个专业对应一条记录。部分高校还按专业组招生，同一专业组内有多个专业。

**Q：如何找到某所学校的 school_id？**

A：可以先用学校名称模糊查询：
```sql
SELECT DISTINCT school_id, year
FROM gaokao_assistant.fact_admission_history
WHERE spname LIKE '%北京大学%'
LIMIT 10;
```
注意：spname 是专业名称，不含学校名。建议通过 gaokao.cn 网站查找学校 ID，或联系数据维护者获取学校 ID 对照表。

**Q：数据更新到哪一年？**

A：目前覆盖 2018–2024 年，2025 年数据待高考录取结束后更新。

**Q：数据准确吗？可以直接用于志愿填报吗？**

A：数据来源于 gaokao.cn 公开接口，仅供参考。志愿填报是重要决策，建议结合官方招生简章、学校官网及专业老师的建议综合判断。
