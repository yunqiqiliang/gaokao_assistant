# 高考志愿填报数据集

基于 gaokao.cn 公开数据构建的高考录取历史数据集，覆盖全国 2784 所高校、31 个省份、2018-2024 年共 7 年。

数据存储在 ClickZetta Lakehouse，可直接用 SQL 查询分析。

---

## 数据规模

| 维度 | 数量 |
|------|------|
| 高校（事实表） | ~2784 所（目标全量） |
| 高校（维度表） | 2564 所 |
| 省份 | 31 个（含直辖市、自治区） |
| 年份 | 2018–2025（投档线含 2025） |
| 录取记录 | ~270 万条 |
| 专业评级记录 | 98,837 条 |
| 投档线记录 | 采集中（含 2025 年数据） |
| 双一流学科 | 采集中 |
| 招生章程 | 采集中（Top 50 优先） |

---

## 数据表

### 事实表

| 表名 | 说明 | 状态 |
|------|------|------|
| `fact_admission_history` | 专业录取历史（最低分/位次/批次/选科要求等 32 列） | 已完成 |
| `fact_school_province_score` | 高校在各省份各年的最低投档线（含 2025 年） | 采集中 |

### 维度表

| 表名 | 说明 | 状态 |
|------|------|------|
| `dim_school` | 高校基本信息（985/211/双一流/软科排名/院士数等） | 已完成 |
| `dim_school_rank` | 高校各榜单排名（软科/校友会/QS/US/泰晤士） | 已完成 |
| `dim_school_special` | 高校专业评级（国家一流专业/学科评估等级） | 已完成（第四轮） |
| `dim_university` | 全国高校基础列表（含地理坐标、热度排名） | 已完成 |
| `dim_dual_class` | 双一流建设学科列表 | 采集中 |
| `dim_campus` | 高校校区和院系信息 | 采集中 |
| `dim_school_enriched` | 高校增强信息（保研率/联系方式/简介/标签） | 采集中 |
| `dim_admission_regulation` | 招生章程关键约束（身体限制/单科要求等） | 采集中 |
| `dim_discipline_assessment_5th` | 第五轮学科评估（2022 年） | 待整理 |

---

## 典型使用场景

### 1. 志愿填报参考
根据考生分数和省份，查询历史上哪些学校哪些专业的录取分数线与考生分数接近：
```sql
-- 广东考生 620 分，查 2024 年普通类可冲/稳/保的专业
SELECT s.name, f.spname, f.local_batch_name, f.min_score, f.min_rank
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
WHERE f.province_id = '44' AND f.year = 2024
  AND f.min_score BETWEEN 600 AND 635
  AND f.zslx_name = '普通类' AND f.min_score > 0
ORDER BY f.min_score DESC;
```

### 2. 院校横向对比
对比同类院校在同一省份的录取分数差异，判断院校梯度：
```sql
-- 对比 985 高校 2024 年在浙江的最低录取分
SELECT s.name, s.ruanke_rank, MIN(f.min_score) AS min_score, MIN(f.min_rank) AS min_rank
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
WHERE f.province_id = '33' AND f.year = 2024
  AND s.f985 = 1 AND f.min_score > 0
GROUP BY s.name, s.ruanke_rank
ORDER BY min_score DESC;
```

### 3. 专业分数趋势分析
追踪某专业历年分数线变化，判断热度走势：
```sql
-- 清华大学计算机类专业在北京历年最低分
SELECT year, spname, min_score, min_rank
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 140 AND province_id = '11'
  AND spname LIKE '%计算机%' AND min_score > 0
ORDER BY year, min_score DESC;
```

### 4. 选科规划（新高考省份）
根据选科要求筛选可报专业，辅助高一/高二选科决策：
```sql
-- 湖南考生选了物理，查 2024 年医学类可报专业
SELECT s.name, f.spname, f.sp_info, f.min_score, f.min_rank
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
WHERE f.province_id = '43' AND f.year = 2024
  AND f.level2_name LIKE '%医学%'
  AND (f.sp_info LIKE '%物理%' OR f.sp_info IS NULL)
  AND f.min_score > 0
ORDER BY f.min_score DESC;
```

### 5. 学科评估与录取分数联合分析
结合教育部学科评估等级，找性价比高的专业：
```sql
-- A+ 学科评估的计算机专业，各校录取分对比
SELECT s.name, sp.xueke_rank_score, f.province_id,
       MIN(f.min_score) AS min_score
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
JOIN gaokao_assistant.dim_school_special sp ON s.school_id = sp.school_id
WHERE sp.name LIKE '%计算机%' AND sp.xueke_rank_score = 'A+'
  AND f.year = 2024 AND f.min_score > 0
GROUP BY s.name, sp.xueke_rank_score, f.province_id
ORDER BY min_score DESC;
```

---

## 快速开始

### 环境配置

```bash
pip install -r scripts/requirements.txt

# 配置连接信息（复制模板后填入真实值）
cp .env.example .env
# 编辑 .env，填入 CZ_SERVICE / CZ_INSTANCE / CZ_WORKSPACE / CZ_USERNAME / CZ_PASSWORD
```

### 运行采集脚本

```bash
# 加载环境变量
export $(cat .env | xargs)

# 1. 采集专业录取历史（主表，支持断点续采）
python3 scripts/scraper.py

# 2. 数据补全（采集中断或 API 失败后运行）
python3 scripts/repair.py

# 3. 采集高校维度信息（dim_school 等三张表）
python3 scripts/dim_school_scraper.py
```

完整操作流程见 [docs/ops_runbook.md](docs/ops_runbook.md)。

---

## 数据完整性说明

### 已知缺失

| 省份 | 缺失年份 | 原因 |
|------|---------|------|
| 上海 | 2022+ | 新高考改革后数据迁移，静态 API 无对应文件 |
| 湖北 | 2021+ | 同上 |
| 湖南 | 部分年份 | 同上 |
| 海南 | 部分年份 | 同上 |
| 西藏 | 全部年份 | 大多数高校不在西藏招生 |

这些缺失是数据源（gaokao.cn 静态 API）本身的限制，不是采集问题。

### 字段级缺失

- `min_score = 0`：数据缺失，查询时加 `WHERE min_score > 0`
- `sp_name`：2018/2019 年为空，用 `spname` 替代
- `lq_num`（录取人数）：2018/2019 年为空
- `sp_info`（选科要求）：仅新高考省份 2019 年起有值

---

## 目录结构

```
gaokao_assistant/
├── README.md
├── .env.example              # 连接配置模板
├── docs/
│   ├── data_dictionary.md    # 完整字段说明（32 列）
│   ├── quick_start.md        # SQL 查询示例
│   └── ops_runbook.md        # 运维手册（从头建库/补数据/质量检查/修复）
└── scripts/
    ├── scraper.py                          # 主采集脚本（专业录取历史，支持断点续采）
    ├── repair.py                           # 数据补全脚本
    ├── dim_school_scraper.py               # 高校维度数据采集
    ├── fact_school_province_score_scraper.py  # 投档线采集（含2025年数据）
    ├── dim_school_enrich_scraper.py        # 高校增强信息采集（保研率/双一流学科/校区等）
    ├── dim_admission_regulation_scraper.py # 招生章程采集（身体限制/单科要求等）
    ├── dim_discipline_assessment_5th_loader.py # 第五轮学科评估数据加载器
    └── requirements.txt                    # Python 依赖
```

---


---

## 数据扩展计划

当前数据已覆盖专业录取历史和高校基本信息，正在按以下优先级扩展：

| 优先级 | 数据 | 时间窗口 | 状态 |
|--------|------|----------|------|
| P0 | 投档线（含 2025 年） | 立即 | 采集中 |
| P1 | 保研率/双一流学科/校区信息 | 立即 | 采集中 |
| P2 | 招生章程（身体限制等） | 立即 | 采集中 |
| P3 | 第五轮学科评估 | 持续 | 待整理 |
| P4 | 一分一段表 | 6 月中旬 | 待发布 |
| P5 | 省控线/批次线 | 6 月中旬 | 待发布 |
| P6 | 招生计划（大厚本） | 持续 | 探索数据源 |

详见 [docs/expansion_plan.md](docs/expansion_plan.md)。
## 数据来源

数据来自 [gaokao.cn](https://www.gaokao.cn) 公开静态接口，仅供学习和研究使用。

| 接口 | 说明 |
|------|------|
| `schoolspecialscore/{school_id}/{year}/{province_id}.json` | 专业录取分数（事实表数据源） |
| `school/{school_id}/info.json` | 高校基本信息（dim_school 数据源） |
| `school/{school_id}/rank.json` | 高校排名（dim_school_rank 数据源） |
| `school/{school_id}/special/list.json` | 高校专业评级（dim_school_special 数据源） |
