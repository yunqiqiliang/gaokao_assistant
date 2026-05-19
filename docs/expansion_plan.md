# 高考数据采集扩展方案

> 文档版本：v1.0（2026-05-18）
> 状态：规划中，按优先级迭代实施
> 作者：Hermes Agent

---

## 一、现状回顾

### 已有数据（5张表）

| 表 | 行数 | 数据源 | 覆盖范围 |
|---|---|---|---|
| `fact_admission_history` | ~270万 | gaokao.cn schoolspecialscore API | 专业录取历史（2018-2024），32列 |
| `dim_school` | 2,564 | gaokao.cn school/info.json | 高校基本信息（19列） |
| `dim_school_rank` | 6,561 | gaokao.cn school/rank.json | 多榜单排名 |
| `dim_school_special` | 98,837 | gaokao.cn school/special/list.json | 专业评级（第四轮学科评估） |
| `dim_university` | 2,784 | university_info.csv | 全量高校基础列表 |

### 现有架构的不足（对比头部博主数据体系）

| 头部博主有的 | 我们缺的 | 优先级 | 数据源 |
|---|---|---|---|
| 当年招生计划（大厚本） | 无 | P0 | 各省考试院PDF → OCR |
| 一分一段表 | 无（`min_section`仅部分有） | P1 | 各省考试院官网 |
| 省控线/批次线 | 无 | P1 | 各省考试院官网 |
| 招生章程（身体限制等） | 无 | P2 | 各高校本科招生网 |
| 第五轮学科评估（2022） | 只有第四轮（2017） | P2 | 多源汇总 |
| 强基计划/综合评价信息 | 无 | P3 | 各高校招生网 |
| 就业质量报告/薪资数据 | 无 | P3 | 各高校就业网/麦可思 |
| 实时热度指数 | 无 | P4 | API逆向（有反爬） |

---

## 二、数据采集时间表（按高考日历）

```
5月18日（当前）
├── P0 招生计划 → 各省已发布，但gaokao.cn静态API无此数据，需另辟径
├── P2 招生章程 → 各高校已发布，可立即爬取
├── P2 第五轮学科评估 → 可立即整理入库
└── P3 就业质量报告 → 持续收集

6月中旬（出分后）
├── P1 一分一段表 → 各省陆续发布，立即采集
└── P1 省控线/批次线 → 随一分一段表发布

6月下旬
└── P4 实时热度数据 → 出分后API逆向

7-8月（录取后）
└── 投档线/录取结果 → 用于校准算法
```

---

## 三、立即执行项（5月中下旬）

### 3.1 增强 dim_school 表 — 利用 info.json 中未采集的字段

**info.json 中当前未采集的高价值字段：**

| 字段 | 说明 | 价值 |
|---|---|---|
| `pro_type_min` | 各省历年最低投档线（含2025年！） | ★★★★★ 核心价值，可直接用于2026志愿填报参考 |
| `province_score_min` | 各省最低分（2025年） | ★★★★★ 同上 |
| `dualclass` | 双一流学科列表（34个学科） | ★★★★ 比dual_class_name更详细 |
| `fenxiao` | 分校区信息（校本部/分校等） | ★★★ 填报时需注意校区差异 |
| `xueke_rank` | 学科评估汇总（A+:21, A:8...） | ★★★★ 快速了解学校学科实力 |
| `label_list` | 学校标签（985/211/强基/C9/机械五虎...） | ★★★ 增加筛选维度 |
| `rank` | 多榜单排名汇总（软科/校友会/QS/US/泰晤士） | ★★★ 已有dim_school_rank但此更集中 |
| `doctor_arr`/`master_arr` | 博士点/硕士点数量 | ★★ 学术实力指标 |
| `num_lab`/`num_library` | 实验室数/图书馆藏书量 | ★ 基础设施 |
| `recommend_master_rate` | 保研率 | ★★★★ 考生关注度高 |
| `phone`/`email` | 联系方式 | ★ 辅助信息 |
| `content` | 学校简介 | ★ 展示用 |
| `province_single`/`single_year` | 单科要求信息 | ★★★ 填报关键约束 |

**实施方案：**
1. 在 `dim_school` 中新增字段，或在 `dim_school_enriched` 新表中存储
2. 采集 `pro_type_min` 作为单独的 `fact_school_province_score` 表（学校-省份-年份-投档线）
3. 采集 `dualclass` 作为 `dim_dual_class` 表（学校-双一流学科）

### 3.2 第五轮学科评估数据采集

**背景：** 教育部第五轮学科评估（2022年）结果各校只收到自己的，未统一公布。但头部机构已通过多源交叉验证整理。

**实施方案：**
1. 从公开渠道（各校官网新闻、教育部公示名单片段、新闻报道）汇总
2. 创建 `dim_discipline_assessment_5th` 表
3. 字段：学校ID、学科名称、评估等级（A+~C-）

**难点：** 数据不完整，需要多源交叉。可以先用第四轮数据占位，逐步补充第五轮。

### 3.3 招生章程采集

**背景：** 各高校本科招生网在4-5月发布2026年招生章程，包含身体限制、单科要求等关键信息。

**实施方案：**
1. 爬取各高校招生官网的招生章程页面
2. 用 NLP 提取关键约束：
   - 身体限制（视力、色觉、身高）
   - 单科成绩要求
   - 外语语种限制
   - 男女比例
3. 创建 `dim_admission_regulation` 表

**难点：** 各高校官网结构不同，需要针对性适配。可以先从 Top 100 高校开始。

---

## 四、中期执行项（6月及以后）

### 4.1 一分一段表采集（6月中旬）

**实施方案：**
1. 各省考试院官网发布一分一段表（通常为HTML表格或PDF）
2. 解析后入库：`fact_province_score_segment` 表
3. 字段：省份、年份、分数、本段人数、累计人数、累计人数百分比

**价值：** 用于"同位分"换算，是志愿填报的核心计算依据。

### 4.2 省控线/批次线采集（6月中旬）

**实施方案：**
1. 各省考试院公布各批次控制分数线
2. 入库：`dim_province_control_line` 表
3. 字段：省份、年份、批次（本科一批/二批/专科等）、科类（物理/历史/综合）、分数线

### 4.3 招生计划数据（需要独立方案）

**背景：** gaokao.cn 静态 API **不提供**招生计划数据（各专业计划招生人数）。这是全年最核心的"锚"数据。

**可能的数据源：**
1. 各省考试院官网的"招生计划"PDF（大厚本电子版）
2. 阳光高考平台（gaokao.chsi.com.cn）的计划查询
3. 各高校招生网公布的分省分专业计划

**实施方案（待验证）：**
1. 先尝试阳光高考平台API是否有结构化计划数据
2. 如无，则针对重点省份（广东、浙江、江苏、山东等）的考试院PDF做OCR
3. OCR方案：百度/腾讯OCR API → 正则提取"院校代码-专业代码-计划数" → 入库

---

## 五、数据库表设计（新增）

### 5.1 fact_school_province_score（学校-省份投档线）

```sql
CREATE TABLE gaokao_assistant.fact_school_province_score (
    school_id       INT     COMMENT '高校ID',
    province_id     STRING  COMMENT '生源省份代码',
    year            INT     COMMENT '年份',
    type_code       STRING  COMMENT '招生类型编码（如2073=物理类, 2074=历史类, 3=综合改革, 1=理科, 2=文科）',
    min_score       INT     COMMENT '最低投档分数',
    data_year       INT     COMMENT '数据年份（区分实际招生年份和发布年份）'
) COMMENT '高校在各省份各年的最低投档线。数据来自gaokao.cn school/info.json 的 pro_type_min 字段'
```

### 5.2 dim_dual_class（双一流学科）

```sql
CREATE TABLE gaokao_assistant.dim_dual_class (
    school_id       INT     COMMENT '高校ID',
    discipline_name STRING  COMMENT '双一流学科名称（如计算机科学、数学）'
) COMMENT '高校双一流建设学科列表。数据来自gaokao.cn school/info.json 的 dualclass 字段'
```

### 5.3 dim_admission_regulation（招生章程关键信息）

```sql
CREATE TABLE gaokao_assistant.dim_admission_regulation (
    school_id           INT     COMMENT '高校ID',
    regulation_year     INT     COMMENT '章程年份',
    body_restriction    STRING  COMMENT '身体限制（视力、色觉、身高要求等）',
    single_subject_req  STRING  COMMENT '单科成绩要求',
    language_restriction STRING  COMMENT '外语语种限制',
    gender_ratio        STRING  COMMENT '男女比例要求',
    other_restrictions  STRING  COMMENT '其他特殊要求',
    source_url          STRING  COMMENT '章程原文链接',
    raw_text            STRING  COMMENT '章程原文（用于后续NLP分析）'
) COMMENT '高校招生章程中的关键约束信息。用于填报"排雷"'
```

### 5.4 fact_province_score_segment（一分一段表）

```sql
CREATE TABLE gaokao_assistant.fact_province_score_segment (
    province_id     STRING  COMMENT '省份代码',
    year            INT     COMMENT '年份',
    score           INT     COMMENT '分数',
    segment_count   INT     COMMENT '该分数段人数',
    cumulative_count INT    COMMENT '累计人数',
    subject_type    STRING  COMMENT '科类（物理类/历史类/综合改革等）'
) COMMENT '各省一分一段表。出分后各省考试院发布'
```

### 5.5 dim_province_control_line（省控线/批次线）

```sql
CREATE TABLE gaokao_assistant.dim_province_control_line (
    province_id     STRING  COMMENT '省份代码',
    year            INT     COMMENT '年份',
    batch_name      STRING  COMMENT '批次名称（本科批/特殊类型招生控制线等）',
    subject_type    STRING  COMMENT '科类',
    score_line      INT     COMMENT '控制分数线'
) COMMENT '各省各批次控制分数线'
```

### 5.6 dim_discipline_assessment_5th（第五轮学科评估）

```sql
CREATE TABLE gaokao_assistant.dim_discipline_assessment_5th (
    school_id           INT     COMMENT '高校ID',
    discipline_name     STRING  COMMENT '学科名称',
    assessment_level    STRING  COMMENT '评估等级（A+~C-）',
    confidence          STRING  COMMENT '置信度（confirmed/estimated）'
) COMMENT '第五轮学科评估（2022年）结果。因教育部未统一公布，部分数据为多源交叉验证估算'
```

---

## 六、实施路线图

### Phase 1：立即可做（5月18日-5月31日）

| 任务 | 状态 | 说明 |
|---|---|---|
| 1.1 增强 dim_school 字段 | **已完成** | 已采集保研率/双一流/校区/标签等 |
| 1.2 采集投档线 fact_school_province_score | **已完成** | 22.4万条，含2025年数据 |
| 1.3 采集双一流学科 dim_dual_class | **已完成** | 498条记录 |
| 1.4 第五轮学科评估数据整理 | **已完成** | 已采集 224 条 A+ 学科数据，覆盖 31 所高校 |
| 1.5 招生章程爬取（Top 100） | **部分完成** | 首页采集 88/98 成功，深度爬取 7/35 成功（URL 模式需定制） |

### Phase 2：6月数据（6月1日-6月30日）

| 任务 | 状态 | 说明 |
|---|---|---|
| 2.1 一分一段表采集 | 待6月中旬 | 出分后立即采集 |
| 2.2 省控线/批次线采集 | 待6月中旬 | 出分后立即采集 |
| 2.3 招生章程深度爬取 | 待优化 | 需针对各校网站结构定制 URL |

### Phase 3：7-8月数据

| 任务 | 状态 | 说明 |
|---|---|---|
| 3.1 投档线/录取结果回填 | 待7月 | 用于校准算法 |
| 3.2 招生计划数据攻坚 | 待验证 | 探索阳光高考/各省考试院数据源 |

### Phase 4：长期建设

| 任务 | 说明 |
|---|---|
| 就业质量报告采集 | 持续收集各高校就业报告 |
| 实时热度数据 | 出分后逆向API |
| 数据质量持续优化 | 去重、补全、校验 |

---

## 七、注意事项

1. **不要硬编码密码**：所有脚本用 `os.environ["CZ_PASSWORD"]`，无默认值
2. **渐进采集**：不必一次做全，按优先级迭代
3. **断点续传**：所有采集脚本支持断点续传
4. **数据质量**：采集后必须做质量检查（重复、空值、异常值）
5. **注释同步**：每次采集完成后自动更新表注释（含最新行数）
