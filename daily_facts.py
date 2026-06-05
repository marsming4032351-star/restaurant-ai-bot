"""日报富数据资产入库层 (additive fact table)。

把每天的日报从「单日记录」升级为「支撑周报/月报/同比/环比的数据资产」。
- 不改 store_history.csv（V1 周报读取器依赖那 13 列骨架），改写到新的 data/daily_facts.csv。
- 日期维度统一来自 date_dimension.py（单一真相源）。
- 字段口径分清楚：营收语义 / 渠道结构 / 支付结构 / 折扣结构 不混用（req 8/9）。
- 去重与污染防护（req 6）：
    * 同 store + business_date 默认禁止静默覆盖；已存在则阻止写入。
    * 更正需显式 mode='amend' 或 'force_update' + reason，旧记录备份 + 审计日志。
    * source_image_hash 命中其它日期 → 疑似重复截图告警。
    * 截图表头日期 != business_date → 阻止（绝不把 05-31 截图写成 06-01）。
    * 与前一天关键指标完全相同但日期不同 → 疑似日期污染告警。
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from date_dimension import DATA_DIR, derive_date_dimension, load_holiday_calendar

FACTS_PATH = DATA_DIR / "daily_facts.csv"
FACTS_BACKUP_PATH = DATA_DIR / "daily_facts_backup.csv"
FACTS_AUDIT_PATH = DATA_DIR / "daily_facts_audit.csv"

PARSE_VERSION = "facts-1.0"
PIPELINE_VERSION = "v1"

# —— 字段字典（req 8/9）：每个口径字段的业务语义，避免把不同口径当同一口径 —— #
FIELD_DICTIONARY = {
    # 营收语义
    "gross_revenue": "折前营业额（打折前的应收）",
    "net_revenue": "折后/经营营收（实际经营收入口径，store_history.revenue 用此口径）",
    "actual_received": "实收（实际到账金额）",
    "discount_amount": "折扣让利金额",
    "discount_rate": "折扣率 = 1 - 折后/折前",
    "member_recharge": "会员储值（充值，非消费）",
    "member_consumption": "会员消费金额",
    "coupon_amount": "券核销金额",
    "groupbuy_amount": "团购金额（无则留空）",
    # 渠道结构（互斥，加总=整体）
    "dine_in_revenue": "堂食收入",
    "takeaway_revenue": "外带收入",
    "online_revenue": "线上/外卖收入",
    # 支付结构（与渠道结构不同口径，不可混在同一张饼图）
    "member_revenue": "会员价消费",
    "full_price_revenue": "原价消费",
    "discount_revenue": "优惠/折扣消费",
    # 客流与品类
    "customer_count": "客流（客单数）",
    "avg_check": "客单价",
    "roast_duck_sales": "烤鸭销量",
}

# CSV 列顺序：身份 + 日期维度 + 口径字段 + 来源/版本 + 元信息
_DATE_DIM_COLUMNS = [
    "business_year", "business_month", "business_week_start", "business_week_end",
    "day_of_month", "weekday", "weekday_name",
    "is_month_start", "is_month_end", "is_week_start", "is_week_end",
    "is_weekend", "is_workday", "is_holiday", "holiday_name", "is_makeup_workday",
    "previous_day_date", "previous_week_same_weekday_date", "previous_month_same_day_date",
    "month_to_date_start", "month_to_date_end",
    "previous_month_mtd_start", "previous_month_mtd_end",
    "is_cross_month_week", "week_month_coverage",
]
_CALIBER_COLUMNS = list(FIELD_DICTIONARY.keys())
# 节气（确定性，来自 date_dimension → solar_terms 权威表；表外年份记 no_data，不伪造）
_SOLAR_COLUMNS = [
    "solar_term_status", "is_solar_term_day", "solar_term_today",
    "current_solar_term", "current_solar_term_date", "days_into_current_term",
    "next_solar_term", "next_solar_term_date", "days_to_next_term",
]
# 天气（高德, 可降级；business_date 为过去日期时当天天气记"暂无"，不伪造）
_WEATHER_COLUMNS = [
    "weather_status", "weather_city",
    "weather_for_business_date", "business_date_weather_note",
    "live_observed_at", "live_weather", "live_temperature_c", "live_wind",
    "forecast_summary",
]
_SOURCE_COLUMNS = [
    "source_image_filename", "source_image_hash", "source_image_header_date",
    "vlm_confidence", "vlm_model_name", "parse_version", "pipeline_version",
]
FACT_COLUMNS = (
    ["business_date", "store_name"]
    + _DATE_DIM_COLUMNS
    + _SOLAR_COLUMNS
    + _CALIBER_COLUMNS
    + _WEATHER_COLUMNS
    + _SOURCE_COLUMNS
    + ["ingested_at", "ingest_mode"]
)

# 用于污染相似度比较的关键指标
_SIMILARITY_KEYS = ["net_revenue", "gross_revenue", "customer_count", "roast_duck_sales"]


def compute_image_hash(path) -> str:
    """图片 sha256，用于识别重复截图。文件缺失返回空串。"""
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_facts(path=FACTS_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_facts(rows: list[dict], path=FACTS_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FACT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in FACT_COLUMNS})


def _append_audit(entry: dict) -> None:
    p = Path(FACTS_AUDIT_PATH)
    cols = ["timestamp", "store_name", "business_date", "action", "reason", "old_value", "new_value"]
    exists = p.exists()
    with p.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerow({c: entry.get(c, "") for c in cols})


def _backup_record(old: dict) -> None:
    p = Path(FACTS_BACKUP_PATH)
    exists = p.exists()
    cols = ["backed_up_at"] + FACT_COLUMNS
    with p.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if not exists:
            w.writeheader()
        row = {c: old.get(c, "") for c in FACT_COLUMNS}
        row["backed_up_at"] = datetime.now().isoformat(timespec="seconds")
        w.writerow(row)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _summarize_forecast(weather: dict) -> str:
    """把高德预报数组压成一行可读摘要（用于落库/弱参考），无数据返回空串。"""
    casts = weather.get("forecast") or []
    parts = []
    for c in casts[:4]:
        d = c.get("date") or ""
        dw = c.get("day_weather") or ""
        nt = c.get("night_temp_c")
        dt = c.get("day_temp_c")
        if d and dw:
            parts.append(f"{d}:{dw} {nt}~{dt}℃")
    return "; ".join(parts)


def build_fact_record(
    business_date,
    store_name: str,
    metrics: dict | None = None,
    source: dict | None = None,
    holiday_calendar: dict | None = None,
    context: dict | None = None,
) -> dict:
    """组装一条 fact 记录：日期维度（派生）+ 节气 + 口径指标 + 天气 + 来源/版本。

    metrics: 口径字段 dict（键见 FIELD_DICTIONARY），缺失留空不伪造。
    source:  source_image_filename / source_image_hash / source_image_header_date /
             vlm_confidence / vlm_model_name 等。
    context: 运营上下文 dict（main._build_ops_context 产出），含 solar_term / weather。
             节气以 date_dimension 派生为准；天气从 context.weather 落库，缺失记"暂无"。
    """
    metrics = metrics or {}
    source = source or {}
    context = context or {}
    cal = holiday_calendar if holiday_calendar is not None else load_holiday_calendar()
    dim = derive_date_dimension(business_date, cal)

    rec: dict = {"business_date": dim["business_date"], "store_name": store_name}
    for col in _DATE_DIM_COLUMNS:
        val = dim.get(col, "")
        if col == "week_month_coverage":
            val = json.dumps(val, ensure_ascii=False)
        rec[col] = val
    # 节气：以 date_dimension 派生为单一真相源（确定性）
    for col in _SOLAR_COLUMNS:
        rec[col] = dim.get(col, "")
    for col in _CALIBER_COLUMNS:
        rec[col] = metrics.get(col, "")
    # 天气：从 context.weather 落库，缺失/降级记"暂无"，绝不伪造
    weather = context.get("weather") or {}
    rec["weather_status"] = weather.get("weather_status", "")
    rec["weather_city"] = weather.get("weather_city", "")
    rec["weather_for_business_date"] = weather.get("weather_for_business_date", "")
    rec["business_date_weather_note"] = weather.get("business_date_weather_note", "")
    rec["live_observed_at"] = weather.get("live_observed_at") or ""
    rec["live_weather"] = weather.get("live_weather", "")
    rec["live_temperature_c"] = weather.get("live_temperature_c", "")
    rec["live_wind"] = weather.get("live_wind", "")
    rec["forecast_summary"] = _summarize_forecast(weather)
    rec["source_image_filename"] = source.get("source_image_filename", "")
    rec["source_image_hash"] = source.get("source_image_hash", "")
    rec["source_image_header_date"] = source.get("source_image_header_date", "")
    rec["vlm_confidence"] = source.get("vlm_confidence", "")
    rec["vlm_model_name"] = source.get("vlm_model_name", "")
    rec["parse_version"] = source.get("parse_version", PARSE_VERSION)
    rec["pipeline_version"] = source.get("pipeline_version", PIPELINE_VERSION)
    rec["ingested_at"] = datetime.now().isoformat(timespec="seconds")
    rec["ingest_mode"] = ""
    return rec


def detect_pollution(record: dict, rows: list[dict]) -> list[str]:
    """污染/重复检测，返回告警列表（不阻断，由 save_fact 决定是否硬阻止）。"""
    warnings: list[str] = []
    bd = record["business_date"]
    store = record["store_name"]
    header = record.get("source_image_header_date", "")
    img_hash = record.get("source_image_hash", "")

    # 1) 截图表头日期与 business_date 不一致（强阻止信号）
    if header and header != bd:
        warnings.append(
            f"BLOCK: 截图表头日期 {header} 与 business_date {bd} 不一致，疑似把 {header} 的截图写成 {bd}。"
        )

    # 2) 相同图片 hash 命中其它日期
    if img_hash:
        for r in rows:
            if r.get("source_image_hash") == img_hash and r.get("business_date") != bd:
                warnings.append(
                    f"WARN: source_image_hash 与 {r.get('store_name')} {r.get('business_date')} 相同，疑似重复截图。"
                )

    # 3) 与前一天关键指标完全相同但日期不同 → 疑似日期污染
    prev_date = record.get("previous_day_date", "")
    for r in rows:
        if r.get("store_name") != store:
            continue
        if r.get("business_date") != prev_date:
            continue
        same = True
        any_value = False
        for k in _SIMILARITY_KEYS:
            a, b = _num(record.get(k)), _num(r.get(k))
            if a is None or b is None:
                continue
            any_value = True
            if a != b:
                same = False
                break
        if any_value and same:
            warnings.append(
                f"WARN: {bd} 关键指标({', '.join(_SIMILARITY_KEYS)})与前一天 {prev_date} 完全相同，疑似重复截图/日期污染。"
            )
    return warnings


def save_fact(
    record: dict,
    mode: str = "append",
    reason: str = "",
    path=FACTS_PATH,
    allow_pollution: bool = False,
) -> dict:
    """写入 fact 记录，带去重 + 污染防护。

    mode:
      'append'       默认；同 store+business_date 已存在则阻止；表头不符/污染则阻止。
      'amend'/'force_update'  更正；需 reason；旧记录备份 + 审计；可覆盖已存在记录。
    allow_pollution: amend 时即便有污染告警也强制写入（需调用方明确）。

    返回 {status, warnings, record}；status ∈
      written / amended / blocked_duplicate / blocked_pollution / blocked_no_reason
    """
    rows = load_facts(path)
    bd = record["business_date"]
    store = record["store_name"]
    warnings = detect_pollution(record, rows)
    hard_block = [w for w in warnings if w.startswith("BLOCK")]

    existing_idx = next(
        (i for i, r in enumerate(rows)
         if r.get("store_name") == store and r.get("business_date") == bd),
        None,
    )

    is_amend = mode in ("amend", "force_update")

    # 表头不符等硬阻止：默认拦截，除非 amend + allow_pollution
    if hard_block and not (is_amend and allow_pollution):
        return {"status": "blocked_pollution", "warnings": warnings, "record": None}

    if not is_amend:
        if existing_idx is not None:
            warnings.append(
                f"BLOCK: {store} {bd} 已存在 fact 记录；更正请用 mode='amend' + reason，禁止静默覆盖。"
            )
            return {"status": "blocked_duplicate", "warnings": warnings, "record": None}
        record["ingest_mode"] = "append"
        rows.append(record)
        _write_facts(rows, path)
        _append_audit({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "store_name": store, "business_date": bd,
            "action": "append", "reason": reason or "",
            "old_value": "", "new_value": "new_record",
        })
        return {"status": "written", "warnings": warnings, "record": record}

    # amend / force_update
    if not reason:
        return {"status": "blocked_no_reason", "warnings": warnings, "record": None}
    record["ingest_mode"] = mode
    if existing_idx is not None:
        old = rows[existing_idx]
        _backup_record(old)
        _append_audit({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "store_name": store, "business_date": bd,
            "action": mode, "reason": reason,
            "old_value": json.dumps({k: old.get(k) for k in _SIMILARITY_KEYS}, ensure_ascii=False),
            "new_value": json.dumps({k: record.get(k) for k in _SIMILARITY_KEYS}, ensure_ascii=False),
        })
        rows[existing_idx] = record
    else:
        _append_audit({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "store_name": store, "business_date": bd,
            "action": mode + "_new", "reason": reason,
            "old_value": "", "new_value": "new_record",
        })
        rows.append(record)
    _write_facts(rows, path)
    return {"status": "amended", "warnings": warnings, "record": record}
