# 数据字段字典 (data schema)

> 2026-06-01 新增。配合 [`date_and_metric_policy.md`](date_and_metric_policy.md)。
> 入库层 [`daily_facts.py`](../daily_facts.py) 写入 `data/daily_facts.csv`，**不改 `store_history.csv`**（V1 周报骨架）。

---

## 1. 身份字段

| 字段 | 含义 |
|------|------|
| business_date | 业务日期（图片表头来源，YYYY-MM-DD） |
| store_name | 门店名 |

## 2. 日期维度字段（由 `date_dimension.py` 派生）

| 字段 | 含义 |
|------|------|
| business_year / business_month | 年 / `YYYY-MM` |
| business_week_start / business_week_end | 自然周（周一/周日） |
| day_of_month / weekday / weekday_name | 月内第几天 / ISO 星期 / 中文星期 |
| is_month_start / is_month_end / is_week_start / is_week_end | 月初/月末/周一/周日 布尔 |
| is_weekend / is_workday | 周末 / 工作日（含调休） |
| is_holiday / holiday_name / is_makeup_workday | 法定节假日 / 名称 / 调休补班 |
| previous_day_date | 前一天 |
| previous_week_same_weekday_date | 上周同一星期几（−7 天） |
| previous_month_same_day_date | 上月同一天（缺日取上月末） |
| month_to_date_start / month_to_date_end | 本月累计窗口 |
| previous_month_mtd_start / previous_month_mtd_end | 上月同期累计窗口（缺日取上月末） |
| is_cross_month_week / week_month_coverage | 是否跨月周 / 每月覆盖天数与日期(JSON) |

## 3. 口径字段字典（req 8/9，口径不混用）

### 营收语义（不同口径，勿混）
| 字段 | 含义 |
|------|------|
| gross_revenue | 折前营业额（应收） |
| net_revenue | 折后/经营营收（= `store_history.revenue` 口径） |
| actual_received | 实收（实际到账） |
| discount_amount | 折扣让利金额 |
| discount_rate | 折扣率 = 1 − 折后/折前 |
| member_recharge | 会员储值（充值，非消费） |
| member_consumption | 会员消费金额 |
| coupon_amount | 券核销金额 |
| groupbuy_amount | 团购金额（无则留空） |

### 渠道结构（互斥，加总=整体）
| 字段 | 含义 |
|------|------|
| dine_in_revenue | 堂食收入 |
| takeaway_revenue | 外带收入 |
| online_revenue | 线上/外卖收入 |

### 支付结构（与渠道结构是不同口径，不可并入同一张饼图）
| 字段 | 含义 |
|------|------|
| member_revenue | 会员价消费 |
| full_price_revenue | 原价消费 |
| discount_revenue | 优惠/折扣消费 |

### 客流与品类
| 字段 | 含义 |
|------|------|
| customer_count | 客流（客单数） |
| avg_check | 客单价 |
| roast_duck_sales | 烤鸭销量 |

> ⚠️ 口径分层：**营收语义 / 渠道结构 / 支付结构 / 折扣结构** 是四套不同口径。
> 例如「优惠消费」属于支付结构，不能和「堂食/外卖/线上」（渠道结构）放进同一张饼图当成同口径。

## 3.5 运营上下文：节气 + 天气（2026-06-05 新增，附加层）

> 这两组字段是**附加运营上下文**，由 `main._build_ops_context(business_date)` 产出，
> 经 `daily.context` 注入日报 JSON，再由 `daily_facts.build_fact_record(..., context=...)` 落库。
> 任何失败都不阻断 V1 主流程；缺数据时诚实记 `no_data` / `暂无`，**绝不伪造**。

### 节气（确定性，单一真相源 = `data/solar_terms_cn.json`）
经 `date_dimension.py` → `solar_terms.py` 派生；表外年份记 `no_data`，不用公式近似。

| 字段 | 含义 |
|------|------|
| solar_term_status | `ok` / `no_data`（该年节气表未覆盖） |
| is_solar_term_day | 当天是否恰逢节气 |
| solar_term_today | 当天恰逢的节气名（否则空） |
| current_solar_term / current_solar_term_date | 当前所处节气及其日期 |
| days_into_current_term | 距当前节气已过天数（节气当天=0） |
| next_solar_term / next_solar_term_date / days_to_next_term | 下一个节气、日期、剩余天数 |

### 天气（高德，可降级）
高德免费版无历史天气；`business_date` 通常是过去日期，故**当日天气多记"暂无"**，
仅把采集时刻实况与预报作为弱参考，绝不把采集日天气当成业务日天气。

| 字段 | 含义 |
|------|------|
| weather_status | `ok` / `unavailable` / `error` |
| weather_city | 天气城市（默认北京市西城区，马连道所在） |
| weather_for_business_date | 业务日当天天气；过去日期记"暂无（无历史天气）" |
| business_date_weather_note | 业务日天气口径说明（为何暂无） |
| live_observed_at / live_weather / live_temperature_c / live_wind | 采集时刻实况（弱参考） |
| forecast_summary | 采集日及未来数天预报摘要（用于明日经营建议弱参考） |

## 4. 来源与版本字段（req 7）

| 字段 | 含义 |
|------|------|
| source_image_filename | 来源截图文件名 |
| source_image_hash | 截图 sha256，用于识别重复截图 |
| source_image_header_date | 截图表头识别出的业务日期 |
| vlm_confidence | 识别置信度（可得时填，否则留空） |
| vlm_model_name | 识别模型名 |
| parse_version / pipeline_version | 解析版本 / 管线版本 |
| ingested_at / ingest_mode | 入库时间 / 入库方式（append/amend/force_update） |

## 5. 审计与备份

- `data/daily_facts_audit.csv`：每次写入/更正的 timestamp、action、reason、old_value、new_value。
- `data/daily_facts_backup.csv`：更正前旧记录的完整快照。

## 6. 单日记录 → 数据资产

新增这些字段后，每条日报从「单日记录」升级为支撑**周报 / 月报 / 同比 / 环比 / 诊断**的数据资产：日期维度让任意周期聚合无需临时推断；对比基准与 MTD 窗口让同比环比口径统一；来源/版本与去重审计让数据可信、可追溯、防污染。
