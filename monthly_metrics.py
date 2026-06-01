"""月报 MTD 指标能力（只读聚合，不写业务数据）。

为 6 月起的月报 / 同比环比做准备。数据源（只读）：
  data/store_history.csv（连续骨架：revenue/customer_count/avg_ticket/discount_rate/roast_duck_sales）
  data/daily_facts.csv（富字段，可选补充，存在即用）
日期维度统一来自 date_dimension.py。本模块不改任何业务数据、不推送飞书。

口径说明：
  - 本月累计(MTD) = 本月 1 号 → business_date。
  - 上月同期 = 上月 1 号 → 上月对应第 N 天（缺日取上月最后一天，见 date_dimension）。
  - 周报口径=自然周，月报口径=business_month，二者不混用（跨月周见 date_dimension.week_month_coverage）。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from date_dimension import (
    DATA_DIR,
    derive_date_dimension,
    load_holiday_calendar,
    monthly_caliber_hint,
    parse_date,
)

STORE_HISTORY_PATH = DATA_DIR / "store_history.csv"
DAILY_FACTS_PATH = DATA_DIR / "daily_facts.csv"

ABNORMAL_LOW_RATIO = 0.7   # 低于月均 70% 记为异常低
ABNORMAL_HIGH_RATIO = 1.5  # 高于月均 150% 记为异常高


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_daily_rows(store: str) -> dict[str, dict]:
    """合并 store_history + daily_facts，按 business_date 索引（facts 优先补充）。"""
    by_date: dict[str, dict] = {}
    for r in _load_csv(STORE_HISTORY_PATH):
        if store and r.get("store_name") != store:
            continue
        d = r.get("date")
        if not d:
            continue
        by_date[d] = {
            "date": d,
            "revenue": _num(r.get("revenue")),
            "customer_count": _num(r.get("customer_count")),
            "avg_ticket": _num(r.get("avg_ticket")),
            "discount_rate": _num(r.get("discount_rate")),
            "roast_duck_sales": _num(r.get("roast_duck_sales")),
        }
    for r in _load_csv(DAILY_FACTS_PATH):
        if store and r.get("store_name") != store:
            continue
        d = r.get("business_date")
        if not d:
            continue
        cur = by_date.setdefault(d, {"date": d})
        # facts 的 net_revenue 视作 revenue 口径；只在 store_history 缺值时补
        for src, dst in [("net_revenue", "revenue"), ("customer_count", "customer_count"),
                         ("avg_check", "avg_ticket"), ("discount_rate", "discount_rate"),
                         ("roast_duck_sales", "roast_duck_sales")]:
            v = _num(r.get(src))
            if v is not None and cur.get(dst) is None:
                cur[dst] = v
    return by_date


def _rows_in_window(by_date: dict[str, dict], start: str, end: str) -> list[dict]:
    s, e = parse_date(start), parse_date(end)
    out = []
    for d, row in by_date.items():
        try:
            dd = parse_date(d)
        except ValueError:
            continue
        if s <= dd <= e:
            out.append(row)
    return sorted(out, key=lambda r: r["date"])


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _sum(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals), 2) if vals else None


def aggregate_window(rows: list[dict], cal: dict) -> dict:
    """对窗口内日报行做聚合，含工作日/周末拆分、最高/最低/异常日。"""
    present = [r for r in rows if r.get("revenue") is not None]
    revenues = [r["revenue"] for r in present]
    total_rev = _sum(revenues)
    daily_avg = _avg(revenues)

    workday_rev, weekend_rev = [], []
    for r in present:
        dim = derive_date_dimension(r["date"], cal)
        (workday_rev if dim["is_workday"] else weekend_rev).append(r["revenue"])

    highest = max(present, key=lambda r: r["revenue"], default=None)
    lowest = min(present, key=lambda r: r["revenue"], default=None)

    abnormal = []
    if daily_avg:
        for r in present:
            ratio = r["revenue"] / daily_avg if daily_avg else None
            if ratio is not None and (ratio < ABNORMAL_LOW_RATIO or ratio > ABNORMAL_HIGH_RATIO):
                abnormal.append({"date": r["date"], "revenue": r["revenue"], "ratio": round(ratio, 2)})

    return {
        "days_present": len(present),
        "total_revenue": total_rev,
        "total_customers": _sum([r.get("customer_count") for r in present]),
        "daily_avg_revenue": daily_avg,
        "avg_ticket": _avg([r.get("avg_ticket") for r in present]),
        "avg_discount_rate": _avg([r.get("discount_rate") for r in present]),
        "total_roast_duck": _sum([r.get("roast_duck_sales") for r in present]),
        "workday_avg_revenue": _avg(workday_rev),
        "weekend_avg_revenue": _avg(weekend_rev),
        "workday_days": len(workday_rev),
        "weekend_days": len(weekend_rev),
        "highest_day": {"date": highest["date"], "revenue": highest["revenue"]} if highest else None,
        "lowest_day": {"date": lowest["date"], "revenue": lowest["revenue"]} if lowest else None,
        "abnormal_days": abnormal,
    }


def _pct_delta(cur, base):
    if cur is None or base in (None, 0):
        return None
    return round((cur - base) / base * 100, 2)


def monthly_metrics(business_date, store: str = "便宜坊马连道", holiday_calendar: dict | None = None) -> dict:
    """计算指定 business_date 的本月 MTD 指标 + 上月同期对比 + 环比。只读。"""
    cal = holiday_calendar if holiday_calendar is not None else load_holiday_calendar()
    dim = derive_date_dimension(business_date, cal)
    by_date = load_daily_rows(store)

    mtd_rows = _rows_in_window(by_date, dim["month_to_date_start"], dim["month_to_date_end"])
    pm_rows = _rows_in_window(by_date, dim["previous_month_mtd_start"], dim["previous_month_mtd_end"])

    mtd = aggregate_window(mtd_rows, cal)
    pm = aggregate_window(pm_rows, cal)

    mom = {
        "total_revenue_mom_pct": _pct_delta(mtd["total_revenue"], pm["total_revenue"]),
        "total_customers_mom_pct": _pct_delta(mtd["total_customers"], pm["total_customers"]),
        "daily_avg_revenue_mom_pct": _pct_delta(mtd["daily_avg_revenue"], pm["daily_avg_revenue"]),
    }

    return {
        "store_name": store,
        "business_date": dim["business_date"],
        "business_month": dim["business_month"],
        "mtd_window": [dim["month_to_date_start"], dim["month_to_date_end"]],
        "previous_month_mtd_window": [dim["previous_month_mtd_start"], dim["previous_month_mtd_end"]],
        "is_cross_month_week": dim["is_cross_month_week"],
        "week_month_coverage": dim["week_month_coverage"],
        "mtd": mtd,
        "previous_month_same_period": pm,
        "mom_comparison": mom,
        "caliber_hint": monthly_caliber_hint(business_date, cal),
        "data_completeness_note": (
            f"本月已入库 {mtd['days_present']} 天；上月同期 {pm['days_present']} 天。"
            "缺失日期不补全、不伪造，比较口径以实际入库日期为准。"
        ),
    }


if __name__ == "__main__":
    import sys
    bd = sys.argv[1] if len(sys.argv) > 1 else "2026-06-01"
    store = sys.argv[2] if len(sys.argv) > 2 else "便宜坊马连道"
    print(json.dumps(monthly_metrics(bd, store), ensure_ascii=False, indent=2))
