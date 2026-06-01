"""日期维度单一真相源 (single source of truth)。

所有日期维度字段、对比基准日期、月累计(MTD)窗口、跨月周覆盖，都是 business_date 的纯函数。
周报/月报/看板读取器应统一从这里取字段，不要各自用系统日期临时推断。

设计原则：
- 纯函数，无副作用，只依赖 stdlib + 一个 config 文件 (data/holiday_calendar_cn.json)。
- business_date 必须由调用方从图片表头/真实业务数据得到，本模块不读系统日期，不做 date.today()。
- 上月同期缺日（如 3/31 对应 2 月）自动取上月最后一天，不报错、不乱填。
"""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
HOLIDAY_CALENDAR_PATH = DATA_DIR / "holiday_calendar_cn.json"

_WEEKDAY_NAMES_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def parse_date(value) -> date:
    """把 'YYYY-MM-DD' 或 date 转成 date。"""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _fmt(d: date) -> str:
    return d.isoformat()


def load_holiday_calendar(path: Path | None = None) -> dict:
    """读取节假日配置；文件缺失时返回空配置（全部按默认工作日规则）。"""
    path = path or HOLIDAY_CALENDAR_PATH
    if not path.exists():
        return {"holidays": {}, "makeup_workdays": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"holidays": {}, "makeup_workdays": {}}
    return {
        "holidays": raw.get("holidays", {}) or {},
        "makeup_workdays": raw.get("makeup_workdays", {}) or {},
    }


def last_day_of_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def clamp_day_to_month(year: int, month: int, day: int) -> date:
    """把 day 夹到该月有效范围内（缺日取该月最后一天）。"""
    last = last_day_of_month(year, month)
    return date(year, month, min(day, last))


def week_bounds(d: date) -> tuple[date, date]:
    """自然周：周一(start) 到 周日(end)。"""
    start = d - timedelta(days=d.weekday())  # weekday(): Mon=0
    end = start + timedelta(days=6)
    return start, end


def previous_month_same_day(d: date) -> date:
    """上月同一天；上月无此日则取上月最后一天。"""
    py, pm = previous_month(d.year, d.month)
    return clamp_day_to_month(py, pm, d.day)


def month_to_date_window(d: date) -> tuple[date, date]:
    """本月累计窗口：本月 1 号 → business_date。"""
    return date(d.year, d.month, 1), d


def previous_month_mtd_window(d: date) -> tuple[date, date]:
    """上月同期累计窗口：上月 1 号 → 上月对应第 N 天（缺日取上月最后一天）。"""
    py, pm = previous_month(d.year, d.month)
    start = date(py, pm, 1)
    end = clamp_day_to_month(py, pm, d.day)
    return start, end


def cross_month_week_coverage(week_start: date, week_end: date) -> dict:
    """给定自然周区间，返回是否跨月，以及每个 business_month 覆盖的天数与日期。"""
    coverage: dict[str, dict] = {}
    cur = week_start
    while cur <= week_end:
        key = f"{cur.year:04d}-{cur.month:02d}"
        bucket = coverage.setdefault(key, {"business_month": key, "days": 0, "dates": []})
        bucket["days"] += 1
        bucket["dates"].append(_fmt(cur))
        cur += timedelta(days=1)
    months = list(coverage.values())
    return {
        "is_cross_month_week": len(months) > 1,
        "months": months,
    }


def derive_date_dimension(business_date, holiday_calendar: dict | None = None) -> dict:
    """从 business_date 派生全部日期维度 + 对比基准 + MTD 窗口。

    business_date 必须来自图片表头/真实业务数据，调用方负责保证。
    """
    d = parse_date(business_date)
    cal = holiday_calendar if holiday_calendar is not None else load_holiday_calendar()
    holidays = cal.get("holidays", {})
    makeup = cal.get("makeup_workdays", {})

    ds = _fmt(d)
    wk_start, wk_end = week_bounds(d)
    mtd_start, mtd_end = month_to_date_window(d)
    pm_mtd_start, pm_mtd_end = previous_month_mtd_window(d)

    is_weekend = d.weekday() >= 5  # Sat=5, Sun=6
    is_holiday = ds in holidays
    is_makeup_workday = ds in makeup
    # 工作日：非休息日。休息日 = 周末或法定节假日；调休补班把周末翻回工作日。
    if is_makeup_workday:
        is_workday = True
    elif is_holiday or is_weekend:
        is_workday = False
    else:
        is_workday = True

    last_dom = last_day_of_month(d.year, d.month)
    cross_week = cross_month_week_coverage(wk_start, wk_end)

    return {
        # —— 基础维度 ——
        "business_date": ds,
        "business_year": d.year,
        "business_month": f"{d.year:04d}-{d.month:02d}",
        "business_week_start": _fmt(wk_start),
        "business_week_end": _fmt(wk_end),
        "day_of_month": d.day,
        "weekday": d.isoweekday(),  # 1=周一 .. 7=周日
        "weekday_name": _WEEKDAY_NAMES_CN[d.weekday()],
        "is_month_start": d.day == 1,
        "is_month_end": d.day == last_dom,
        "is_week_start": d.weekday() == 0,
        "is_week_end": d.weekday() == 6,
        "is_weekend": is_weekend,
        "is_workday": is_workday,
        "is_holiday": is_holiday,
        "holiday_name": holidays.get(ds, ""),
        "is_makeup_workday": is_makeup_workday,
        # —— 对比基准日期 ——
        "previous_day_date": _fmt(d - timedelta(days=1)),
        "previous_week_same_weekday_date": _fmt(d - timedelta(days=7)),
        "previous_month_same_day_date": _fmt(previous_month_same_day(d)),
        # —— MTD 窗口 ——
        "month_to_date_start": _fmt(mtd_start),
        "month_to_date_end": _fmt(mtd_end),
        "previous_month_mtd_start": _fmt(pm_mtd_start),
        "previous_month_mtd_end": _fmt(pm_mtd_end),
        # —— 跨月周 ——
        "is_cross_month_week": cross_week["is_cross_month_week"],
        "week_month_coverage": cross_week["months"],
    }


def monthly_caliber_hint(business_date, holiday_calendar: dict | None = None) -> str:
    """日报推送用的‘月度口径提示’文本（req 11）。只读真实派生值，不造数。"""
    dim = derive_date_dimension(business_date, holiday_calendar)
    bm = dim["business_month"]
    return (
        f"月度口径提示：当前为 {bm} 第 {dim['day_of_month']} 天；"
        f"本月累计区间 {dim['month_to_date_start']} ~ {dim['month_to_date_end']}；"
        f"上月同期累计 {dim['previous_month_mtd_start']} ~ {dim['previous_month_mtd_end']}；"
        f"上周同一星期({dim['weekday_name']}) 为 {dim['previous_week_same_weekday_date']}；"
        f"今日为 {bm} 月报的第 {dim['day_of_month']} 个口径基准记录。"
    )


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "2026-06-01"
    dim = derive_date_dimension(target)
    print(json.dumps(dim, ensure_ascii=False, indent=2))
    print()
    print(monthly_caliber_hint(target))
