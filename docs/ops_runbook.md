# 运维手册（Ops Runbook）

本文档覆盖数据库的完整生命周期操作：从头建库、日常采集、断点续采、数据补全、质量检查、问题修复。

---

## 一、环境准备

### 依赖安装

```bash
pip install -r scripts/requirements.txt
```

### 连接配置

```bash
cp .env.example .env
# 编辑 .env 填入真实值
export $(cat .env | xargs)
```

### 验证连接

```python
import os, clickzetta
conn = clickzetta.connect(
    service=os.environ['CZ_SERVICE'], instance=os.environ['CZ_INSTANCE'],
    workspace=os.environ['CZ_WORKSPACE'], username=os.environ['CZ_USERNAME'],
    password=os.environ['CZ_PASSWORD'], vcluster=os.environ.get('CZ_VCLUSTER','default'),
    schema='gaokao_assistant'
)
conn.cursor().execute("SELECT 1")
print("连接成功")
conn.close()
```

---

## 二、从头建库（全新部署）

按以下顺序执行，每步完成后再执行下一步。

### 步骤 1：采集专业录取历史（主表）

```bash
python3 scripts/scraper.py
```

- 耗时：约 10-14 小时（全量 2784 所）
- 断点文件：`/tmp/gaokao_done_keys.txt`（格式 `school_id|province_id|year`）
- 失败记录：`/tmp/gaokao_still_missing.txt`
- 中途中断可直接重跑，自动跳过已完成的组合

### 步骤 2：数据补全

```bash
python3 scripts/repair.py
```

- 计算理论组合集，找出断点文件中缺失的部分，重新采集
- 建议在 scraper.py 完成后运行一次

### 步骤 3：采集高校维度信息

```bash
python3 scripts/dim_school_scraper.py
```

- 耗时：约 15 分钟（2784 所）
- 会 DROP + CREATE 三张维度表，建表语句已内置完整注释

---

## 三、断点续采

scraper.py 内置断点机制，中断后直接重跑即可：

```bash
python3 scripts/scraper.py
# 输出示例：
# 断点: 已完成 94,340 个组合，继续采集
# 待处理任务: 508,746 个，启动 16 线程
```

**断点文件位置**：`/tmp/gaokao_done_keys.txt`

> 注意：断点文件在 `/tmp` 目录，重启机器后会丢失。如需持久化，手动备份：
> ```bash
> cp /tmp/gaokao_done_keys.txt ~/gaokao_done_keys_backup.txt
> ```

---

## 四、数据质量检查

### 4.1 整体规模检查

```sql
-- 各年记录数和学校覆盖
SELECT year,
       COUNT(*) AS 记录数,
       COUNT(DISTINCT school_id) AS 学校数,
       COUNT(DISTINCT province_id) AS 省份数
FROM gaokao_assistant.fact_admission_history
GROUP BY year ORDER BY year;
```

预期：2018-2020 年每年约 20-30 万条，2021 年后因新高考专业组拆分逐年增加。

### 4.2 分数有效性检查

```sql
SELECT year,
       COUNT(*) AS 总记录,
       SUM(CASE WHEN min_score > 0 THEN 1 ELSE 0 END) AS 有效分数,
       ROUND(SUM(CASE WHEN min_score > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS 有效率
FROM gaokao_assistant.fact_admission_history
GROUP BY year ORDER BY year;
```

预期：2020 年后有效率应 > 95%，2022 年因新高考过渡期略低。

### 4.3 重复数据检查

```sql
SELECT COUNT(*) AS 重复行数 FROM (
    SELECT school_id, province_id, year, special_id, spname, min_score,
           COUNT(*) AS cnt
    FROM gaokao_assistant.fact_admission_history
    GROUP BY school_id, province_id, year, special_id, spname, min_score
    HAVING cnt > 1
) t;
```

预期：0。如有重复，执行第六节的去重操作。

### 4.4 特定学校完整性检查

```sql
-- 检查清华大学各年省份覆盖（2024 年应有 27 个省）
SELECT year, COUNT(DISTINCT province_id) AS 省份数, COUNT(*) AS 记录数
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 140
GROUP BY year ORDER BY year;
```

### 4.5 维度表完整性检查

```sql
-- 事实表中有多少学校在维度表中找不到
SELECT COUNT(DISTINCT f.school_id) AS 事实表学校数,
       COUNT(DISTINCT s.school_id) AS 维度表匹配数
FROM gaokao_assistant.fact_admission_history f
LEFT JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id;
```

---

## 五、已知数据缺失（正常现象，无需修复）

| 缺失类型 | 原因 | 影响 |
|---------|------|------|
| 上海/湖北 2021+ 顶校数据 | 新高考改革后静态 API 无对应文件 | 这些省份新高考年份数据缺失 |
| 西藏全部年份 | 大多数高校不在西藏招生 | 正常，API 返回 404 |
| 2018/2019 年 sp_name 为空 | API 历史数据不含此字段 | 用 spname 字段替代 |
| 2018/2019 年 lq_num 为空 | API 历史数据不含此字段 | 无法获取这两年录取人数 |
| min_score=0 | API 返回了记录但分数为 0 | 查询时加 WHERE min_score > 0 |

---

## 六、问题修复

### 6.1 去重

```sql
-- 建去重后的临时表
CREATE TABLE gaokao_assistant.fact_admission_history_dedup AS
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY school_id, province_id, year, special_id, spname, min_score
        ORDER BY school_id
    ) AS rn
    FROM gaokao_assistant.fact_admission_history
) t WHERE rn = 1;

-- 确认行数正确后执行替换
-- SELECT COUNT(*) FROM gaokao_assistant.fact_admission_history_dedup;
-- DROP TABLE gaokao_assistant.fact_admission_history;
-- ALTER TABLE gaokao_assistant.fact_admission_history_dedup RENAME TO fact_admission_history;
```

### 6.2 补采特定学校

修改 scraper.py 中的学校过滤条件，或手动删除断点文件中对应的 key，重跑 scraper.py。

### 6.3 重建维度表

```bash
# dim_school_scraper.py 会自动 DROP + CREATE，直接重跑即可
python3 scripts/dim_school_scraper.py
```

### 6.4 重置断点（从头全量重采）

```bash
rm /tmp/gaokao_done_keys.txt
rm /tmp/gaokao_still_missing.txt
python3 scripts/scraper.py
```

---

## 七、年度更新（每年高考录取结束后）

1. 修改 scraper.py 中的年份范围，加入新年份（如 2025）
2. 删除断点文件，重跑 scraper.py（或只采新年份）
3. 重跑 repair.py 补全
4. 重跑 dim_school_scraper.py 更新排名数据（软科排名每年更新）
5. 更新 README.md 中的数据规模数字
