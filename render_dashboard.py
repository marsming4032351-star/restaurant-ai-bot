#!/usr/bin/env python3
"""把 store_history.csv + daily_facts.csv 渲染进经营驾驶舱 HTML 模板。

数据流：日报流水线每天 append 两张 CSV → 本脚本读表 → 替换模板里内嵌的
`<script id="dashboard-data">` 数据块与默认日期区间 → 输出可发布的 HTML。

口径约定（见 docs/data_schema.md）：
- 核心指标取自 store_history.csv；其中 discount_rate / dine_in_ratio /
  takeaway_ratio 在该表是百分数(43.97)，本脚本统一 ÷100 转成小数(0.4397)。
- 渠道明细取自 daily_facts.csv，原值；缺失记 null（不补 0，不伪造）。
- 默认视图 = 最新数据所在月的 1 号 → 最新一天（"当月至今"）；
  内嵌全部历史，日期滑块可回看上月任意区间。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_TEMPLATE = BASE_DIR / "outputs" / "interactive_dashboard" / "malian_dao_june_sales_demo_2026-06-18.html"
DEFAULT_OUTPUT = BASE_DIR / "outputs" / "interactive_dashboard" / "dashboard_live.html"

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]
CHANNEL_FIELDS = [
    "dine_in_revenue", "takeaway_revenue", "online_revenue",
    "member_revenue", "member_recharge", "member_consumption", "coupon_amount",
]


def _num(value, *, ndigits=None, as_int=False):
    """空字符串/None -> None；否则转 float（可取整/四舍五入）。"""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None
    num = float(text)
    if as_int:
        return int(round(num))
    if ndigits is not None:
        return round(num, ndigits)
    return num


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_rows(store: str, data_dir: Path = DATA_DIR) -> list[dict]:
    """合并两张 CSV，产出与模板内嵌 JSON 同构的行数组（按日期升序）。"""
    history = _read_csv(data_dir / "store_history.csv")
    facts = _read_csv(data_dir / "daily_facts.csv")

    # daily_facts 按 (业务日期, 门店) 建索引，供渠道明细查找
    facts_index: dict[str, dict] = {}
    for f in facts:
        if (f.get("store_name") or "").strip() == store:
            facts_index[(f.get("business_date") or "").strip()] = f

    rows: list[dict] = []
    for h in history:
        if (h.get("store_name") or "").strip() != store:
            continue
        d = (h.get("date") or "").strip()
        if not d:
            continue
        wd = date.fromisoformat(d).weekday()  # 周一=0 ... 周日=6
        fact = facts_index.get(d, {})
        row = {
            "date": d,
            "weekday": WEEKDAY_CN[wd],
            "isWeekend": wd >= 5,
            "revenue": _num(h.get("revenue")),
            "customers": _num(h.get("customer_count"), as_int=True),
            "avgTicket": _num(h.get("avg_ticket")),
            "discountRate": round(_num(h.get("discount_rate")) / 100, 4) if _num(h.get("discount_rate")) is not None else None,
            "dineInRatio": round(_num(h.get("dine_in_ratio")) / 100, 4) if _num(h.get("dine_in_ratio")) is not None else None,
            "takeawayRatio": round(_num(h.get("takeaway_ratio")) / 100, 4) if _num(h.get("takeaway_ratio")) is not None else None,
            "roastDuck": _num(h.get("roast_duck_sales")),
        }
        for key in CHANNEL_FIELDS:
            row[key] = _num(fact.get(key))
        rows.append(row)

    rows.sort(key=lambda r: r["date"])
    return rows


def default_start_index(rows: list[dict]) -> int:
    """默认选中起点 = 最新数据所在月的第一条记录的下标。"""
    if not rows:
        return 0
    latest_month = rows[-1]["date"][:7]  # YYYY-MM
    for i, r in enumerate(rows):
        if r["date"][:7] == latest_month:
            return i
    return 0


def render(rows: list[dict], template_path: Path) -> str:
    html = template_path.read_text(encoding="utf-8")
    data_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    # 1) 替换内嵌数据块（按 id 精确匹配，幂等）
    html, n1 = re.subn(
        r'(<script id="dashboard-data" type="application/json">).*?(</script>)',
        lambda m: m.group(1) + data_json + m.group(2),
        html,
        count=1,
        flags=re.DOTALL,
    )
    if n1 != 1:
        raise RuntimeError("模板中未找到 <script id=\"dashboard-data\"> 数据块")

    # 2) 默认日期区间落到"当月至今"
    start = default_start_index(rows)
    html, n2 = re.subn(r"startIndex:\s*\d+", f"startIndex: {start}", html, count=1)
    if n2 != 1:
        raise RuntimeError("模板中未找到 state.startIndex 初始化")

    # 3) 让左侧起始滑块的滑块位置与默认起点同步（模板原本只设了 max 不设 value）
    html, n3 = re.subn(
        r"(\$\('startDateSlider'\)\.max = rows\.length - 1;)",
        r"\1 $('startDateSlider').value = state.startIndex;",
        html,
        count=1,
    )
    if n3 != 1:
        raise RuntimeError("模板中未找到 startDateSlider 初始化行")

    return html


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染经营驾驶舱 HTML（数据来自 CSV）")
    parser.add_argument("--store", default="便宜坊马连道", help="门店名称")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="HTML 模板路径")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出 HTML 路径")
    args = parser.parse_args()

    rows = build_rows(args.store)
    if not rows:
        print(f"[dashboard] 没有 {args.store} 的数据，未生成。")
        return 1

    html = render(rows, Path(args.template))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    start = default_start_index(rows)
    print(
        f"[dashboard] 已渲染 {len(rows)} 天（{rows[0]['date']} ~ {rows[-1]['date']}），"
        f"默认视图自 {rows[start]['date']} 起 -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
