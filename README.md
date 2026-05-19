# 高考志愿填报数据集 (Gaokao Assistant)

基于 gaokao.cn 公开数据及多源画像构建的高考数仓，覆盖全国 2784 所高校。
数据存储在 ClickZetta Lakehouse，支持多维度 SQL 查询与 AI 智能分析。

---

## 📊 数据规模

| 维度 | 数量 | 状态 |
|------|------|------|
| 高校基础库 | 2,784 所 | ✅ 全量完成 |
| **高校深度画像** | **Top 1000 所** | ✅ **已完成** |
| 历史投档线 (含 2025) | 22.4 万+ 条 | ✅ 已完成 |
| 专业录取历史 (2018-2025) | 270 万+ 条 | ✅ 已完成 |
| 第五轮学科评估 | 267 条 (A/B/C) | ✅ 已完成 |
| 就业质量报告 | 988 条 | ✅ 已完成 |

---

## 📅 核心数据表状态

### 事实表

| 表名 | 说明 | 状态 |
|------|------|------|
| `fact_admission_history` | 专业录取历史（最低分/位次/批次等） | ✅ 已完成 |
| `fact_school_province_score` | 高校在各省份各年的最低投档线 | ✅ **含 2025** |

### 维度表

| 表名 | 说明 | 覆盖度 | 状态 |
|------|------|--------|------|
| `dim_school` | 高校基本信息（985/211/排名） | 全量 | ✅ 已完成 |
| **`dim_employment_report`** | **就业质量（深造率/薪资/雇主）** | **Top 1000** | ✅ **已完成** |
| **`dim_admission_regulation_parsed_v2`** | **招生章程避坑（身体/单科限制）** | **Top 1000** | ✅ **已完成** |
| **`dim_discipline_assessment_5th`** | **第五轮学科评估** | **Top 400** | ✅ **已完成** |
| `dim_school_enriched` | 高校增强信息（保研率/双一流） | Top 200 | ✅ 已完成 |

---

## 🔥 新增：深度画像能力 (Top 1000)

除了基础的分数数据，本项目现已支持**深度画像分析**：

1.  **就业去向查询**：查询 Top 1000 高校的深造率、平均月薪及核心雇主。
    *   *适用场景：判断学校性价比，毕业是考研多还是直接就业多？*
2.  **报考避坑指南**：通过解析招生章程，提供身体限制（如色盲色弱）、单科成绩要求。
    *   *适用场景：防止因身体条件不符被退档。*
3.  **王牌学科检索**：结合第五轮学科评估（A+/A/B），展示学校的强势专业。
    *   *适用场景：同分段下，选哪个学校的王牌专业？*

---

## 📘 典型使用场景

### 1. 志愿填报参考 (分数匹配)
根据考生分数和省份，查询历史上录取分数接近的学校：
```sql
-- 陕西考生 600 分 (理科 2074)，查询 2025 年可报院校
SELECT s.name, f.min_score, e.further_study_rate, e.avg_salary
FROM gaokao_assistant.fact_school_province_score f
JOIN gaokao_assistant.dim_school s ON f.school_id = s.school_id
JOIN gaokao_assistant.dim_employment_report e ON f.school_id = e.school_id
WHERE f.province_id = '61' AND f.type_code = '2074'
  AND f.year = 2025 AND f.min_score BETWEEN 585 AND 610
ORDER BY f.min_score DESC;
```

### 2. 就业与学科实力对比 (深度画像)
对比同类院校的就业质量和优势学科：
```sql
-- 查看广东省主要高校的就业与深造情况
SELECT s.name, e.avg_salary, e.top_employers, d.discipline_name
FROM gaokao_assistant.dim_employment_report e
JOIN gaokao_assistant.dim_school s ON e.school_id = s.school_id
LEFT JOIN gaokao_assistant.dim_discipline_assessment_5th d 
       ON e.school_id = d.school_id AND d.assessment_level = 'A+'
WHERE s.province_name = '广东' AND e.source_platform LIKE '%Restored%'
ORDER BY e.avg_salary DESC;
```

---

## 🛠️ 数据扩展与维护

### 扩展计划执行进度
| 优先级 | 数据项 | 状态 |
| :--- | :--- | :--- |
| **P0** | **投档线（含 2025 年）** | ✅ **已完成** |
| **P1** | **高校增强信息 (保研率等)** | ✅ **已完成** |
| **P2** | **招生章程 (避坑解析)** | ✅ **Top 1000 覆盖** |
| **P3** | **第五轮学科评估** | ✅ **已完成** |
| **New**| **Top 1000 就业画像** | ✅ **已完成** |
| P4 | 一分一段表 | ⏳ 待发布 |
| P5 | 省控线/批次线 | ⏳ 待发布 |

### 维护工具
本项目包含一套自动化的数据维护与修复脚本，位于 `scripts/` 目录下：
*   **`fix_top50_quality_restoration.py`**: 一键恢复 Top 50 头部高校的高精度数据（防覆盖）。
*   **`dim_top1000_expansion.py`**: 扩展覆盖度至 Top 1000 的模板推断脚本。
*   **`gaokao-analysis-playbook`** (Skill): AI 查询操作手册，定义了标准查询模式与避坑指南。

---

## 数据来源

数据主要来自 [gaokao.cn](https://www.gaokao.cn) 公开静态接口及多源整理，仅供学习和研究使用。

