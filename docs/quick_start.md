# 快速上手指南

---

## 一、从头开始（全新部署）

### 1. 安装依赖

```bash
pip install -r scripts/requirements.txt
```

### 2. 配置连接信息

```bash
cp .env.example .env
# 编辑 .env，填入以下变量：
# CZ_SERVICE=https://cn-shanghai-alicloud.api.clickzetta.com
# CZ_INSTANCE=你的实例ID
# CZ_WORKSPACE=你的工作空间
# CZ_USERNAME=你的用户名
# CZ_PASSWORD=你的密码
# CZ_VCLUSTER=default

export $(cat .env | xargs)
```

### 3. 采集数据（按顺序执行）

```bash
# 第一步：采集专业录取历史（主表，约 10-14 小时，支持断点续采）
python3 scripts/scraper.py

# 第二步：补全中断或失败的数据
python3 scripts/repair.py

# 第三步：采集高校维度信息（约 15 分钟）
python3 scripts/dim_school_scraper.py
```

采集完成后 Lakehouse 中会有 5 张表：
- `fact_admission_history`：专业录取历史（主表）
- `dim_school`：高校基本信息
- `dim_school_rank`：高校各榜单排名
- `dim_school_special`：高校专业评级
- `dim_university`：全国高校基础列表（含地理坐标）

---

## 二、连接数据库

### Python

```python
import os, clickzetta

conn = clickzetta.connect(
    service=os.environ['CZ_SERVICE'],
    instance=os.environ['CZ_INSTANCE'],
    workspace=os.environ['CZ_WORKSPACE'],
    username=os.environ['CZ_USERNAME'],
    password=os.environ['CZ_PASSWORD'],
    vcluster=os.environ.get('CZ_VCLUSTER', 'default'),
    schema='gaokao_assistant'
)
cur = conn.cursor()
cur.execute("SELECT COUNT(1) FROM gaokao_assistant.fact_admission_history")
print("总记录数：", cur.fetchone()[0])
conn.close()
```

### ClickZetta 控制台

登录控制台 → 选择对应实例和工作空间 → SQL 编辑器直接查询。

---

## 三、常用查询示例

> 常用 school_id：清华=140，北大=31，复旦=132，上交=125，浙大=114，西交=330，人大=46
> 常用 province_id：北京=11，上海=31，广东=44，浙江=33，四川=51，湖北=42

### 示例 1：查某高校在某省的历年最低录取分

```sql
-- 清华大学在广东历年最低录取分
SELECT year, spname, local_batch_name, min_score, min_rank
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 140
  AND province_id = '44'
  AND min_score > 0
ORDER BY year DESC, min_score DESC;
```

### 示例 2：按分数查可报学校和专业

```sql
-- 广东考生 620 分，查 2024 年普通类录取分在 610-630 的专业
SELECT s.name AS 学校, f.spname AS 专业, f.local_batch_name AS 批次,
       f.min_score AS 最低分, f.min_rank AS 最低位次
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
WHERE f.province_id = '44' AND f.year = 2024
  AND f.min_score BETWEEN 610 AND 630
  AND f.zslx_name = '普通类'
ORDER BY f.min_score DESC;
```

### 示例 3：某专业历年分数趋势

```sql
-- 北京大学计算机类专业在北京历年最低分
SELECT year, spname, min_score, min_rank, lq_num AS 录取人数
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 31
  AND province_id = '11'
  AND spname LIKE '%计算机%'
  AND min_score > 0
ORDER BY year ASC;
```

### 示例 4：985 院校在某省录取分对比

```sql
-- 985 高校 2024 年在浙江的最低录取分排名
SELECT s.name, s.ruanke_rank AS 软科排名,
       MIN(f.min_score) AS 最低分, MIN(f.min_rank) AS 最低位次
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
WHERE f.province_id = '33' AND f.year = 2024
  AND s.f985 = 1 AND f.min_score > 0
GROUP BY s.name, s.ruanke_rank
ORDER BY 最低分 DESC;
```

### 示例 5：新高考选科筛专业

```sql
-- 湖南考生选了物理，查 2024 年医学类可报专业
SELECT s.name AS 学校, f.spname AS 专业, f.sp_info AS 选科要求,
       f.min_score AS 最低分, f.min_rank AS 最低位次
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
WHERE f.province_id = '43' AND f.year = 2024
  AND f.level2_name LIKE '%医学%'
  AND (f.sp_info LIKE '%物理%' OR f.sp_info IS NULL)
  AND f.min_score > 0
ORDER BY f.min_score DESC;
```

### 示例 6：结合学科评估找性价比专业

```sql
-- 计算机专业学科评估 A+ 的院校，2024 年在全国各省录取分
SELECT s.name AS 学校, sp.xueke_rank_score AS 学科评估,
       f.province_id AS 省份, MIN(f.min_score) AS 最低分
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
JOIN gaokao_assistant.dim_school_special sp ON s.school_id = sp.school_id
WHERE sp.name LIKE '%计算机%' AND sp.xueke_rank_score = 'A+'
  AND f.year = 2024 AND f.min_score > 0
GROUP BY s.name, sp.xueke_rank_score, f.province_id
ORDER BY 最低分 DESC;
```

---

## 四、数据补全（repair.py）

**什么时候用**：scraper.py 中途中断、网络超时、或发现某些学校/省份/年份数据缺失时。

```bash
export $(cat .env | xargs)
python3 scripts/repair.py
```

repair.py 会自动：
1. 计算理论上应有的全部组合（学校 × 省份 × 年份）
2. 对比断点文件，找出未完成的组合
3. 重新采集缺失部分
4. 去重写入

---

## 五、数据质量检查

### 检查各年数据量是否正常

```sql
SELECT year, COUNT(*) AS 记录数,
       COUNT(DISTINCT school_id) AS 学校数,
       COUNT(DISTINCT province_id) AS 省份数,
       SUM(CASE WHEN min_score = 0 THEN 1 ELSE 0 END) AS 零分记录数
FROM gaokao_assistant.fact_admission_history
GROUP BY year
ORDER BY year;
```

### 检查某学校是否有漏采省份

```sql
-- 清华大学 2024 年覆盖了哪些省份（应有 27-30 个）
SELECT COUNT(DISTINCT province_id) AS 省份数,
       COUNT(*) AS 记录数
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 140 AND year = 2024;
```

### 检查重复数据

```sql
-- 检查是否有重复行（同一学校/省份/年份/专业/最低分）
SELECT school_id, province_id, year, special_id, spname, min_score,
       COUNT(*) AS cnt
FROM gaokao_assistant.fact_admission_history
GROUP BY school_id, province_id, year, special_id, spname, min_score
HAVING cnt > 1
LIMIT 20;
```

### 检查字段空值率

```sql
SELECT
    SUM(CASE WHEN min_score = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS 零分率,
    SUM(CASE WHEN min_rank = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS 零位次率,
    SUM(CASE WHEN sp_name IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS sp_name空值率,
    SUM(CASE WHEN lq_num IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS 录取人数空值率
FROM gaokao_assistant.fact_admission_history;
```

---

## 六、数据修复

### 删除重复数据

ClickZetta 不支持直接 DELETE + 子查询去重，需要重建表：

```sql
-- 1. 建临时表存去重后的数据
CREATE TABLE gaokao_assistant.fact_admission_history_dedup AS
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY school_id, province_id, year, special_id, spname, min_score
        ORDER BY school_id
    ) AS rn
    FROM gaokao_assistant.fact_admission_history
) t WHERE rn = 1;

-- 2. 确认行数后替换
-- DROP TABLE gaokao_assistant.fact_admission_history;
-- ALTER TABLE gaokao_assistant.fact_admission_history_dedup RENAME TO fact_admission_history;
```

### 补采特定学校/省份/年份

修改 scraper.py 的学校列表，或直接用 repair.py 的断点机制重跑。

---

## 七、常见问题

**Q：min_score = 0 是什么意思？**
A：数据缺失，原始 API 未返回分数。查询时加 `WHERE min_score > 0` 过滤。

**Q：为什么清华/北大在上海、湖北 2021 年后没有数据？**
A：这些省份实施新高考改革后，gaokao.cn 的静态 API 没有生成对应文件，是数据源本身的限制，不是采集问题。

**Q：min_rank（位次）为 0 是什么意思？**
A：老高考省份（文理分科）没有位次数据。只有新高考改革省份才有有效位次。

**Q：如何找某所学校的 school_id？**
A：查 dim_school 表：
```sql
SELECT school_id, name, province_name, ruanke_rank
FROM gaokao_assistant.dim_school
WHERE name LIKE '%武汉大学%';
```

**Q：2018/2019 年 sp_name 为什么是空的？**
A：API 历史数据限制，这两年没有返回 sp_name 字段。用 `spname` 字段替代，它在所有年份都有值。
