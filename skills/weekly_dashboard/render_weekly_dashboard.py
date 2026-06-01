#!/usr/bin/env python3
"""Render a weekly restaurant dashboard from verified store_history.csv data."""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import sys
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path
from functools import lru_cache
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import weekly_report
import yaml


WIDTH = 1600
HEIGHT = 900
FIELD_MAP_PATH = ROOT_DIR / "field_map.yaml"


@lru_cache(maxsize=1)
def load_field_map() -> dict:
    if not FIELD_MAP_PATH.exists():
        return {}
    return yaml.safe_load(FIELD_MAP_PATH.read_text(encoding="utf-8")) or {}


def parse_date(value: str | None, field_name: str) -> date:
    if not value:
        raise ValueError(f"必须显式传入 {field_name}，不能用系统日期推断周报区间")
    return date.fromisoformat(value)


def safe_name(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\\s]+", "_", value.strip())


def output_paths(store: str, start: date, end: date, output_dir: Path) -> tuple[Path, Path]:
    stem = f"weekly_dashboard_{safe_name(store)}_{start}_{end}"
    return output_dir / f"{stem}.html", output_dir / f"{stem}.png"


def expected_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end-date 不能早于 start-date")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def load_rows(store: str, start: date, end: date, history_path: Path) -> list[dict]:
    if not history_path.exists():
        raise FileNotFoundError(f"找不到历史数据文件: {history_path}")
    rows = []
    with history_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                row_date = date.fromisoformat(row.get("date", ""))
            except ValueError:
                continue
            if row.get("store_name", "").strip() != store.strip():
                continue
            if start <= row_date <= end:
                rows.append({**row, "_date": row_date})
    rows.sort(key=lambda r: r["_date"])
    return rows


def load_report_payloads(
    store: str,
    start: date,
    end: date,
    output_dir: Path | None = None,
) -> dict[str, dict]:
    output = Path(output_dir) if output_dir else config.OUTPUT_DIR
    payloads: dict[str, dict] = {}
    if not output.exists():
        return payloads

    for path in output.glob("report_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        daily = payload.get("daily", {})
        meta = daily.get("meta", {})
        business_date = meta.get("date")
        store_name = meta.get("store_name", "")
        if store_name.strip() != store.strip():
            continue
        try:
            row_date = date.fromisoformat(str(business_date))
        except ValueError:
            continue
        if start <= row_date <= end:
            payloads[str(row_date)] = payload
    return payloads


def as_float(row: dict, key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _value_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _coerce_display_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    coerced = _value_or_none(value)
    return coerced if coerced is not None else None


def _extract_report_values(payload: dict) -> dict:
    daily = payload.get("daily", {})
    revenue = daily.get("revenue", {})
    member = daily.get("member_consumption", {})
    traffic = daily.get("traffic", {})
    dishes = daily.get("dishes_by_category", {})
    derived = daily.get("derived", {})
    duck = dishes.get("烤鸭类", {})
    set_meal = dishes.get("套餐类", {})
    fish = dishes.get("鱼类_牛掌", {})
    dessert = dishes.get("位吃_甜品", {})
    def pick(section: dict, key: str) -> float | None:
        return _value_or_none(section.get(key))

    values = {
        "date": daily.get("meta", {}).get("date"),
        "store_name": daily.get("meta", {}).get("store_name"),
        "revenue_today": pick(revenue, "revenue_today"),
        "revenue_today_before_discount": pick(revenue, "revenue_today_before_discount"),
        "revenue_month_to_date": pick(revenue, "revenue_month_to_date"),
        "revenue_mtd_before_discount": pick(revenue, "revenue_mtd_before_discount"),
        "revenue_same_period_last_year": pick(revenue, "revenue_same_period_last_year"),
        "revenue_yoy_delta": pick(revenue, "revenue_yoy_delta"),
        "dine_in_revenue": pick(revenue, "dine_in_revenue"),
        "takeaway_revenue": pick(revenue, "dine_in_takeaway_revenue"),
        "online_revenue": pick(revenue, "online_takeaway_revenue"),
        "member_recharge": pick(revenue, "member_recharge_today"),
        "member_recharge_mtd": pick(revenue, "member_recharge_mtd"),
        "free_amount": pick(revenue, "free_amount"),
        "purchase_amount": pick(revenue, "purchase_amount"),
        "member_revenue": pick(member, "member_revenue"),
        "full_price_revenue": pick(member, "full_price_revenue"),
        "discount_revenue": pick(member, "discount_revenue"),
        "member_revenue_ratio": pick(member, "member_revenue_ratio"),
        "full_price_ratio": pick(member, "full_price_ratio"),
        "discount_ratio": pick(member, "discount_ratio"),
        "customer_count": pick(traffic, "customer_count"),
        "avg_ticket": pick(traffic, "avg_check"),
        "rebate_coupon": pick(traffic, "rebate_coupon_issued"),
        "coupon_verify": pick(traffic, "rebate_coupon_redeemed"),
        "coupon_recycle": pick(traffic, "cash_coupon_redeemed"),
        "coupon_revenue": pick(traffic, "coupon_revenue"),
        "cash_coupon_revenue": pick(traffic, "cash_coupon_revenue"),
        "duck_total": pick(derived, "duck_total"),
        "set_meal_total": pick(derived, "set_meal_total"),
        "dine_in_share": pick(derived, "dine_in_share"),
        "takeaway_share": pick(derived, "takeaway_share"),
        "online_share": pick(derived, "online_share"),
        "discount_rate": pick(derived, "discount_rate"),
        "effective_price_ratio": pick(derived, "effective_price_ratio"),
        "yoy_pct": pick(derived, "yoy_pct"),
        "roasted_duck_dine_in": pick(duck, "roasted_duck_dine_in"),
        "mini_duck": pick(duck, "mini_duck"),
        "roasted_duck_online": pick(duck, "roasted_duck_online"),
        "spiced_duck_rack": pick(duck, "spiced_duck_rack"),
        "duck_sauce": pick(duck, "duck_sauce"),
        "sesame_cake": pick(duck, "sesame_cake"),
        "duck_rack_ratio": pick(duck, "duck_rack_ratio"),
        "sesame_cake_ratio": pick(duck, "sesame_cake_ratio"),
        "set_meal_3p": pick(set_meal, "set_meal_3p"),
        "set_meal_6p": pick(set_meal, "set_meal_6p"),
        "set_meal_8p": pick(set_meal, "set_meal_8p"),
        "set_meal_10p": pick(set_meal, "set_meal_10p"),
        "set_meal_12p": pick(set_meal, "set_meal_12p"),
        "crab_set_meal": pick(set_meal, "crab_set_meal"),
        "pigeon": pick(set_meal, "pigeon"),
        "mandarin_fish": pick(fish, "mandarin_fish"),
        "fish_total": pick(fish, "fish_total"),
        "sea_cucumber_beef_paw": pick(fish, "sea_cucumber_beef_paw"),
        "dessert": pick(dessert, "dessert"),
        "per_seat_dish": pick(dessert, "per_seat_dish"),
        "sweet": pick(dessert, "sweet"),
        "house_drink": pick(dessert, "house_drink"),
        "craft_beer": pick(dessert, "craft_beer"),
    }

    return values


def _sum_present(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    return round(sum(values), 2)


def _weighted_average(rows: list[dict], value_key: str, weight_key: str) -> float | None:
    weighted = 0.0
    total_weight = 0.0
    for row in rows:
        value = row.get(value_key)
        weight = row.get(weight_key)
        if value is None or weight in (None, 0):
            continue
        weighted += float(value) * float(weight)
        total_weight += float(weight)
    if total_weight == 0:
        return None
    return round(weighted / total_weight, 4)


def _latest_present(rows: list[dict], key: str) -> float | None:
    for row in reversed(rows):
        value = row.get(key)
        if value is not None:
            return value
    return None


def _build_category_totals(rows: list[dict]) -> dict[str, float | None]:
    categories = OrderedDict(
        [
            ("烤鸭", ["duck_total"]),
            ("烧饼", ["sesame_cake"]),
            ("鱼类+牛羊", ["fish_total", "sea_cucumber_beef_paw"]),
            ("位吃+甜品", ["per_seat_dish", "dessert", "sweet"]),
            ("套餐", ["set_meal_total"]),
            ("乳鸽", ["pigeon"]),
            ("自制饮品", ["house_drink"]),
            ("精酿", ["craft_beer"]),
        ]
    )
    totals = {}
    for name, keys in categories.items():
        value = 0.0
        has_value = False
        for key in keys:
            for row in rows:
                item = row.get(key)
                if item is None:
                    continue
                has_value = True
                value += float(item)
        totals[name] = round(value, 2) if has_value else None
    return totals


def load_weekly_enriched_fields(
    store: str,
    start_date: str,
    end_date: str,
    *,
    history_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    start = parse_date(start_date, "start-date")
    end = parse_date(end_date, "end-date")
    history = Path(history_path) if history_path else config.DATA_DIR / "store_history.csv"
    field_map = load_field_map()

    rows = load_rows(store, start, end, history)
    report_payloads = load_report_payloads(store, start, end, output_dir)
    report_by_date = {}
    for report_date, payload in report_payloads.items():
        report_by_date[report_date] = _extract_report_values(payload)

    expected = expected_dates(start, end)
    row_by_date = {row["_date"]: row for row in rows}
    daily: list[dict] = []
    for day in expected:
        date_str = str(day)
        history_row = row_by_date.get(day, {})
        report_row = report_by_date.get(date_str, {})
        merged = {
            "date": date_str,
            "store_name": store,
            "has_history": day in row_by_date,
            "has_report": date_str in report_by_date,
            "revenue": _coerce_display_number(history_row.get("revenue")),
            "customer_count": _coerce_display_number(history_row.get("customer_count")),
            "avg_ticket": _coerce_display_number(history_row.get("avg_ticket")),
            "month_yoy": _coerce_display_number(history_row.get("month_yoy")),
            "discount_rate_history": _coerce_display_number(history_row.get("discount_rate")),
            "dine_in_ratio_history": _coerce_display_number(history_row.get("dine_in_ratio")),
            "takeaway_ratio_history": _coerce_display_number(history_row.get("takeaway_ratio")),
            "roast_duck_sales": _coerce_display_number(history_row.get("roast_duck_sales")),
            "warning_level": history_row.get("warning_level") or None,
            "summary": history_row.get("summary") or None,
            "suggestions": history_row.get("suggestions") or None,
        }
        merged.update(report_row)
        preferred_overrides = {
            "revenue": report_row.get("revenue_today"),
            "customer_count": report_row.get("customer_count"),
            "avg_ticket": report_row.get("avg_check"),
            "roast_duck_sales": report_row.get("duck_total"),
            "member_recharge": report_row.get("member_recharge"),
            "member_recharge_mtd": report_row.get("member_recharge_mtd"),
            "dine_in_revenue": report_row.get("dine_in_revenue"),
            "takeaway_revenue": report_row.get("takeaway_revenue"),
            "online_revenue": report_row.get("online_revenue"),
            "discount_revenue": report_row.get("discount_revenue"),
            "dine_in_share": report_row.get("dine_in_share"),
            "takeaway_share": report_row.get("takeaway_share"),
            "online_share": report_row.get("online_share"),
            "discount_rate": report_row.get("discount_rate"),
            "duck_total": report_row.get("duck_total"),
            "set_meal_total": report_row.get("set_meal_total"),
            "duck_dine_in": report_row.get("roasted_duck_dine_in"),
            "duck_online": report_row.get("roasted_duck_online"),
            "duck_mini": report_row.get("mini_duck"),
            "duck_sauce": report_row.get("duck_sauce"),
            "sesame_cake": report_row.get("sesame_cake"),
            "duck_rack_ratio": report_row.get("duck_rack_ratio"),
            "sesame_cake_ratio": report_row.get("sesame_cake_ratio"),
        }
        for target_key, preferred_value in preferred_overrides.items():
            if preferred_value is not None:
                merged[target_key] = preferred_value
        if merged.get("discount_rate") is None and merged.get("discount_ratio") is not None:
            merged["discount_rate"] = merged["discount_ratio"] * 100 if merged["discount_ratio"] <= 1 else merged["discount_ratio"]
        if merged.get("dine_in_share") is None and merged.get("dine_in_ratio_history") is not None:
            merged["dine_in_share"] = merged["dine_in_ratio_history"] / 100 if merged["dine_in_ratio_history"] > 1 else merged["dine_in_ratio_history"]
        if merged.get("takeaway_share") is None and merged.get("takeaway_ratio_history") is not None:
            merged["takeaway_share"] = merged["takeaway_ratio_history"] / 100 if merged["takeaway_ratio_history"] > 1 else merged["takeaway_ratio_history"]
        if merged.get("online_share") is None and merged.get("online_revenue") is not None and merged.get("revenue_today") is not None:
            merged["online_share"] = round(float(merged["online_revenue"]) / float(merged["revenue_today"]), 4) if merged["revenue_today"] else 0.0
        daily.append(merged)

    weekly_revenue = _sum_present(daily, "revenue")
    weekly_customers = _sum_present(daily, "customer_count")
    weekly_avg_ticket = round(weekly_revenue / weekly_customers, 2) if weekly_revenue is not None and weekly_customers not in (None, 0) else (0.0 if weekly_revenue == 0 and weekly_customers else None)
    weekly_dine_in = _sum_present(daily, "dine_in_revenue")
    weekly_takeaway = _sum_present(daily, "takeaway_revenue")
    weekly_online = _sum_present(daily, "online_revenue")
    weekly_discount = _sum_present(daily, "discount_revenue")
    weekly_before_discount = _sum_present(daily, "revenue_today_before_discount")
    weekly_member_recharge = _sum_present(daily, "member_recharge")
    weekly_member_recharge_mtd = _latest_present(daily, "member_recharge_mtd")
    weekly_coupon_revenue = _sum_present(daily, "coupon_revenue")
    weekly_coupon_verify = _sum_present(daily, "coupon_verify")
    weekly_coupon_recycle = _sum_present(daily, "coupon_recycle")
    weekly_rebate_coupon = _sum_present(daily, "rebate_coupon")
    weekly_child_card_issue = _sum_present(daily, "child_card_issue")
    weekly_child_card_total = _sum_present(daily, "child_card_total")
    weekly_duck_total = _sum_present(daily, "duck_total")
    weekly_duck_dine_in = _sum_present(daily, "roasted_duck_dine_in")
    weekly_duck_online = _sum_present(daily, "roasted_duck_online")
    weekly_duck_mini = _sum_present(daily, "mini_duck")
    weekly_duck_sauce = _sum_present(daily, "duck_sauce")
    weekly_sesame_cake = _sum_present(daily, "sesame_cake")
    weekly_duck_rack_ratio = _weighted_average(daily, "duck_rack_ratio", "duck_total")
    weekly_sesame_cake_ratio = _weighted_average(daily, "sesame_cake_ratio", "duck_total")

    weekly = {
        "revenue_total": weekly_revenue,
        "customer_total": weekly_customers,
        "avg_ticket": weekly_avg_ticket,
        "dine_in_revenue": weekly_dine_in,
        "takeaway_revenue": weekly_takeaway,
        "online_revenue": weekly_online,
        "discount_revenue": weekly_discount,
        "revenue_before_discount": weekly_before_discount,
        "dine_in_share": round(weekly_dine_in / weekly_revenue, 4) if weekly_dine_in is not None and weekly_revenue is not None and weekly_revenue != 0 else (0.0 if weekly_dine_in == 0 and weekly_revenue == 0 else None),
        "takeaway_share": round(weekly_takeaway / weekly_revenue, 4) if weekly_takeaway is not None and weekly_revenue is not None and weekly_revenue != 0 else (0.0 if weekly_takeaway == 0 and weekly_revenue == 0 else None),
        "online_share": round(weekly_online / weekly_revenue, 4) if weekly_online is not None and weekly_revenue is not None and weekly_revenue != 0 else (0.0 if weekly_online == 0 and weekly_revenue == 0 else None),
        "discount_rate": round(1 - weekly_revenue / weekly_before_discount, 4) if weekly_before_discount is not None and weekly_before_discount != 0 and weekly_revenue is not None else (0.0 if weekly_before_discount == 0 and weekly_revenue == 0 else None),
        "revenue_per_customer": round(weekly_revenue / weekly_customers, 2) if weekly_revenue is not None and weekly_customers not in (None, 0) else (0.0 if weekly_revenue == 0 and weekly_customers else None),
        "member_recharge": weekly_member_recharge,
        "member_recharge_mtd": weekly_member_recharge_mtd,
        "rebate_coupon": weekly_rebate_coupon,
        "coupon_verify": weekly_coupon_verify,
        "coupon_recycle": weekly_coupon_recycle,
        "coupon_revenue": weekly_coupon_revenue,
        "child_card_issue": weekly_child_card_issue,
        "child_card_total": weekly_child_card_total,
        "duck_total": weekly_duck_total,
        "duck_dine_in": weekly_duck_dine_in,
        "duck_online": weekly_duck_online,
        "duck_mini": weekly_duck_mini,
        "duck_sauce": weekly_duck_sauce,
        "sesame_cake": weekly_sesame_cake,
        "duck_rack_ratio": weekly_duck_rack_ratio,
        "sesame_cake_ratio": weekly_sesame_cake_ratio,
        "set_meal_3p": _sum_present(daily, "set_meal_3p"),
        "set_meal_6p": _sum_present(daily, "set_meal_6p"),
        "set_meal_8p": _sum_present(daily, "set_meal_8p"),
        "set_meal_10p": _sum_present(daily, "set_meal_10p"),
        "set_meal_12p": _sum_present(daily, "set_meal_12p"),
        "crab_set_meal": _sum_present(daily, "crab_set_meal"),
        "pigeon": _sum_present(daily, "pigeon"),
        "mandarin_fish": _sum_present(daily, "mandarin_fish"),
        "fish_total": _sum_present(daily, "fish_total"),
        "sea_cucumber_beef_paw": _sum_present(daily, "sea_cucumber_beef_paw"),
        "dessert": _sum_present(daily, "dessert"),
        "per_seat_dish": _sum_present(daily, "per_seat_dish"),
        "sweet": _sum_present(daily, "sweet"),
        "house_drink": _sum_present(daily, "house_drink"),
        "craft_beer": _sum_present(daily, "craft_beer"),
        "month_yoy": _latest_present(daily, "month_yoy"),
        "revenue_month_to_date": _latest_present(daily, "revenue_month_to_date"),
        "revenue_mtd_before_discount": _latest_present(daily, "revenue_mtd_before_discount"),
        "revenue_same_period_last_year": _latest_present(daily, "revenue_same_period_last_year"),
        "revenue_yoy_delta": _latest_present(daily, "revenue_yoy_delta"),
        "best_day": None,
        "worst_day": None,
        "top_categories": _build_category_totals(daily),
        "daily_series": daily,
        "available_reports": len(report_by_date),
        "field_map_sections": sorted(field_map.keys()),
    }

    revenue_candidates = [row for row in daily if row.get("revenue") is not None]
    if revenue_candidates:
        best_row = max(revenue_candidates, key=lambda row: row["revenue"])
        worst_row = min(revenue_candidates, key=lambda row: row["revenue"])
        weekly["best_day"] = {
            "date": best_row["date"],
            "revenue": best_row["revenue"],
        }
        weekly["worst_day"] = {
            "date": worst_row["date"],
            "revenue": worst_row["revenue"],
        }
    else:
        weekly["best_day"] = {"date": None, "revenue": None}
        weekly["worst_day"] = {"date": None, "revenue": None}

    weekly["field_availability"] = {
        "report_json_days": len(report_by_date),
        "history_days": len(rows),
        "has_member_activity": any(
            weekly[key] is not None for key in ("member_recharge", "rebate_coupon", "coupon_verify", "coupon_recycle", "coupon_revenue", "child_card_issue")
        ),
        "has_duck_module": any(weekly[key] is not None for key in ("duck_total", "duck_dine_in", "duck_online", "duck_mini", "duck_sauce", "sesame_cake")),
        "has_category_module": any(value is not None for value in weekly["top_categories"].values()),
    }
    return weekly


def weekly_context(
    store: str,
    start_date: str,
    end_date: str,
    history_path: Path,
    strict_weekly_date_check: bool | None = None,
) -> dict:
    start = parse_date(start_date, "start-date")
    end = parse_date(end_date, "end-date")
    rows = load_rows(store, start, end, history_path)
    if not rows:
        raise ValueError(f"{store} 在 {start} 到 {end} 没有可用于看板的周报数据")

    expected = expected_dates(start, end)
    found = {row["_date"] for row in rows}
    missing_dates = [str(day) for day in expected if day not in found]
    strict = config.STRICT_WEEKLY_DATE_CHECK if strict_weekly_date_check is None else strict_weekly_date_check
    if missing_dates and strict:
        raise ValueError(f"周报区间缺失日期：{', '.join(missing_dates)}")

    stats = weekly_report.calc_stats(rows)
    stats["period_start_date"] = str(start)
    stats["period_end_date"] = str(end)
    stats["expected_days"] = len(expected)
    stats["missing_dates"] = missing_dates
    stats["date_check_status"] = "missing_dates_allowed" if missing_dates else "complete"
    enhanced = load_weekly_enriched_fields(
        store,
        str(start),
        str(end),
        history_path=history_path,
    )
    stats["weekly_enriched"] = enhanced

    row_by_date = {row["_date"]: row for row in rows}
    labels = [day.strftime("%m/%d") for day in expected]
    full_dates = [str(day) for day in expected]
    revenues = [as_float(row_by_date[day], "revenue") if day in row_by_date else None for day in expected]
    customers = [as_float(row_by_date[day], "customer_count") if day in row_by_date else None for day in expected]
    ducks = [as_float(row_by_date[day], "roast_duck_sales") if day in row_by_date else None for day in expected]

    existing_rank = sorted(
        [{"date": str(r["_date"]), "revenue": as_float(r, "revenue")} for r in rows],
        key=lambda item: item["revenue"],
        reverse=True,
    )

    weekly_dine_in = enhanced["dine_in_revenue"]
    weekly_takeaway = enhanced["takeaway_revenue"]
    weekly_online = enhanced["online_revenue"]
    weekly_discount = enhanced["discount_revenue"]
    has_structure = any(v is not None for v in [weekly_dine_in, weekly_takeaway, weekly_online, weekly_discount])
    structure = (
        [
            {"name": "堂食", "value": round(weekly_dine_in, 2) if weekly_dine_in is not None else 0},
            {"name": "外卖", "value": round(weekly_takeaway, 2) if weekly_takeaway is not None else 0},
            {"name": "线上外卖", "value": round(weekly_online, 2) if weekly_online is not None else 0},
            {"name": "优惠消费/其他", "value": round(weekly_discount, 2) if weekly_discount is not None else 0},
        ]
        if has_structure
        else []
    )

    max_revenue = max([item["revenue"] for item in existing_rank] or [1])
    strengths = []
    for day in expected:
        row = row_by_date.get(day)
        if row:
            score = round((as_float(row, "revenue") / max_revenue) * 100, 1) if max_revenue else 0
        else:
            score = 0
        strengths.append(score)

    diagnosis = build_weekly_diagnosis(enhanced, missing_dates, stats)

    return {
        "store": store,
        "start_date": str(start),
        "end_date": str(end),
        "title": f"{store} · {start} 至 {end} 周报经营看板",
        "labels": labels,
        "full_dates": full_dates,
        "revenues": revenues,
        "customers": customers,
        "ducks": ducks,
        "top_revenue": existing_rank[:5],
        "structure": structure,
        "strengths": strengths,
        "stats": stats,
        "enriched": enhanced,
        "missing_dates": missing_dates,
        "date_check_status": stats["date_check_status"],
        "diagnosis": diagnosis,
    }


def build_weekly_diagnosis(enriched: dict, missing_dates: list[str], stats: dict) -> list[str]:
    lines: list[str] = []
    daily_series = enriched.get("daily_series", [])
    available = [row for row in daily_series if row.get("revenue") is not None]
    if not available:
        return ["本周暂无可用经营字段，建议先补齐日报数据。"]

    weekend = [row for row in available if date.fromisoformat(row["date"]).weekday() >= 5]
    if weekend:
        weekend_avg = sum(row["revenue"] for row in weekend) / len(weekend)
        weekday_rows = [row for row in available if row not in weekend]
        if weekday_rows:
            weekday_avg = sum(row["revenue"] for row in weekday_rows) / len(weekday_rows)
            if weekend_avg >= weekday_avg * 1.1:
                lines.append("本周营业额高峰集中在周末，建议复盘周末客流来源。")

    if enriched.get("dine_in_share") is not None and enriched["dine_in_share"] >= 0.7:
        lines.append("堂食占比较高，门店到店消费仍是主要收入来源。")
    if enriched.get("online_share") is not None and enriched["online_share"] < 0.12:
        lines.append("外卖占比较低，下周可关注线上套餐和烤鸭外卖转化。")
    if enriched.get("member_recharge") is not None and enriched["member_recharge"] > 0:
        lines.append("会员储值本周有贡献，建议继续跟踪复购。")
    if enriched.get("duck_total") is not None and enriched.get("set_meal_total") is not None and enriched["set_meal_total"] < enriched["duck_total"] * 0.5:
        lines.append("套餐销量偏弱，建议复盘套餐推荐和组合定价。")
    if enriched.get("duck_total") is not None and enriched["duck_total"] > 0 and enriched.get("craft_beer") is not None and enriched["craft_beer"] == 0:
        lines.append("精酿销量为零，若是重点单品可加强推荐动作。")
    if missing_dates:
        lines.append(f"本周存在缺失日期：{'、'.join(missing_dates)}，需补齐日报连续性。")
    if stats.get("best_day", {}).get("date") and stats.get("worst_day", {}).get("date"):
        best = stats["best_day"].get("revenue") or 0
        worst = stats["worst_day"].get("revenue") or 0
        if worst > 0 and best / worst >= 1.4:
            lines.append("高低营业日差距较大，建议复盘活动和客流波动。")
    if not lines:
        lines.append("本周经营波动平稳，继续保持当前的客流和出品节奏。")
    return lines[:5]


def _fmt_money(value: float | None) -> str:
    return f"¥{value:,.0f}" if value is not None else "暂无"


def _fmt_count(value: float | None, unit: str = "") -> str:
    if value is None:
        return "暂无"
    if float(value).is_integer():
        text = f"{int(value):,}"
    else:
        text = f"{value:,.1f}"
    return f"{text}{unit}"


def _fmt_percent(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "暂无"
    pct = value * 100 if abs(value) <= 1 else value
    return f"{pct:.{digits}f}%"


def _build_chart_data(context: dict) -> dict:
    enriched = context["enriched"]
    series = enriched["daily_series"]
    labels = [row["date"][5:] for row in series]
    revenue = [row.get("revenue") for row in series]
    customers = [row.get("customer_count") for row in series]
    avg_tickets = [row.get("avg_ticket") for row in series]
    return {
        "labels": labels,
        "revenue": revenue,
        "customers": customers,
        "avg_tickets": avg_tickets,
        "structure": context["structure"],
        "top_categories": enriched["top_categories"],
        "duck": {
            "烤鸭总销量": enriched.get("duck_total"),
            "堂食烤鸭": enriched.get("duck_dine_in"),
            "线上外卖烤鸭": enriched.get("duck_online"),
            "迷你烤鸭": enriched.get("duck_mini"),
            "烤鸭小料": enriched.get("duck_sauce"),
            "烧饼": enriched.get("sesame_cake"),
            "烤鸭占比": enriched.get("duck_rack_ratio"),
            "烧饼占比": enriched.get("sesame_cake_ratio"),
        },
        "activity": {
            "会员储值": enriched.get("member_recharge"),
            "月累计会员储值": enriched.get("member_recharge_mtd"),
            "发券数量": enriched.get("rebate_coupon"),
            "验券数量": enriched.get("coupon_verify"),
            "代金券回收": enriched.get("coupon_recycle"),
            "券带来收入": enriched.get("coupon_revenue"),
            "儿童卡发放": enriched.get("child_card_issue"),
            "儿童卡累计": enriched.get("child_card_total"),
        },
        "summary": {
            "revenue_month_to_date": enriched.get("revenue_month_to_date"),
            "revenue_same_period_last_year": enriched.get("revenue_same_period_last_year"),
            "revenue_yoy_delta": enriched.get("revenue_yoy_delta"),
            "revenue_mtd_before_discount": enriched.get("revenue_mtd_before_discount"),
            "revenue_before_discount": enriched.get("revenue_before_discount"),
        },
    }


def echarts_option(context: dict) -> dict:
    data = _build_chart_data(context)
    return {
        "backgroundColor": "#08111f",
        "color": ["#42d7ff", "#8b5cf6", "#18e3b7", "#ffcf5a", "#ff6b8a"],
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["营业额", "客流"], "textStyle": {"color": "#b9c7e6"}},
        "grid": {"left": 50, "right": 55, "top": 40, "bottom": 35},
        "xAxis": {"type": "category", "data": data["labels"], "axisLabel": {"color": "#b9c7e6"}},
        "yAxis": [
            {"type": "value", "name": "营业额", "axisLabel": {"color": "#b9c7e6"}, "splitLine": {"lineStyle": {"color": "#20314f"}}},
            {"type": "value", "name": "客流", "axisLabel": {"color": "#b9c7e6"}, "splitLine": {"show": False}},
        ],
        "series": [
            {
                "name": "营业额",
                "type": "bar",
                "barWidth": "38%",
                "yAxisIndex": 0,
                "data": data["revenue"],
                "itemStyle": {"borderRadius": [6, 6, 0, 0]},
                "markPoint": {
                    "data": [
                        {"type": "max", "name": "最高营业日"},
                        {"type": "min", "name": "最低营业日"},
                    ]
                },
            },
            {
                "name": "客流",
                "type": "line",
                "smooth": True,
                "yAxisIndex": 1,
                "data": data["customers"],
                "lineStyle": {"width": 4, "color": "#8b5cf6"},
                "symbolSize": 8,
                "areaStyle": {"opacity": 0.08},
            }
        ],
    }


def render_html(context: dict, html_path: Path) -> Path:
    title = html.escape(context["title"])
    missing = "、".join(context["missing_dates"]) if context["missing_dates"] else "无"
    stats = context["stats"]
    data = _build_chart_data(context)
    trend_option = json.dumps(echarts_option(context), ensure_ascii=False)
    pie_data = json.dumps(data["structure"], ensure_ascii=False)
    category_names = json.dumps(list(data["top_categories"].keys()), ensure_ascii=False)
    category_values = json.dumps([v if v is not None else None for v in data["top_categories"].values()], ensure_ascii=False)
    avg_labels = json.dumps(data["labels"], ensure_ascii=False)
    avg_values = json.dumps(data["avg_tickets"], ensure_ascii=False)
    compare_values = json.dumps(
        [
            context["enriched"].get("dine_in_revenue"),
            context["enriched"].get("takeaway_revenue"),
            context["enriched"].get("online_revenue"),
            context["enriched"].get("discount_revenue"),
        ],
        ensure_ascii=False,
    )
    duck_names = json.dumps(list(data["duck"].keys()), ensure_ascii=False)
    duck_values = json.dumps([v if v is not None else None for v in data["duck"].values()], ensure_ascii=False)
    activity = data["activity"]
    duck = data["duck"]
    diagnosis = context["diagnosis"]
    summary = data["summary"]

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; width:{WIDTH}px; height:{HEIGHT}px; background:#08111f; color:#eaf4ff; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; }}
    .screen {{ width:{WIDTH}px; height:{HEIGHT}px; padding:28px 34px; background:radial-gradient(circle at top,#182f66 0,#08111f 44%,#050914 100%); }}
    .header {{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:18px; }}
    h1 {{ margin:0; font-size:34px; letter-spacing:0; }}
    .sub {{ color:#90a8d8; font-size:16px; }}
    .warn {{ margin:0 0 14px; padding:10px 16px; border:1px solid #ffcf5a; background:rgba(255,207,90,.12); color:#ffe6a3; border-radius:8px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(7,1fr); gap:12px; margin-bottom:14px; }}
    .kpi,.card {{ border:1px solid rgba(91,141,255,.28); background:linear-gradient(180deg,rgba(21,39,75,.88),rgba(8,17,31,.9)); border-radius:8px; box-shadow:0 0 22px rgba(66,215,255,.08) inset; }}
    .kpi {{ padding:12px 14px; min-height:84px; }}
    .kpi span {{ display:block; color:#8ea4cf; font-size:13px; margin-bottom:8px; }}
    .kpi strong {{ font-size:21px; color:#fff; }}
    .grid {{ display:grid; grid-template-columns:1.9fr 1.1fr; grid-template-rows:230px 168px 168px 112px; gap:14px; }}
    .card {{ padding:12px; min-width:0; }}
    .card-title {{ color:#b9d7ff; font-size:15px; margin:0 0 8px; }}
    .chart {{ width:100%; height:calc(100% - 24px); }}
    .empty {{ height:calc(100% - 24px); display:flex; align-items:center; justify-content:center; color:#7f90b8; border:1px dashed rgba(142,164,207,.35); border-radius:8px; }}
    .subgrid {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; grid-column:1 / span 2; }}
    .subgrid2 {{ display:grid; grid-template-columns:repeat(2, 1fr); gap:14px; grid-column:1 / span 2; }}
    .activity {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px 10px; }}
    .metric {{ padding:10px 12px; border:1px solid rgba(91,141,255,.2); background:rgba(16,35,64,.72); border-radius:8px; }}
    .metric span {{ display:block; color:#8ea4cf; font-size:12px; margin-bottom:6px; }}
    .metric strong {{ color:#fff; font-size:16px; }}
    .diagnosis {{ grid-column:1 / span 2; padding:10px 14px; }}
    .diagnosis ul {{ margin:4px 0 0 16px; padding:0; color:#eaf4ff; }}
    .diagnosis li {{ margin:4px 0; line-height:1.45; }}
  </style>
</head>
<body>
<main class="screen">
  <div class="header">
    <h1>{title}</h1>
    <div class="sub">Apache ECharts 风格 · 周报数据可视化增强层</div>
  </div>
  {'<div class="warn">缺失日期提示：' + html.escape(missing) + '</div>' if context["missing_dates"] else ''}
  <section class="kpis">
    <div class="kpi"><span>本周营业额</span><strong>{_fmt_money(stats.get("total_revenue"))}</strong></div>
    <div class="kpi"><span>日均营业额</span><strong>{_fmt_money(stats.get("daily_avg_revenue"))}</strong></div>
    <div class="kpi"><span>本周总客流</span><strong>{_fmt_count(stats.get("total_customers"), "人")}</strong></div>
    <div class="kpi"><span>客单价</span><strong>{_fmt_money(stats.get("avg_ticket"))}</strong></div>
    <div class="kpi"><span>堂食占比</span><strong>{_fmt_percent(context["enriched"].get("dine_in_share"))}</strong></div>
    <div class="kpi"><span>外卖占比</span><strong>{_fmt_percent(context["enriched"].get("takeaway_share"))}</strong></div>
    <div class="kpi"><span>周报天数 / 缺失</span><strong>{stats["n_days"]}/{stats["expected_days"]} · {html.escape(missing)}</strong></div>
  </section>
  <section class="grid">
    <div class="card" style="grid-column:1 / span 1; grid-row:1;">
      <p class="card-title">每日营业额 + 客流双轴趋势</p>
      <div id="trend" class="chart"></div>
    </div>
    <div class="card" style="grid-column:2 / span 1; grid-row:1;">
      <p class="card-title">收入结构</p>
      {('<div id="structure" class="chart"></div>') if context["structure"] else '<div class="empty">暂无采集数据</div>'}
      <div style="color:#90a8d8;font-size:12px;margin-top:4px;">
        月累计 { _fmt_money(summary.get("revenue_month_to_date")) } · 同期累计 { _fmt_money(summary.get("revenue_same_period_last_year")) } · 差额 {_fmt_money(summary.get("revenue_yoy_delta"))}
      </div>
    </div>
    <div class="subgrid">
      <div class="card">
        <p class="card-title">客单价趋势</p>
        <div id="ticket" class="chart"></div>
      </div>
      <div class="card">
        <p class="card-title">堂食 / 外卖 / 线上收入对比</p>
        <div id="revenue_compare" class="chart"></div>
      </div>
      <div class="card">
        <p class="card-title">会员与活动</p>
        <div class="activity">
          <div class="metric"><span>会员储值</span><strong>{_fmt_money(activity.get("会员储值"))}</strong></div>
          <div class="metric"><span>发券数量</span><strong>{_fmt_count(activity.get("发券数量"))}</strong></div>
          <div class="metric"><span>验券数量</span><strong>{_fmt_count(activity.get("验券数量"))}</strong></div>
          <div class="metric"><span>代金券回收</span><strong>{_fmt_count(activity.get("代金券回收"))}</strong></div>
          <div class="metric"><span>儿童卡发放</span><strong>{_fmt_count(activity.get("儿童卡发放"))}</strong></div>
          <div class="metric"><span>券带来收入</span><strong>{_fmt_money(activity.get("券带来收入"))}</strong></div>
        </div>
      </div>
    </div>
    <div class="subgrid2">
      <div class="card">
        <p class="card-title">关键品类销量 TOP</p>
        <div id="categories" class="chart"></div>
      </div>
      <div class="card">
        <p class="card-title">烤鸭专项分析</p>
        <div id="duck" class="chart"></div>
      </div>
    </div>
    <div class="card diagnosis">
      <p class="card-title">本周经营诊断</p>
      <ul>
        {''.join(f'<li>{html.escape(item)}</li>' for item in diagnosis)}
      </ul>
    </div>
  </section>
</main>
<script>
const baseText = {{ color: '#b9c7e6' }};
echarts.init(document.getElementById('trend')).setOption({trend_option});
if (document.getElementById('structure')) echarts.init(document.getElementById('structure')).setOption({{
  tooltip: {{ trigger:'item' }},
  series:[{{ type:'pie', radius:['44%','72%'], center:['42%','48%'], data:{pie_data}, label:{{ color:'#dfe9ff', formatter:'{{b}}\\n{{d}}%' }} }}]
}});
echarts.init(document.getElementById('ticket')).setOption({{
  tooltip: {{ trigger:'axis' }},
  grid: {{ left: 50, right: 20, top: 18, bottom: 24 }},
  xAxis: {{ type:'category', data:{avg_labels}, axisLabel:baseText }},
  yAxis: {{ type:'value', axisLabel:baseText, splitLine:{{ lineStyle:{{ color:'#20314f' }} }} }},
  series:[{{ name:'客单价', type:'line', smooth:true, data:{avg_values}, lineStyle:{{ width:4, color:'#18e3b7' }}, symbolSize:7, areaStyle:{{ opacity:.12 }} }}]
}});
echarts.init(document.getElementById('revenue_compare')).setOption({{
  tooltip: {{ trigger:'axis', axisPointer: {{ type:'shadow' }} }},
  grid: {{ left: 85, right: 20, top: 18, bottom: 22 }},
  xAxis: {{ type:'value', axisLabel:baseText, splitLine:{{ lineStyle:{{ color:'#20314f' }} }} }},
  yAxis: {{ type:'category', data:['堂食','外卖','线上','优惠'], axisLabel:baseText }},
  series:[{{ type:'bar', data:{compare_values}, itemStyle:{{ borderRadius:[0,6,6,0] }} }}]
}});
echarts.init(document.getElementById('categories')).setOption({{
  tooltip: {{ trigger:'axis', axisPointer: {{ type:'shadow' }} }},
  grid: {{ left: 96, right: 20, top: 18, bottom: 24 }},
  xAxis: {{ type:'value', axisLabel:baseText, splitLine:{{ lineStyle:{{ color:'#20314f' }} }} }},
  yAxis: {{ type:'category', data:{category_names}, axisLabel:baseText }},
  series:[{{ type:'bar', data:{category_values}, itemStyle:{{ borderRadius:[0,6,6,0] }} }}]
}});
echarts.init(document.getElementById('duck')).setOption({{
  tooltip: {{ trigger:'axis', axisPointer: {{ type:'shadow' }} }},
  grid: {{ left: 96, right: 20, top: 18, bottom: 24 }},
  xAxis: {{ type:'value', axisLabel:baseText, splitLine:{{ lineStyle:{{ color:'#20314f' }} }} }},
  yAxis: {{ type:'category', data:{duck_names}, axisLabel:baseText }},
  series:[{{ type:'bar', data:{duck_values}, itemStyle:{{ borderRadius:[0,6,6,0] }} }}]
}});
</script>
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_text, encoding="utf-8")
    return html_path


def _font(size: int):
    from PIL import ImageFont

    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def render_png(context: dict, png_path: Path) -> Path:
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        raise RuntimeError(f"无法生成 PNG：缺少 Pillow 依赖 ({exc})") from exc

    image = Image.new("RGB", (WIDTH, HEIGHT), "#08111f")
    draw = ImageDraw.Draw(image)
    title_font = _font(34)
    text_font = _font(18)
    small_font = _font(14)
    number_font = _font(28)

    data = _build_chart_data(context)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill="#08111f")
    draw.ellipse((-160, -260, 760, 420), fill="#132d66")
    draw.rectangle((34, 28, WIDTH - 34, HEIGHT - 28), outline="#1f4b89", width=2)
    draw.text((56, 44), context["title"], fill="#f3f8ff", font=title_font)
    draw.text((WIDTH - 380, 58), "周报数据可视化增强层", fill="#8ea4cf", font=text_font)

    y = 110
    if context["missing_dates"]:
        draw.rounded_rectangle((56, y, WIDTH - 56, y + 44), radius=8, fill="#3a2f13", outline="#ffcf5a")
        draw.text((76, y + 12), f"缺失日期提示：{'、'.join(context['missing_dates'])}", fill="#ffe6a3", font=text_font)
        y += 58

    stats = context["stats"]
    kpis = [
        ("本周营业额", _fmt_money(stats.get("total_revenue"))),
        ("日均营业额", _fmt_money(stats.get("daily_avg_revenue"))),
        ("本周总客流", _fmt_count(stats.get("total_customers"), "人")),
        ("客单价", _fmt_money(stats.get("avg_ticket"))),
        ("堂食占比", _fmt_percent(context["enriched"].get("dine_in_share"))),
        ("外卖占比", _fmt_percent(context["enriched"].get("takeaway_share"))),
        ("周报天数/缺失", f"{stats['n_days']}/{stats['expected_days']} · {('无' if not context['missing_dates'] else '、'.join(context['missing_dates']))}"),
    ]
    card_w = (WIDTH - 112 - 6 * 10) // 7
    for idx, (label, value) in enumerate(kpis):
        x = 56 + idx * (card_w + 10)
        draw.rounded_rectangle((x, y, x + card_w, y + 92), radius=8, fill="#102340", outline="#2b62aa")
        draw.text((x + 14, y + 14), label, fill="#8ea4cf", font=small_font)
        draw.text((x + 14, y + 46), value, fill="#ffffff", font=number_font if idx < 4 else text_font)
    y += 112

    def panel(box, title):
        draw.rounded_rectangle(box, radius=8, fill="#0d1d36", outline="#264f8a")
        draw.text((box[0] + 16, box[1] + 12), title, fill="#b9d7ff", font=text_font)

    panel((56, y, 1008, y + 230), "趋势判断")
    panel((1032, y, WIDTH - 56, y + 230), "收入结构")
    y2 = y + 248
    panel((56, y2, 510, y2 + 168), "客单价趋势")
    panel((526, y2, 1040, y2 + 168), "堂食 / 外卖 / 线上收入对比")
    panel((1060, y2, WIDTH - 56, y2 + 168), "会员与活动")
    y3 = y2 + 186
    panel((56, y3, 768, y3 + 176), "关键品类销量 TOP")
    panel((784, y3, WIDTH - 56, y3 + 176), "烤鸭专项分析")
    y4 = y3 + 192
    panel((56, y4, WIDTH - 56, y4 + 110), "本周经营诊断")

    # Trend panel
    x1, y1, x2, y2p = 56, y, 1008, y + 230
    values = [v if v is not None else 0 for v in data["revenue"]]
    customers_values = [v if v is not None else 0 for v in data["customers"]]
    max_v = max(values or [1]) or 1
    max_c = max(customers_values or [1]) or 1
    left = x1 + 32
    right = x2 - 28
    bottom = y2p - 34
    points = []
    line_points = []
    for i, value in enumerate(values):
        x = left + i * ((right - left) / max(1, len(values) - 1))
        h = int((value / max_v) * 130)
        draw.rectangle((x - 20, bottom - h, x + 20, bottom), fill="#42d7ff")
        draw.text((x - 14, bottom + 6), data["labels"][i], fill="#8ea4cf", font=small_font)
        points.append((x, bottom - h))
    for i, value in enumerate(customers_values):
        x = left + i * ((right - left) / max(1, len(customers_values) - 1))
        yy = bottom - int((value / max_c) * 130)
        line_points.append((x, yy))
    if len(line_points) > 1:
        draw.line(line_points, fill="#8b5cf6", width=4)
        for p in line_points:
            draw.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill="#ffcf5a")
    if context["stats"]["best_day"]["date"]:
        draw.text((x2 - 220, y + 18), f"最高营业日: {context['stats']['best_day']['date']}", fill="#ffe6a3", font=small_font)
    if context["stats"]["worst_day"]["date"]:
        draw.text((x2 - 220, y + 36), f"最低营业日: {context['stats']['worst_day']['date']}", fill="#ffe6a3", font=small_font)

    # Revenue structure panel
    sx1, sy1, sx2, sy2p = 1032, y, WIDTH - 56, y + 230
    struct = data["structure"]
    if struct:
        total = sum(item["value"] for item in struct if item["value"] is not None) or 1
        cx1, cy1, cx2, cy2 = sx1 + 42, sy1 + 38, sx1 + 178, sy1 + 174
        start_angle = 0
        colors = ["#42d7ff", "#8b5cf6", "#18e3b7", "#ffcf5a"]
        for idx, item in enumerate(struct):
            val = item["value"] or 0
            angle = 360 * val / total
            draw.pieslice((cx1, cy1, cx2, cy2), start_angle, start_angle + angle, fill=colors[idx % len(colors)])
            start_angle += angle
        for idx, item in enumerate(struct):
            ytext = sy1 + 30 + idx * 42
            draw.rectangle((sx1 + 210, ytext, sx1 + 224, ytext + 14), fill=colors[idx % len(colors)])
            pct = (item["value"] or 0) / total * 100 if total else 0
            draw.text((sx1 + 232, ytext - 2), f"{item['name']}  {_fmt_money(item['value'])}  {pct:.1f}%", fill="#dfe9ff", font=small_font)
        draw.text((sx1 + 40, sy2p - 26), f"月累计 {_fmt_money(data['summary'].get('revenue_month_to_date'))}  同期累计 {_fmt_money(data['summary'].get('revenue_same_period_last_year'))}", fill="#8ea4cf", font=small_font)
        draw.text((sx1 + 40, sy2p - 8), f"同比差额 {_fmt_money(data['summary'].get('revenue_yoy_delta'))}  月折前 {_fmt_money(data['summary'].get('revenue_mtd_before_discount'))}", fill="#8ea4cf", font=small_font)
    else:
        draw.text((sx1 + 180, sy1 + 96), "暂无采集数据", fill="#7f90b8", font=text_font)

    def draw_line_chart(box, values, color="#18e3b7", title=None):
        x1, y1, x2, y2p = box
        numeric = [v if v is not None else 0 for v in values]
        max_v = max(numeric or [1]) or 1
        if title:
            draw.text((x1 + 12, y1 + 12), title, fill="#b9d7ff", font=small_font)
        points = []
        for i, value in enumerate(numeric):
            x = x1 + 26 + i * ((x2 - x1 - 56) / max(1, len(numeric) - 1))
            yv = y2p - 30 - (value / max_v) * (y2p - y1 - 56)
            points.append((x, yv))
        if len(points) > 1:
            draw.line(points, fill=color, width=4)
            for p in points:
                draw.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill="#ffcf5a")
        for i, p in enumerate(points):
            if i < len(data["labels"]):
                draw.text((p[0] - 12, y2p - 22), data["labels"][i], fill="#8ea4cf", font=small_font)

    draw_line_chart((56, y2, 510, y2 + 168), data["avg_tickets"], color="#18e3b7")

    # Revenue compare
    rbx1, rby1, rbx2, rby2 = 526, y2, 1040, y2 + 168
    compare_items = [("堂食", context["enriched"].get("dine_in_revenue")), ("外卖", context["enriched"].get("takeaway_revenue")), ("线上", context["enriched"].get("online_revenue")), ("优惠", context["enriched"].get("discount_revenue"))]
    max_compare = max([item[1] or 0 for item in compare_items] or [1]) or 1
    for idx, (name, value) in enumerate(compare_items):
        yy = rby1 + 34 + idx * 28
        draw.text((rbx1 + 16, yy), name, fill="#b9c7e6", font=small_font)
        width = int(((value or 0) / max_compare) * (rbx2 - rbx1 - 130))
        draw.rounded_rectangle((rbx1 + 76, yy + 2, rbx1 + 76 + width, yy + 16), radius=5, fill="#8b5cf6" if idx == 1 else "#42d7ff")
        draw.text((rbx1 + 82 + width + 8, yy), _fmt_money(value), fill="#dfe9ff", font=small_font)

    # Activity panel
    ax1, ay1, ax2, ay2 = 1060, y2, WIDTH - 56, y2 + 168
    activity_lines = [
        ("会员储值", data["activity"].get("会员储值")),
        ("月累计会员储值", data["activity"].get("月累计会员储值")),
        ("发券数量", data["activity"].get("发券数量")),
        ("验券数量", data["activity"].get("验券数量")),
        ("代金券回收", data["activity"].get("代金券回收")),
        ("儿童卡发放", data["activity"].get("儿童卡发放")),
    ]
    for idx, (name, value) in enumerate(activity_lines):
        yy = ay1 + 24 + (idx // 2) * 40
        xx = ax1 + 14 + (idx % 2) * 110
        draw.rectangle((xx, yy, xx + 98, yy + 34), fill="#102340", outline="#2b62aa")
        draw.text((xx + 8, yy + 6), name, fill="#8ea4cf", font=small_font)
        draw.text((xx + 8, yy + 18), _fmt_money(value) if "储值" in name or "收入" in name else _fmt_count(value), fill="#ffffff", font=small_font)

    # Category top panel
    cat_items = list(data["top_categories"].items())
    max_cat = max([v or 0 for _, v in cat_items] or [1]) or 1
    for idx, (name, value) in enumerate(cat_items):
        yy = y3 + 32 + idx * 16
        width = int(((value or 0) / max_cat) * (708 if (WIDTH - 56) > 768 else 650))
        draw.text((76, yy), name, fill="#b9c7e6", font=small_font)
        draw.rounded_rectangle((170, yy + 2, 170 + width, yy + 14), radius=4, fill="#42d7ff")
        draw.text((180 + width, yy), _fmt_count(value), fill="#dfe9ff", font=small_font)

    # Duck special panel
    duck_items = list(data["duck"].items())
    max_duck = max([v or 0 for _, v in duck_items if isinstance(v, (int, float)) or v is not None] or [1]) or 1
    for idx, (name, value) in enumerate(duck_items):
        col = 0 if idx < 4 else 1
        row = idx if idx < 4 else idx - 4
        xx = 808 + col * 290
        yy = y3 + 34 + row * 34
        draw.text((xx, yy), name, fill="#b9c7e6", font=small_font)
        bar_x = xx + 82
        bar_w = int(((value or 0) / max_duck) * 150) if value is not None else 0
        draw.rounded_rectangle((bar_x, yy + 3, bar_x + bar_w, yy + 15), radius=4, fill="#18e3b7")
        draw.text((bar_x + bar_w + 6, yy), _fmt_percent(value) if "占比" in name else _fmt_count(value), fill="#dfe9ff", font=small_font)

    # Diagnosis panel
    dx1, dy1, dx2, dy2 = 56, y4, WIDTH - 56, y4 + 110
    for idx, line in enumerate(context["diagnosis"]):
        draw.text((dx1 + 18, dy1 + 28 + idx * 18), f"• {line}", fill="#eaf4ff", font=small_font)

    image.save(png_path)
    return png_path


def render_dashboard(
    store: str,
    start_date: str | None,
    end_date: str | None,
    history_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    strict_weekly_date_check: bool | None = None,
) -> dict:
    history = Path(history_path) if history_path else config.DATA_DIR / "store_history.csv"
    output = Path(output_dir) if output_dir else config.OUTPUT_DIR
    context = weekly_context(store, start_date, end_date, history, strict_weekly_date_check)
    start = date.fromisoformat(context["start_date"])
    end = date.fromisoformat(context["end_date"])
    html_path, png_path = output_paths(store, start, end, output)
    render_html(context, html_path)
    render_png(context, png_path)
    return {
        "html_path": str(html_path),
        "png_path": str(png_path),
        "start_date": context["start_date"],
        "end_date": context["end_date"],
        "missing_dates": context["missing_dates"],
        "date_check_status": context["date_check_status"],
    }


def send_dashboard_to_feishu(png_path: Path, store: str, start_date: str, end_date: str) -> None:
    import feishu_bot

    png_path = Path(png_path)
    if not png_path.exists():
        raise FileNotFoundError(f"PNG 不存在，不能推送飞书: {png_path}")
    if not feishu_bot._has_app_creds():
        raise RuntimeError("未配置飞书 App 图片上传凭证，已跳过图片推送")
    title = f"{store}｜{start_date} 至 {end_date} 周报可视化看板"
    note = "本看板基于已校验周报数据生成，业务日期来自图片表头日期。"
    key = feishu_bot._upload_image(png_path)
    feishu_bot.send_text(f"{title}\n{note}", ensure_keyword=False)
    feishu_bot._send_image_key(key)


def push_to_feishu(png_path: Path) -> None:
    import feishu_bot

    png_path = Path(png_path)
    if not png_path.exists():
        raise FileNotFoundError(f"PNG 不存在，不能推送飞书: {png_path}")
    if not feishu_bot._has_app_creds():
        raise RuntimeError("未配置飞书 App 图片上传凭证，已跳过图片推送")
    key = feishu_bot._upload_image(png_path)
    feishu_bot._send_image_key(key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成周报可视化看板 HTML/PNG")
    parser.add_argument("--store", required=True, help="门店名称，例如 便宜坊马连道")
    parser.add_argument("--start-date", required=True, help="周报开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="周报结束日期 YYYY-MM-DD")
    parser.add_argument("--history-path", default=str(config.DATA_DIR / "store_history.csv"), help="历史数据 CSV")
    parser.add_argument("--output-dir", default=str(config.OUTPUT_DIR), help="输出目录")
    parser.add_argument("--strict-weekly-date-check", action="store_true", help="缺失日期时停止生成")
    parser.add_argument("--send-to-feishu", action="store_true", help="生成后推送 PNG 到飞书；默认不推送")
    parser.add_argument("--push-feishu", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = render_dashboard(
        store=args.store,
        start_date=args.start_date,
        end_date=args.end_date,
        history_path=Path(args.history_path),
        output_dir=Path(args.output_dir),
        strict_weekly_date_check=args.strict_weekly_date_check or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.send_to_feishu or args.push_feishu:
        send_dashboard_to_feishu(Path(result["png_path"]), args.store, result["start_date"], result["end_date"])
        print("[weekly-dashboard] 已推送看板图片到飞书")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
