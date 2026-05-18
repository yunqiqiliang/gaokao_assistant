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

## 七、年度更新（以 2025 年为例）

每年高考录取结束后（通常 9 月底），gaokao.cn 会陆续放出新一年的录取数据。以下以补采 2025 年数据为例。

### 步骤 1：确认数据已上线

先验证 API 是否已有 2025 年数据，再开始采集：

```python
import urllib.request, json

url = "https://static-data.gaokao.cn/www/2.0/schoolspecialscore/140/2025/11.json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gaokao.cn/"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read())

items = list(data.get("data", {}).values())
cnt = sum(len(v.get("item", [])) for v in items if isinstance(v, dict))
print(f"code={data.get('code')}  条数={cnt}")
# code=0000 且 cnt>0 说明数据已上线，可以开始采集
# code=0000 但 cnt=0，或 HTTP 404，说明数据还未放出
```

### 步骤 2：修改年份配置

编辑 `scripts/scraper.py` 第 61 行，加入 2025：

```python
# 修改前
YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

# 修改后
YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
```

同样修改 `scripts/repair.py` 中相同的 `YEARS` 常量（搜索 `YEARS =` 找到对应行）。

### 步骤 3：只采新年份（推荐，避免重复采集历史数据）

断点文件已记录了历史年份的完成状态，直接重跑 scraper.py 会自动跳过已完成的组合，只采 2025 年的新数据：

```bash
export $(cat .env | xargs)
python3 scripts/scraper.py
# 输出示例：
# 断点: 已完成 xxxxxx 个组合，继续采集
# 待处理任务: ~86,000 个（2784所 × 31省 × 1年）
```

耗时约 1-2 小时（只采一年，比全量快很多）。

### 步骤 4：补全漏采数据

```bash
python3 scripts/repair.py
```

### 步骤 5：更新维度表排名数据

软科排名、QS 排名等每年更新，重跑维度采集脚本：

```bash
python3 scripts/dim_school_scraper.py
```

> 注意：dim_school_scraper.py 会 DROP + CREATE 三张维度表，原有数据会被覆盖，这是正常的。

### 步骤 6：验证新数据

```sql
-- 确认 2025 年数据已入库
SELECT COUNT(*) AS 记录数, COUNT(DISTINCT school_id) AS 学校数,
       COUNT(DISTINCT province_id) AS 省份数
FROM gaokao_assistant.fact_admission_history
WHERE year = 2025;

-- 对比各年数据量，确认 2025 年规模合理
SELECT year, COUNT(*) AS 记录数
FROM gaokao_assistant.fact_admission_history
GROUP BY year ORDER BY year;
```

2025 年记录数应与 2024 年接近（误差在 ±20% 以内为正常）。

### 步骤 7：更新文档

修改 `README.md` 中的数据规模表格，将年份范围从 2018–2024 改为 2018–2025，更新总记录数。

---

## 八、常用脚本速查

| 场景 | 命令 |
|------|------|
| 全量采集（首次） | `python3 scripts/scraper.py` |
| 断点续采 | `python3 scripts/scraper.py`（直接重跑，自动跳过已完成） |
| 补全漏采 | `python3 scripts/repair.py` |
| 更新维度表 | `python3 scripts/dim_school_scraper.py` |
| 补采新年份 | 修改 YEARS 常量后重跑 `scraper.py` |
| 重置断点（从头全采） | `rm /tmp/gaokao_done_keys.txt && python3 scripts/scraper.py` |
