# 数据字典

本文档说明 `gaokao_assistant` schema 下所有表的字段含义。

---

## 表概览

| 表名 | 类型 | 行数 | 说明 |
|------|------|------|------|
| `fact_admission_history` | 事实表 | ~270 万 | 专业录取历史（32 列） |
| `dim_school` | 维度表 | 2,564 | 高校基本信息 |
| `dim_school_rank` | 维度表 | 6,561 | 高校各榜单排名 |
| `dim_school_special` | 维度表 | 98,837 | 高校专业评级 |
| `dim_university` | 维度表 | 2,784 | 全国高校基础列表（含地理坐标） |

---

## fact_admission_history

数据来源：`gaokao.cn/schoolspecialscore/{school_id}/{year}/{province_id}.json`

### 核心维度字段

| 字段 | 类型 | 空值 | 说明 |
|------|------|------|------|
| `school_id` | INT | 无 | 高校 ID（gaokao.cn 内部编码，非教育部代码）。清华=140，北大=31，复旦=132，上交=125，浙大=114，西交=330 |
| `province_id` | STRING | 无 | 生源省份代码。11=北京，31=上海，33=浙江，44=广东，51=四川，完整对照见下表 |
| `year` | INT | 无 | 招生年份（2018–2024） |

省份代码对照：

| 代码 | 省份 | 代码 | 省份 | 代码 | 省份 |
|------|------|------|------|------|------|
| 11 | 北京 | 32 | 江苏 | 51 | 四川 |
| 12 | 天津 | 33 | 浙江 | 52 | 贵州 |
| 13 | 河北 | 34 | 安徽 | 53 | 云南 |
| 14 | 山西 | 35 | 福建 | 54 | 西藏 |
| 15 | 内蒙古 | 36 | 江西 | 61 | 陕西 |
| 21 | 辽宁 | 37 | 山东 | 62 | 甘肃 |
| 22 | 吉林 | 41 | 河南 | 63 | 青海 |
| 23 | 黑龙江 | 42 | 湖北 | 64 | 宁夏 |
| 31 | 上海 | 43 | 湖南 | 65 | 新疆 |
| — | — | 44 | 广东 | — | — |
| — | — | 45 | 广西 | — | — |
| — | — | 46 | 海南 | — | — |
| — | — | 50 | 重庆 | — | — |

### 专业信息字段

| 字段 | 类型 | 空值 | 说明 |
|------|------|------|------|
| `special_id` | STRING | 少量 | 专业 ID（gaokao.cn 内部编码） |
| `sp_name` | STRING | 2018/2019 年为空 | 专业基础名称（不含备注）。2018/2019 年 API 不返回此字段，用 `spname` 替代 |
| `spname` | STRING | 极少 | 专业完整名称（含备注，如"计算机科学与技术（雷军班）"）。核心字段，所有年份均可用 |
| `info` | STRING | ~60% | 专业附加说明 |
| `remark` | STRING | ~80% | 备注 |

### 批次与招生类型字段

| 字段 | 类型 | 空值 | 说明 |
|------|------|------|------|
| `batch` | STRING | 少量 | 批次内部编码（API 原始值），建议用 `local_batch_name` |
| `local_batch_name` | STRING | 少量 | 批次本地化名称。各省叫法不统一：本科批/本科一批/平行录取一段等。新高考省份合并批次后统称"本科批" |
| `zslx_name` | STRING | 无 | 招生类型。主要值：普通类(96.4%)、中外合作办学(2.4%)、国家专项计划(0.4%)、预科(0.3%) |
| `type` | STRING | 部分 | 招生类型内部编码（API 原始值） |

### 学科分类字段

| 字段 | 类型 | 空值 | 说明 |
|------|------|------|------|
| `level1_name` | STRING | ~1.8% | 学历层次，如"本科(普通)" |
| `level2_name` | STRING | ~1.8% | 学科门类，如"工学"/"理学"/"医学"/"经济学" |
| `level3_name` | STRING | ~1.8% | 专业大类，如"计算机类"/"经济学类"/"临床医学类" |

### 录取分数字段

| 字段 | 类型 | 空值/缺失 | 说明 |
|------|------|---------|------|
| `min_score` | INT | 0 表示缺失（约 0.3%） | 最低录取分数。查询时加 `WHERE min_score > 0` |
| `max_score` | INT | 0 表示缺失 | 最高录取分数。部分省份不提供 |
| `average_score` | INT | 0 表示缺失（约 40%） | 平均录取分数 |
| `min_rank` | INT | 0 表示不适用（约 2.6%） | 最低录取位次。老高考省份（文理分科）无位次，此字段为 0 |
| `min_section` | STRING | ~30% | 最低分对应的一分一段位次（原始字符串） |
| `diff` | INT | 无 | 线差（最低分 - 省控线）。可衡量专业热度 |
| `lq_num` | STRING | 2018/2019 年为空，共约 29% | 录取人数。存为字符串，使用时需转换 |

### 选科与专业组字段（新高考省份）

| 字段 | 类型 | 空值 | 说明 |
|------|------|------|------|
| `sp_info` | STRING | ~86% | 选科要求文字描述，如"物理、化学(2科必选)"。仅新高考省份 2019 年起有值 |
| `sp_type` | STRING | 部分 | 选科类型编码（API 内部值） |
| `special_group` | STRING | 部分 | 专业组编号 |
| `first_km` | STRING | 部分 | 首选科目编码（物理/历史二选一，新高考 3+1+2 模式） |
| `is_score_range` | STRING | 部分 | 是否为分数区间类型 |
| `min_range` | STRING | ~80% | 最低分区间下限 |
| `min_rank_range` | STRING | ~80% | 最低位次区间 |
| `sg_name` | STRING | 部分 | 专业组名称 |
| `sg_info` | STRING | ~70% | 专业组附加信息 |
| `sg_xuanke` | STRING | 部分 | 专业组选科要求编码 |

---

## dim_school

数据来源：`gaokao.cn/school/{school_id}/info.json`

| 字段 | 类型 | 说明 |
|------|------|------|
| `school_id` | INT | 高校 ID，与 fact_admission_history.school_id 关联 |
| `name` | STRING | 高校全称 |
| `province_name` | STRING | 所在省份 |
| `city_name` | STRING | 所在城市 |
| `type_name` | STRING | 院校类型：综合类/理工类/师范类/财经类/医药类/农林类/政法类/语言类/艺术类/体育类/民族类 |
| `school_nature` | STRING | 办学性质：公办/民办/中外合作办学 |
| `level_name` | STRING | 办学层次：本科/专科（高职） |
| `f985` | INT | 是否 985（1=是，0=否）。全国 39 所 |
| `f211` | INT | 是否 211（1=是，0=否）。全国 116 所，含全部 985 |
| `dual_class` | STRING | 双一流类别：双一流A类/双一流B类/NULL=非双一流。全国 147 所 |
| `num_subject` | INT | 国家一级重点学科数 |
| `num_master` | INT | 一级学科硕士点数 |
| `num_doctor` | INT | 一级学科博士点数 |
| `num_academician` | INT | 两院院士数（中科院+工程院） |
| `ruanke_rank` | INT | 软科综合排名。0=未上榜或500+ |
| `qs_rank` | STRING | QS 世界排名。字符串，含区间如"501-510"。NULL=未上榜 |
| `motto` | STRING | 校训 |
| `address` | STRING | 学校地址 |
| `site` | STRING | 招生官网 URL |

---

## dim_school_rank

数据来源：`gaokao.cn/school/{school_id}/rank.json`

| 字段 | 类型 | 说明 |
|------|------|------|
| `school_id` | INT | 高校 ID |
| `rank_name` | STRING | 榜单名称：软科综合/校友会综合/QS世界/US世界/泰晤士（大陆）/人气值排名 |
| `rank` | STRING | 排名值（字符串，含区间如"501-600"） |

---

## dim_school_special

数据来源：`gaokao.cn/school/{school_id}/special/list.json`

| 字段 | 类型 | 说明 |
|------|------|------|
| `school_id` | INT | 高校 ID |
| `special_id` | STRING | 专业 ID（教育部专业目录编码） |
| `name` | STRING | 专业名称（标准名称） |
| `xueke_rank` | STRING | 教育部学科评估排名（第几名）。来源：第四轮学科评估（2017年） |
| `xueke_rank_score` | STRING | 学科评估等级：A+（前2%）/A（2-5%）/A-（5-10%）/B+（10-20%）/B/B-/C+/C/C- |
| `ruanke_rank` | STRING | 软科中国最好学科排名 |
| `ruanke_level` | STRING | 软科学科等级（A+/A/A-/B+/B/B-/C+/C/C-） |
| `nation_first_class` | INT | 国家一流本科专业（双万计划）：1=是，2=否 |
| `nation_feature` | INT | 国家特色专业：1=是，2=否 |
| `limit_year` | STRING | 标准学制：四年/五年/三年 |

> 注意：数据基于 2017 年第四轮学科评估，第五轮（2022年）结果尚未更新。

---

## dim_university

数据来源：`university_info.csv`（gaokao.cn 高校目录）

| 字段 | 类型 | 说明 |
|------|------|------|
| `school_id` | INT | 高校 ID，与其他表关联 |
| `school_name` | STRING | 高校名称 |
| `province` | STRING | 所在省份 |
| `level` | STRING | 办学层次：普通本科/高职（专科） |
| `national_rank` | INT | 全国热度排名（基于 gaokao.cn 浏览量） |
| `category` | STRING | 院校类型 |
| `category_rank` | INT | 同类院校内排名 |
| `latitude` | DOUBLE | 纬度（WGS84） |
| `longitude` | DOUBLE | 经度（WGS84） |
| `website` | STRING | gaokao.cn 详情页 URL |

> 与 dim_school 的区别：dim_university 覆盖全量 2784 所但字段少；dim_school 含 2564 所但字段更丰富（985/211/排名/院士数等）。

---

## 常用过滤条件速查

```sql
WHERE min_score > 0          -- 过滤无效分数
WHERE min_rank > 0           -- 仅新高考省份有效位次
WHERE zslx_name = '普通类'   -- 排除艺术/体育/保送等特殊类型
WHERE year = 2024            -- 最新年份
WHERE f985 = 1               -- 仅 985 院校（需 JOIN dim_school）
WHERE xueke_rank_score = 'A+' -- 学科评估顶级（需 JOIN dim_school_special）
```
