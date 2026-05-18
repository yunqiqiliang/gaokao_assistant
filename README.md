# 高考志愿填报数据集

基于 gaokao.cn 公开数据构建的高考录取历史数据集，覆盖全国热度前 500 所高校、31 个省份、2018-2024 年共 7 年，约 **203 万条**专业录取记录。

数据存储在 ClickZetta Lakehouse，可直接用 SQL 查询，也可以导出为 CSV 使用。

---

## 数据规模

| 维度 | 数量 |
|------|------|
| 高校 | 496 所（热度前 500，其中 4 所无招生数据） |
| 省份 | 31 个（含直辖市、自治区） |
| 年份 | 2018 - 2024，共 7 年 |
| 总记录数 | 约 203 万条 |
| 覆盖率 | 86.1%（其余为该校不在该省招生） |

---

## 数据表

### 事实表

| 表名 | 说明 | 行数 |
|------|------|------|
| `fact_admission_history` | 专业录取历史（最低分/位次/批次/选科要求等） | ~203 万 |

### 维度表（需运行 `dim_school_scraper.py` 采集）

| 表名 | 说明 |
|------|------|
| `dim_school` | 高校基本信息（985/211/双一流/排名/院士数等） |
| `dim_school_rank` | 高校各榜单排名（软科/QS/US/泰晤士） |
| `dim_school_special` | 高校专业评级（国家一流专业/学科评估等级） |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r scripts/requirements.txt
```

### 2. 查询数据（SQL）

连接 ClickZetta Lakehouse 后直接查询：

```sql
-- 查看清华大学2024年在北京的录取情况
SELECT spname, local_batch_name, min_score, min_rank
FROM gaokao_assistant.fact_admission_history
WHERE school_id = 140
  AND province_id = '11'
  AND year = 2024
  AND min_score > 0
ORDER BY min_score DESC;
```

更多示例见 [docs/quick_start.md](docs/quick_start.md)。

### 3. 重新采集数据

```bash
# 采集专业录取历史（主表）
python3 scripts/scraper.py

# 数据补全（处理采集中断、API失败等）
python3 scripts/repair.py

# 采集高校维度信息（dim_school 等三张表）
python3 scripts/dim_school_scraper.py
```

---

## 主要字段说明

`fact_admission_history` 核心字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `school_id` | INT | 高校 ID（如清华=140，北大=31） |
| `province_id` | STRING | 省份代码（如 11=北京，44=广东） |
| `year` | INT | 招生年份（2018-2024） |
| `spname` | STRING | 专业完整名称（含备注） |
| `sp_name` | STRING | 专业基础名（2018/2019年为空） |
| `local_batch_name` | STRING | 批次名称（各省叫法不同） |
| `zslx_name` | STRING | 招生类型（普通类/中外合作等） |
| `min_score` | INT | 最低录取分（0=数据缺失） |
| `min_rank` | INT | 最低录取位次（0=该省不公布） |
| `diff` | INT | 超出省控线分数 |
| `sp_info` | STRING | 选科要求（新高考省份2019年起有值） |
| `level2_name` | STRING | 学科门类（工学/理学/文学等） |
| `level3_name` | STRING | 专业大类（计算机类/经济学类等） |

完整字段说明见 [docs/data_dictionary.md](docs/data_dictionary.md)。

---

## 数据质量说明

- **min_score=0**：2022 年新高考过渡期部分省份数据缺失，查询时建议加 `WHERE min_score > 0`
- **2018/2019 年**：`sp_name`、`lq_num` 字段为空（API 历史数据限制），用 `spname` 替代
- **批次名称**：各省叫法不统一（"本科批"/"本科一批"/"平行录取一段"），跨省比较需归一化
- **选科要求**：仅新高考省份 2019 年起有值，全表约 13.6% 有值
- **所有字符串字段**：空值统一为 NULL（非空字符串），可直接用 `IS NULL` 判断

---

## 目录结构

```
gaokao_assistant/
├── README.md
├── docs/
│   ├── data_dictionary.md    # 完整字段说明
│   └── quick_start.md        # 快速上手（含 SQL 示例）
└── scripts/
    ├── scraper.py             # 主采集脚本（专业录取历史）
    ├── repair.py              # 数据补全脚本
    ├── dim_school_scraper.py  # 高校维度数据采集
    └── requirements.txt       # Python 依赖
```

---

## 数据来源

数据来自 [gaokao.cn](https://www.gaokao.cn) 公开静态接口，仅供学习和研究使用。

主要接口：
- `schoolspecialscore/{school_id}/{year}/{province_id}.json` — 专业录取分数（已采集）
- `school/{school_id}/info.json` — 高校基本信息
- `school/{school_id}/rank.json` — 高校排名
- `school/{school_id}/special/list.json` — 高校专业评级
