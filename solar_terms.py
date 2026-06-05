"""二十四节气上下文（确定性，单一真相源 = data/solar_terms_cn.json）。

设计原则（与项目「绝不伪造数据」一致）：
- 节气日期只来自权威发布表（data/solar_terms_cn.json），不用公式临时近似推断。
  （寿星公式对个别年份有 ±1 天误差，不可作为业务真相。）
- 表未覆盖的年份诚实返回 status='no_data'，字段填 None / "暂无"，绝不猜测。
- 纯函数，无副作用，只依赖 stdlib + 一个 config 文件。

主入口：solar_term_context(business_date) -> dict
返回当日是否恰逢节气、当前所处节气、下一个节气、距下一个节气天数等。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SOLAR_TERMS_PATH = DATA_DIR / "solar_terms_cn.json"

# 节气标准顺序（小寒 起，冬至 止），用于跨年衔接
TERM_ORDER = [
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分",
    "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
    "小暑", "大暑", "立秋", "处暑", "白露", "秋分",
    "寒露", "霜降", "立冬", "小雪", "大雪", "冬至",
]


def _parse(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def load_solar_terms(path: Path | None = None) -> dict:
    """读取节气表；缺失或损坏时返回空表（全部按 no_data 处理）。"""
    path = path or SOLAR_TERMS_PATH
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw.get("terms", {}) or {}


def _all_terms_sorted(terms_table: dict) -> list[tuple[date, str]]:
    """把多年的节气拍平成按日期升序的 (date, name) 列表。"""
    flat: list[tuple[date, str]] = []
    for _year, mapping in terms_table.items():
        for name, ds in mapping.items():
            try:
                flat.append((_parse(ds), name))
            except (ValueError, TypeError):
                continue
    flat.sort(key=lambda x: x[0])
    return flat


def solar_term_context(business_date, terms_table: dict | None = None) -> dict:
    """从 business_date 派生节气上下文（确定性，纯函数）。

    返回字段：
    - solar_term_status: 'ok' | 'no_data'（该年节气表未覆盖）
    - is_solar_term_day: 当天是否恰好是某个节气
    - solar_term_today: 当天恰逢的节气名（否则 None）
    - current_solar_term: 当前所处节气（≤ business_date 的最近一个节气）
    - current_solar_term_date: 该节气日期
    - days_into_current_term: 距当前节气已过天数（节气当天=0）
    - next_solar_term: 下一个节气名
    - next_solar_term_date: 下一个节气日期
    - days_to_next_term: 距下一个节气还有几天
    """
    d = _parse(business_date)
    table = terms_table if terms_table is not None else load_solar_terms()

    none_result = {
        "solar_term_status": "no_data",
        "is_solar_term_day": False,
        "solar_term_today": None,
        "current_solar_term": None,
        "current_solar_term_date": None,
        "days_into_current_term": None,
        "next_solar_term": None,
        "next_solar_term_date": None,
        "days_to_next_term": None,
    }

    # 该年是否在表内；为安全起见，要求 business_date 当年和相邻年份足以定位前后节气
    flat = _all_terms_sorted(table)
    if not flat:
        return none_result

    # 必须保证表覆盖到 business_date 当年，否则诚实降级
    year_keys = {dt.year for dt, _ in flat}
    if d.year not in year_keys:
        return none_result

    # 当前所处节气 = 最近一个 <= d 的节气；下一个 = 第一个 > d 的节气
    current = None  # (date, name)
    nxt = None
    for dt, name in flat:
        if dt <= d:
            current = (dt, name)
        elif dt > d:
            nxt = (dt, name)
            break

    # 若 d 早于表内最早节气（如 1/1 而表从当年 1/5 起），current 落到上一年最后一个节气；
    # 若表未含上一年，则 current 可能为 None → 诚实降级该字段，但 next 仍可给。
    result = dict(none_result)
    result["solar_term_status"] = "ok"

    if current is not None:
        cur_date, cur_name = current
        result["current_solar_term"] = cur_name
        result["current_solar_term_date"] = cur_date.isoformat()
        result["days_into_current_term"] = (d - cur_date).days
        result["is_solar_term_day"] = (cur_date == d)
        result["solar_term_today"] = cur_name if cur_date == d else None

    if nxt is not None:
        nxt_date, nxt_name = nxt
        result["next_solar_term"] = nxt_name
        result["next_solar_term_date"] = nxt_date.isoformat()
        result["days_to_next_term"] = (nxt_date - d).days

    # 如果既没有 current 也没有 next（理论上不会），降级
    if current is None and nxt is None:
        return none_result

    return result


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "2026-06-05"
    print(json.dumps(solar_term_context(target), ensure_ascii=False, indent=2))
