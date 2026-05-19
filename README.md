# 高考志愿填报数据集 (Gaokao Assistant)

基于 gaokao.cn 公开数据构建的高考数据集，覆盖全国 2784 所高校。
数据存储在 ClickZetta Lakehouse，支持多维度 SQL 查询与 AI 智能分析。

---

## 📊 数据规模

| 维度 | 数量 | 状态 |
|------|------|------|
| 高校基础库 | 2784 所 | ✅ 全量 |
| 高校深度画像 | Top 1000 所 | ✅ **Top 1000 覆盖** |
| 历史投档线 (2018-2025) | ~400 万条 | ✅ 已完成 |
| 专业录取历史 (2018-2024) | ~270 万条 | ✅ 已完成 |
| 就业质量报告 | 988 条 | ✅ **Top 1000 覆盖** |
| 第五轮学科评估 | 267 条 | ✅ **Top 300 覆盖** |

---

## 📅 数据表状态

### 事实表

| 表名 | 说明 | 状态 |
|------|------|------|
| `fact_admission_history` | 专业录取历史（最低分/位次/批次等） | ✅ 已完成 |
| `fact_school_province_score` | 高校投档线（含 2025 年） | ✅ **已完成** |

### 维度表（深度画像）

| 表名 | 说明 | 覆盖度 | 状态 |
|------|------|--------|------|
| `dim_school` | 高校基本信息（985/211/排名） | 全量 | ✅ 已完成 |
| **`dim_employment_report`** | **就业质量（深造率/薪资/雇主）** | **Top 1000** | ✅ **已完成** |
| **`dim_admission_regulation_parsed_v2`** | **招生章程避坑（身体/单科限制）** | **Top 1000** | ✅ **已完成** |
| **`dim_discipline_assessment_5th`** | **第五轮学科评估** | **Top 300** | ✅ **已完成** |
| `dim_school_enriched` | 高校增强信息（保研率/双一流） | Top 100 | ✅ 已完成 |
| **`dim_major_category`** | **教育部专业分类映射（大类/门类）** | **全量** | ✅ **新增完成** |

---

## 📘 典型使用场景

### 1. 志愿填报参考（分省/分科）
根据考生分数和省份，查询历史上录取分数接近的学校与专业：
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

### 2. 按专业大类检索（新增能力）
利用教育部《专业目录》，将所有细碎专业归纳为“大类”进行对比：
```sql
-- 查询“计算机类”所有专业的录取分
SELECT s.name, f.spname, f.min_score, d.category_name
FROM gaokao_assistant.fact_admission_history f
JOIN gaokao_assistant.dim_school s ON CAST(f.school_id AS INT) = s.school_id
JOIN gaokao_assistant.dim_major_category d ON f.spname = d.major_name
WHERE f.province_id = '61' AND f.year = 2025
  AND d.category_name = '计算机类'
ORDER BY f.min_score DESC;
```

### 3. 就业与学科实力对比（深度画像）
对比同类院校的就业质量和优势学科（结合新增维度表）：
```sql
-- 对比 Top 100 高校在计算机专业的学科评估与就业薪资
SELECT s.name, e.avg_salary, d.assessment_level
FROM gaokao_assistant.dim_employment_report e
JOIN gaokao_assistant.dim_school s ON e.school_id = s.school_id
LEFT JOIN gaokao_assistant.dim_discipline_assessment_5th d ON e.school_id = d.school_id
WHERE s.name IN ('清华大学', '北京大学', '浙江大学')
  AND d.discipline_name = '计算机科学与技术'
ORDER BY e.avg_salary DESC;
```

---

## 🚀 数据扩展计划与维护

当前数据已覆盖专业录取历史、投档线（含 2025）及 Top 1000 高校深度画像。

| 优先级 | 数据 | 状态 | 说明 |
| :--- | :--- | :--- | :--- |
| **P0** | 投档线（含 2025 年） | ✅ 已完成 | 覆盖全量，数据清洗完毕 |
| **P1** | 保研率/双一流/校区 | ✅ 已完成 | Top 100 覆盖 |
| **P2** | 招生章程（身体限制等） | ✅ 已完成 | **Top 1000 覆盖**，含 JSON 避坑解析 |
| **P3** | 第五轮学科评估 | ✅ 已完成 | A+/A/B 等级数据已入库 |
| **P4** | 一分一段表 | ⏳ 待发布 | 预计 6 月中旬 |
| **P5** | 省控线/批次线 | ⏳ 待发布 | 预计 6 月中旬 |

### 维护与质量保证
*   **数据分层策略**: Top 50 为高精人工数据 (Tier 1)，Top 1000 为区域模板推断数据 (Tier 2/3)。
*   **自动修复**: 扩展 Top 1000 后，请运行 `scripts/fix_top50_quality_restoration.py` 确保头部高校数据不被覆盖。
*   **AI 分析技能**: 项目内置 `gaokao-analysis-playbook`，定义了标准的 SQL 查询模式与 ClickZetta 避坑指南。

---

## 目录结构

```
gaokao_assistant/
├── README.md
├── .env.example
├── docs/
├── scripts/
│   ├── scraper.py                  # 主采集脚本
│   ├── dim_top1000_expansion.py    # Top 1000 扩展脚本
│   ├── fix_top50_quality_restoration.py # Top 50 质量恢复脚本
│   └── ...                         # 其他采集/清洗脚本
└── .hermes/skills/gaokao-analysis-playbook/ # AI 分析技能
```

---

## 数据来源

数据来自 [gaokao.cn](https://www.gaokao.cn) 公开静态接口，仅供学习和研究使用。
