---
name: weekly_dashboard
description: Generate an ECharts-style weekly restaurant operations dashboard from verified weekly report data, export HTML/PNG, and optionally push the dashboard image to Feishu without modifying business data.
---

# 周报可视化看板 Skill

> ⚠️ **周报默认标准已固定为 V1（2026-06-01）**：自动周报默认生成 **融合版“经营大屏 + 管理诊断”高清长图看板**（结构与导出参数已锁定，不再增加模块）（`scripts/render_manager_weekly_fusion.py`）：先生成固定 1600px 宽的「长图导出画布」HTML，再用本机 Chrome 无头两遍法整页截图成高清长图 PNG（默认 viewport 1600 / deviceScaleFactor 2）推送飞书。本 skill 现在是 **fallback**——当融合版脚本不存在、本机无 Chrome 且 PIL 兜底也失败时，`weekly_auto.py` 才回退到这里。手动单独生成基础看板仍可使用本 skill。

## 用途

把已经验证过的周报数据渲染成餐饮经营大屏风格看板，用于飞书汇报、经营复盘和周报增强展示。

该 skill 是“周报数据可视化增强层”，不改变现有日报/周报数据逻辑，不写入、不覆盖、不修正任何真实业务数据。

当前版本新增 `weekly field enhancer`：优先读取 `output/report_*.json` 中的日报结构化字段，再结合 `field_map.yaml` 和 `store_history.csv`，生成更完整的经营管理看板。字段缺失时显示 `暂无` 或隐藏对应模块，不伪造数据。

## 输入

- 门店名：例如 `便宜坊马连道`
- 周报统计区间：`--start-date YYYY-MM-DD` 与 `--end-date YYYY-MM-DD`
- 数据来源优先级：`output/report_*.json` -> `field_map.yaml` -> `data/store_history.csv`
- 其中 `store_history.csv` 仍然是周报骨架，`report_*.json` 提供更丰富的经营字段

业务日期规则：
- 日报 `business_date` 仍然只能来自图片表头日期。
- 系统日期、文件创建日期、监听日期不能覆盖业务日期。
- 本 skill 必须显式传入周报区间，不允许用 `date.today()` 或 `datetime.now()` 推断业务周。

## 输出

- `output/weekly_dashboard_<store_name>_<start_date>_<end_date>.html`
- `output/weekly_dashboard_<store_name>_<start_date>_<end_date>.png`

看板默认 16:9 横版，深色科技感背景，蓝紫主色，适合飞书图片推送。

默认看板模块包含：
- 核心 KPI
- 每日营业额 + 客流双轴趋势
- 收入结构
- 客单价趋势
- 堂食 / 外卖 / 线上收入对比
- 会员与活动
- 关键品类销量 TOP
- 烤鸭专项分析
- 底部经营诊断

## 调用方式

```bash
python3 skills/weekly_dashboard/render_weekly_dashboard.py \
  --store "便宜坊马连道" \
  --start-date 2026-05-25 \
  --end-date 2026-05-31
```

可选参数：

```bash
--history-path data/store_history.csv
--output-dir output
--strict-weekly-date-check
--send-to-feishu
```

`--send-to-feishu` 只在 PNG 生成成功后，复用项目现有飞书推送逻辑发送“标题 + 说明 + 看板图片”；默认不推送。历史兼容参数 `--push-feishu` 仍可用，但新流程统一使用 `--send-to-feishu`。

## 日期校验

- 看板标题和文件名必须使用传入的周报统计区间。
- 周报统计区间必须来自 `weekly_report` 或 `weekly_auto` 的结果。
- 如果发现缺失日期，看板必须显示“缺失日期提示”，不得伪造数据。
- `STRICT_WEEKLY_DATE_CHECK=true` 或传入 `--strict-weekly-date-check` 时，缺失日期会阻止生成推送图片。

## 图表模块

- 本周每日营业额柱状图
- 本周每日客流折线图
- 本周营业额趋势面积图
- 本周收入结构饼图；无结构数据时显示“暂无分类数据”
- TOP 指标横向条形图；菜品数据不足时使用每日营业额排行
- 一周经营强弱极坐标图
- 核心 KPI 卡片：总营业额、日均营业额、最高/最低营业日、周报天数、缺失日期

## 注意事项

- 只读取周报数据，不修改 `store_history.csv`、`pipeline_log.csv` 或任何业务日期。
- 自动周报默认走融合版看板；本 skill 仅作为融合版失败时的 fallback 被 `weekly_auto.py` 调用。
- 不传 `--send-to-feishu` 时只生成 HTML/PNG，不调用飞书推送。
- 传 `--send-to-feishu` 时必须先成功生成 PNG；PNG 不存在时中止推送。
- 不打印 `.env`、webhook、token、app secret 等敏感信息。
- 日期口径单一真相源为 `date_dimension.py`（2026-06-01 新增）：周报/月报/看板的日期维度（自然周、MTD、跨月周、上月同期等）应优先取该模块派生值，不要用 `date.today()` 临时推断。跨月周由 `week_month_coverage` 标注，周统计按自然周、月统计按 `business_month`，不混用。详见 `docs/date_and_metric_policy.md`、`docs/data_schema.md`。
