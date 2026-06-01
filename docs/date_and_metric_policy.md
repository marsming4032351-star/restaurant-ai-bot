# 日期与数据口径治理规范 (date & metric policy)

> 2026-06-01 新增。为 6 月起的周报、月报、同比、环比分析建立统一口径。
> 核心思想：每天的日报不再是「单日记录」，而是「支撑周报/月报/同比/环比/诊断的数据资产」。

---

## 1. 单一真相源

所有日期维度字段、对比基准日期、月累计(MTD)窗口、跨月周覆盖，都是 `business_date` 的**纯函数**，统一在 [`date_dimension.py`](../date_dimension.py) 派生。

周报 / 月报 / 看板读取器**必须**从这里取字段，不允许各自用系统日期 (`date.today()` / `datetime.now()`) 临时推断。

## 2. business_date 来源铁律

- `business_date` 只能来自**图片表头 / 真实营业数据**。
- ❌ 系统运行日期、文件创建日期、监听日期一律不得覆盖业务日期。
- 图片表头日期识别失败 → **立即中止**，不 fallback。
- 传入参数 `--date` 只作为 `processing_date`；与表头不一致时**以表头为准**并记录 `date_validation_status=warning_processing_date_differs`。

## 3. 日期维度字段（派生）

`derive_date_dimension(business_date)` 输出：

| 字段 | 含义 |
|------|------|
| business_year / business_month | 年 / `YYYY-MM` |
| business_week_start / business_week_end | 自然周（周一~周日） |
| day_of_month / weekday / weekday_name | 月内第几天 / ISO 星期(1=周一) / 中文星期 |
| is_month_start / is_month_end | 是否月初 / 月末 |
| is_week_start / is_week_end | 是否周一 / 周日 |
| is_weekend / is_workday | 是否周末 / 工作日（含调休逻辑） |
| is_holiday / holiday_name / is_makeup_workday | 法定节假日 / 名称 / 调休补班 |

节假日来自配置文件 [`data/holiday_calendar_cn.json`](../data/holiday_calendar_cn.json)，**config-driven，不在代码硬编码、不自动推断农历**。缺失即按「周一至周五=工作日，周六日=休息日」默认，不伪造。

## 4. 对比基准日期

| 字段 | 规则 |
|------|------|
| previous_day_date | business_date − 1 天 |
| previous_week_same_weekday_date | business_date − 7 天（上周同一星期几） |
| previous_month_same_day_date | 上月同一天；上月无此日 → 上月最后一天 |

## 5. 月累计 (MTD) 与上月同期口径

- **本月累计** `month_to_date_start ~ month_to_date_end` = 本月 1 号 → `business_date`。
- **上月同期累计** `previous_month_mtd_start ~ previous_month_mtd_end` = 上月 1 号 → 上月对应第 N 天。
- **缺日规则**：上月没有对应第 N 天（如 3/31 对应 2 月）→ 取**上月最后一天**（2026 年非闰年 → 2026-02-28）。不报错、不乱填。

示例（2026-06-01，6 月第 1 天）：
```
month_to_date        = 2026-06-01 ~ 2026-06-01
previous_month_mtd   = 2026-05-01 ~ 2026-05-01
previous_week_same_weekday = 2026-05-25
```

## 6. 周报 vs 月报口径，不混用

- **周报**口径 = 自然周（周一~周日）。
- **月报**口径 = `business_month`。
- **跨月周**（如 2026-06-29 ~ 2026-07-05）由 `week_month_coverage` 标注每月覆盖的天数与日期，`is_cross_month_week=true`。周统计仍按自然周，月统计仍按 business_month，二者不互相污染。

## 7. 入库去重与污染防护

入库层 [`daily_facts.py`](../daily_facts.py) 写入新表 `data/daily_facts.csv`（**不动 `store_history.csv`**），规则：

1. 同 `store + business_date` 默认**禁止静默覆盖**；已存在则阻止（`blocked_duplicate`）。
2. 更正需显式 `mode='amend'`（或 `force_update`）+ `reason`；旧记录备份到 `daily_facts_backup.csv`，审计写入 `daily_facts_audit.csv`（旧值/新值/原因/时间戳）。
3. **截图表头日期 ≠ business_date → 硬阻止**（`BLOCK`），绝不把 05-31 截图写成 06-01。
4. `source_image_hash` 命中其它日期 → 疑似重复截图告警。
5. 与前一天关键指标（net_revenue/gross_revenue/customer_count/roast_duck_sales）完全相同但日期不同 → 疑似日期污染告警。

## 8. 月度能力

[`monthly_metrics.py`](../monthly_metrics.py)（**只读**聚合，不写业务数据）提供：本月累计营收/客流、日均、客单价、折扣率、烤鸭、工作日均/周末均、最高/最低/异常日、上月同期对比、环比 MoM、数据完整度说明。缺失日期不补全、不伪造。

## 9. 本任务边界

本次治理**只改代码与文档**：不修改历史业务数据、不伪造 6 月数据、不推送飞书、不生成正式日报、不影响周报标准 V1，原流程可回退（富字段入库为 try/except 包裹的附加层）。
