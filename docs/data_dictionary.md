# 高考数据字典 (Data Dictionary)

由于 ClickZetta 引擎的语法特性，本文件作为数仓的**官方文档**，详细记录 Schema、表及字段的含义与枚举值，同时也作为后续元数据维护的基准。

## 📚 Schema: `gaokao_assistant`
> 高考志愿填报辅助数据集。包含历史分数、投档线、高校画像、专业就业及转专业政策等。

---

## 1. 维度表 (Dimensions)

### `dim_school` (高校基础信息表)
*   **描述**: 全国高校的基本属性数据，包括 985/211、排名等。
*   **核心字段**:
    *   `school_id` (INT): 唯一 ID (来源于 Gaokao.cn)
    *   `name` (STRING): 高校名称
    *   `f985` (INT): 是否 985 高校 (**1=是, 2=否**)
    *   `f211` (INT): 是否 211 高校 (**1=是, 2=否**)
    *   `school_nature` (STRING): 办学性质 (**公办/民办**)
    *   `ruanke_rank` (INT): 软科排名

### `dim_employment_report` (就业质量报告)
*   **描述**: Top 1000 高校的就业率、薪资及核心雇主数据。
*   **核心字段**:
    *   `further_study_rate` (DOUBLE): 深造率 (0.0 - 1.0)
    *   `avg_salary` (INT): 估算平均月薪 (¥)
    *   `top_employers` (STRING): 核心雇主列表

### `dim_major_category` (专业分类目录)
*   **描述**: 教育部本科专业映射关系（专业 -> 大类 -> 门类）。
*   **核心字段**:
    *   `major_code` (STRING): 专业代码
    *   `major_name` (STRING): 专业名称
    *   `category_name` (STRING): 二级类名称 (如 "计算机类")
    *   `door_name` (STRING): 一级门类名称 (如 "工学")

### `dim_school_campus` (校区分布)
*   **描述**: 高校多校区分布及中外合作办学标记。
*   **核心字段**:
    *   `is_main_campus` (INT): **1=本部, 0=分校区**
    *   `is_sino_foreign` (INT): **1=中外合作, 0=普通**

### 其他维度表
*   **`dim_admission_regulation_parsed_v2`**: 招生章程结构化解析（Top 1000，含身体/单科限制）。
*   **`dim_major_transfer_policy`**: 高校转专业政策库（门槛/难度）。
*   **`dim_sino_foreign_programs`**: 中外合作办学项目详情。

---

## 2. 事实表 (Facts)

### `fact_admission_history` (历史专业录取数据)
*   **描述**: 最核心的历年专业录取分数表（2018-2025）。
*   **核心字段**:
    *   `spname` (STRING): **专业名称** (全名，含方向，如 "自动化类（国家专项）")
    *   `min_score` (INT): 最低录取分 (**=0 表示缺失**)
    *   `max_score` (INT): 最高录取分 (覆盖率 59%)
    *   `min_rank` (INT): 最低录取位次
    *   `local_batch_name` (STRING): 录取批次 (如 "本科一批")
    *   `zslx_name` (STRING): 招生类型 (如 "普通类", "国家专项")
    *   `sp_info` (STRING): 选科要求 (如 "物理")

### `fact_school_province_score` (高校投档线)
*   **描述**: 各高校在各省每年的最低投档分数线。
*   **核心字段**:
    *   `min_score` (INT): 投档线
    *   `province_id` (STRING): 省份代码 (**61=陕西**, **11=北京**)
    *   `type_code` (STRING): 科类代码 (**2074=理科**, **2073=文科**)

### `fact_major_employment` (分专业就业预估)
*   **描述**: 基于行业系数模型预估的分专业薪资与就业率。
*   **核心字段**:
    *   `major_name` (STRING): 专业名称
    *   `category_name` (STRING): 所属大类
    *   `avg_salary` (INT): 预估月薪 (¥)
    *   `employment_rate` (DOUBLE): 预估就业率 (0.80 ~ 0.99)
