"""周报生成器：读取 store_history.csv → AI 分析 → 飞书互动卡片推送。

用法:
    python3 weekly_report.py --last-week            # 上周一～上周日（cron 推荐）
    python3 weekly_report.py                        # 最近 7 天
    python3 weekly_report.py --days 14              # 最近 14 天
    python3 weekly_report.py --start 2026-05-20 --end 2026-05-26
    python3 weekly_report.py --store 便宜坊马连道   # 指定门店
    python3 weekly_report.py --last-week --dry-run  # 验证范围，不推送
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import config
import feishu_bot
import solar_terms

# ─────────────────────────────────────────────────────────
# 1. 读取历史数据
# ─────────────────────────────────────────────────────────
HISTORY_FILE = config.DATA_DIR / "store_history.csv"


def load_rows(store: str, start: date, end: date) -> list[dict]:
    """从 CSV 读取指定门店、日期范围内的行，按日期升序排列。"""
    if not HISTORY_FILE.exists():
        raise FileNotFoundError(f"找不到历史数据文件: {HISTORY_FILE}")

    rows = []
    with open(HISTORY_FILE, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                d = date.fromisoformat(row["date"])
            except ValueError:
                continue
            if row.get("store_name", "").strip() != store.strip():
                continue
            if start <= d <= end:
                rows.append({**row, "_date": d})

    rows.sort(key=lambda r: r["_date"])
    return rows


# ─────────────────────────────────────────────────────────
# 2. 统计计算
# ─────────────────────────────────────────────────────────
def _f(row: dict, key: str, default=0.0) -> float:
    try:
        return float(row.get(key) or default)
    except ValueError:
        return default


def calc_stats(rows: list[dict]) -> dict:
    """把 CSV 行列表转成周报统计 dict。"""
    if not rows:
        return {}

    revenues      = [_f(r, "revenue")        for r in rows]
    customers     = [_f(r, "customer_count") for r in rows]
    avg_tickets   = [_f(r, "avg_ticket")     for r in rows]
    discount_rates= [_f(r, "discount_rate")  for r in rows]
    duck_sales    = [_f(r, "roast_duck_sales") for r in rows]
    dates         = [r["_date"]              for r in rows]

    total_rev  = sum(revenues)
    total_cust = sum(customers)
    n          = len(rows)

    best_idx  = revenues.index(max(revenues))
    worst_idx = revenues.index(min(revenues))

    # 折扣率异常日（>40%）
    high_disc = [
        {"date": str(r["_date"]), "rate": _f(r, "discount_rate"),
         "summary": r.get("summary", "")}
        for r in rows if _f(r, "discount_rate") > 40
    ]

    # 烤鸭趋势：带简单 emoji 箭头
    duck_trend_items = []
    for i, r in enumerate(rows):
        qty = _f(r, "roast_duck_sales")
        if i == 0:
            arrow = "—"
        elif qty > duck_sales[i - 1]:
            arrow = "↑"
        elif qty < duck_sales[i - 1]:
            arrow = "↓"
        else:
            arrow = "→"
        duck_trend_items.append(
            f"{r['_date'].strftime('%m/%d')} {arrow}{qty:.0f}只"
        )

    # 警示天数统计
    warning_counts = {"健康": 0, "警示": 0, "异常": 0}
    for r in rows:
        lv = r.get("warning_level", "")
        if lv in warning_counts:
            warning_counts[lv] += 1

    # ISO 周数（取最后一天）
    iso = dates[-1].isocalendar()
    week_num = iso[1]
    year     = iso[0]

    return {
        "store_name":   rows[0].get("store_name", ""),
        "start_date":   str(dates[0]),
        "end_date":     str(dates[-1]),
        "n_days":       n,
        "year":         year,
        "week_num":     week_num,
        # KPI
        "total_revenue":     round(total_rev, 2),
        "daily_avg_revenue": round(total_rev / n, 2),
        "total_customers":   int(total_cust),
        "avg_ticket":        round(total_rev / total_cust, 2) if total_cust else 0,
        # 最高 / 最低
        "best_day":  {"date": str(dates[best_idx]),  "revenue": revenues[best_idx],
                      "summary": rows[best_idx].get("summary", "")},
        "worst_day": {"date": str(dates[worst_idx]), "revenue": revenues[worst_idx],
                      "summary": rows[worst_idx].get("summary", "")},
        # 折扣
        "avg_discount_rate": round(sum(discount_rates) / n, 2),
        "high_discount_days": high_disc,
        # 烤鸭
        "duck_trend":      duck_trend_items,
        "duck_total_week": round(sum(duck_sales), 1),
        "duck_daily_avg":  round(sum(duck_sales) / n, 1),
        # 警示
        "warning_counts": warning_counts,
        # 原始行（给 LLM 用）
        "raw_rows": [
            {"date": str(r["_date"]), "revenue": _f(r, "revenue"),
             "customer_count": int(_f(r, "customer_count")),
             "avg_ticket": _f(r, "avg_ticket"),
             "discount_rate": _f(r, "discount_rate"),
             "roast_duck_sales": _f(r, "roast_duck_sales"),
             "warning_level": r.get("warning_level", ""),
             "summary": r.get("summary", "")}
            for r in rows
        ],
    }


# ─────────────────────────────────────────────────────────
# 3. LLM 分析
# ─────────────────────────────────────────────────────────
WEEKLY_SYSTEM = """你是一个连锁餐饮经营分析师，擅长从多日数据中发现趋势、定位问题。
请根据提供的周度经营数据，输出结构化 JSON，格式如下：
{
  "main_issues": ["问题1", "问题2", "问题3"],
  "next_week_suggestions": ["建议1", "建议2", "建议3"],
  "trend_summary": "一句话描述本周整体趋势",
  "focus_metric": "下周最需关注的一个指标名称"
}
要求：
- main_issues 列出 2~4 条本周核心问题，每条≤40字，直接说问题不要废话
- next_week_suggestions 给出 2~4 条可执行建议，每条≤50字，具体到操作动作
- trend_summary 不超过 30 字
- 输出纯 JSON，不要 markdown 包裹"""


# ─────────────────────────────────────────────────────────
# 3.5 天气 / 节气观察（确定性附加层，绝不伪造数据）
# ─────────────────────────────────────────────────────────
# 节气 → 简短「相关性」经营提示（保守措辞，不下因果结论）。
# 表内没有的节气，统一退回到通用提示，绝不编造影响结论。
_SOLAR_HINTS = {
    "立春": "初春乍暖还寒，可关注暖锅、热饮与家庭聚餐需求。",
    "雨水": "天气多变偏湿，留意外卖保温与到店客流波动。",
    "惊蛰": "气温回升，可逐步增加清爽菜品比重。",
    "春分": "昼夜均衡、踏青出行增多，周末堂食客流或上升。",
    "清明": "假期与祭扫出行叠加，外卖与家庭套餐需求可提前备货。",
    "谷雨": "暮春多雨，关注雨天到店下滑与外卖补位。",
    "立夏": "天气转暖，可关注清爽菜品与冰饮需求。",
    "小满": "湿热渐起，留意凉菜备货与外卖保温。",
    "芒种": "进入初夏湿热期，凉菜、饮品、降温外卖需求或上升。",
    "夏至": "盛夏高温临近，午市清淡套餐与冷饮可重点准备。",
    "小暑": "高温持续，关注堂食空调体验与清爽出品。",
    "大暑": "最热时段，午市客流或受高温影响，可加强夜市与外卖。",
    "立秋": "暑热渐退，可逐步恢复滋补、暖食类菜品推荐。",
    "处暑": "昼热夜凉，关注晚市客流回升与套餐组合。",
    "白露": "天气转凉，暖锅、热汤类需求或回升。",
    "秋分": "天高气爽、出行增多，周末聚餐可加强引导。",
    "寒露": "气温走低，进补与热食类可提前准备。",
    "霜降": "深秋转寒，暖锅、套餐类需求或上升。",
    "立冬": "进入冬季，聚餐与进补需求增加，套餐可重点推荐。",
    "小雪": "天气寒冷，外卖保温与到店暖食体验需关注。",
    "大雪": "严寒时段，聚餐、暖锅与节庆套餐需求或走高。",
    "冬至": "进补与聚餐高峰，套餐、暖锅类可提前备货。",
    "小寒": "一年最冷时段之一，关注堂食保暖与外卖时效。",
    "大寒": "严寒持续，节前聚餐与年货套餐需求可提前布局。",
}


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _is_blank_weather(text) -> bool:
    if text is None:
        return True
    s = str(text).strip()
    return s == "" or s in ("暂无", "未采集", "no_data", "无数据", "None")


def build_weather_solar_observation(
    start_date,
    end_date,
    *,
    weather_text=None,
    terms_table: dict | None = None,
) -> dict:
    """构建「本周天气 / 节气观察」（确定性 + 可降级）。

    - 节气来自 solar_terms（确定性、权威表），表未覆盖年份诚实记 no_data。
    - 天气为可选弱参考；缺失时明确写「数据不完整」，绝不伪造。
    - 措辞只做相关性观察，不下因果结论。
    返回 dict：solar_term_status / solar_term_text / weather_text /
    weather_available / hints / lines。
    """
    start = _as_date(start_date)
    end = _as_date(end_date)
    if end < start:
        start, end = end, start

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    term_days: list[tuple[date, str]] = []
    current_term = None
    status_ok = False
    for d in days:
        ctx = solar_terms.solar_term_context(d, terms_table)
        if ctx.get("solar_term_status") == "ok":
            status_ok = True
            current_term = ctx.get("current_solar_term") or current_term
            if ctx.get("is_solar_term_day") and ctx.get("solar_term_today"):
                term_days.append((d, ctx["solar_term_today"]))

    if not status_ok:
        solar_term_text = "暂无（节气表未覆盖该年份）"
    elif term_days:
        solar_term_text = "、".join(f"{d.month}/{d.day} {n}" for d, n in term_days)
    elif current_term:
        solar_term_text = f"无关键节气（本周处于{current_term}）"
    else:
        solar_term_text = "无关键节气"

    # 节气经营提示：优先用本周内出现的节气，否则用当前所处节气。
    hint_terms = [n for _, n in term_days] or ([current_term] if current_term else [])
    hints: list[str] = []
    for name in hint_terms:
        hint = _SOLAR_HINTS.get(name)
        if hint and hint not in hints:
            hints.append(hint)
    if status_ok and not hints:
        hints.append("可结合当前节气适度调整菜品结构与活动节奏。")

    if _is_blank_weather(weather_text):
        weather_out = "本周天气数据不完整（高德免费版无历史天气），仅作弱参考。"
        weather_available = False
    else:
        weather_out = str(weather_text).strip()
        weather_available = True

    lines = [f"本周节气：{solar_term_text}", f"天气概况：{weather_out}"]
    for hint in hints[:2]:
        lines.append(f"经营提示：{hint}")

    return {
        "solar_term_status": "ok" if status_ok else "no_data",
        "solar_term_text": solar_term_text,
        "weather_text": weather_out,
        "weather_available": weather_available,
        "hints": hints[:2],
        "lines": lines,
    }


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"LLM 返回里找不到 JSON:\n{text[:500]}")


def analyze(stats: dict) -> dict:
    """调 LLM 生成周报分析。"""
    user_data = {k: v for k, v in stats.items() if k != "raw_rows"}
    user_data["daily_detail"] = stats["raw_rows"]
    user_msg = "请分析以下周度经营数据：\n```json\n" + \
               json.dumps(user_data, ensure_ascii=False, indent=2) + "\n```"

    if config.LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
        resp = client.messages.create(
            model=config.LLM_MODEL, max_tokens=1500,
            system=WEEKLY_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text
    else:
        from openai import OpenAI
        kwargs = {"api_key": config.LLM_API_KEY}
        if config.LLM_BASE_URL:
            kwargs["base_url"] = config.LLM_BASE_URL
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=config.LLM_MODEL, temperature=0.3,
            messages=[
                {"role": "system", "content": WEEKLY_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
        )
        raw = resp.choices[0].message.content

    result = _extract_json(raw)
    result.setdefault("main_issues", [])
    result.setdefault("next_week_suggestions", [])
    result.setdefault("trend_summary", "")
    result.setdefault("focus_metric", "")
    # 天气 / 节气观察：确定性附加层，失败不影响主流程
    try:
        s = stats.get("period_start_date") or stats.get("start_date")
        e = stats.get("period_end_date") or stats.get("end_date")
        if s and e:
            result["weather_solar_summary"] = build_weather_solar_observation(s, e)
    except Exception as exc:  # pragma: no cover - 附加层不得阻断周报
        print(f"[weekly] 天气/节气观察生成失败（已跳过）: {exc}")
    return result


# ─────────────────────────────────────────────────────────
# 4. 飞书互动卡片
# ─────────────────────────────────────────────────────────
def _col(weight: int, *lines: str) -> dict:
    return {
        "tag": "column", "width": "weighted", "weight": weight,
        "vertical_align": "center",
        "elements": [{"tag": "div",
                       "text": {"tag": "lark_md", "content": "\n".join(lines)}}],
    }


def build_card(stats: dict, analysis: dict) -> dict:
    store   = stats["store_name"]
    w_num   = stats["week_num"]
    year    = stats["year"]
    s_date  = stats.get("period_start_date", stats["start_date"])
    e_date  = stats.get("period_end_date", stats["end_date"])
    n_days  = stats["n_days"]
    expected_days = stats.get("expected_days", n_days)
    missing_dates = stats.get("missing_dates", [])

    title = f"{store} · {year}年第{w_num}周经营周报"

    # 警示等级 → 卡片颜色
    wc = stats["warning_counts"]
    if wc.get("异常", 0) > 0:
        header_color = "red"
    elif wc.get("警示", 0) > 0:
        header_color = "orange"
    else:
        header_color = "wathet"   # 蓝色 = 正常周报

    elems = []

    if missing_dates:
        elems.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**本周数据不完整，缺少以下日期：{'、'.join(missing_dates)}**",
            },
        })
        elems.append({"tag": "hr"})

    # ── KPI 4 列 ──────────────────────────────────────────
    elems.append({
        "tag": "column_set", "flex_mode": "none", "background_style": "grey",
        "columns": [
            _col(1, "**本周总收入**", f"¥{stats['total_revenue']:,.0f}"),
            _col(1, "**日均收入**",   f"¥{stats['daily_avg_revenue']:,.0f}"),
            _col(1, "**总来客数**",   f"{stats['total_customers']:,} 人"),
            _col(1, "**平均客单价**", f"¥{stats['avg_ticket']:.2f}"),
        ],
    })

    # ── 趋势总结 ──────────────────────────────────────────
    trend = analysis.get("trend_summary", "")
    if trend:
        elems.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"📝 {trend}"},
        })

    elems.append({"tag": "hr"})

    # ── 最高 / 最低收入日 ─────────────────────────────────
    best  = stats["best_day"]
    worst = stats["worst_day"]
    elems.append({
        "tag": "column_set", "flex_mode": "none", "background_style": "default",
        "columns": [
            _col(1,
                 "**🏆 最高收入日**",
                 f"{best['date']}　¥{best['revenue']:,.0f}",
                 f"<font color='grey'>{best['summary'][:30]}{'…' if len(best['summary'])>30 else ''}</font>"),
            _col(1,
                 "**📉 最低收入日**",
                 f"{worst['date']}　¥{worst['revenue']:,.0f}",
                 f"<font color='grey'>{worst['summary'][:30]}{'…' if len(worst['summary'])>30 else ''}</font>"),
        ],
    })

    elems.append({"tag": "hr"})

    # ── 折扣率 ────────────────────────────────────────────
    avg_disc = stats["avg_discount_rate"]
    disc_color = "red" if avg_disc > 45 else ("orange" if avg_disc > 40 else "green")
    disc_header = f"**💳 折扣率**　周均 <font color='{disc_color}'>{avg_disc:.1f}%</font>"

    high_disc = stats["high_discount_days"]
    if high_disc:
        disc_lines = [disc_header, "⚠️ 异常日（>40%）："]
        for d in high_disc:
            disc_lines.append(f"  · {d['date']}　{d['rate']:.1f}%　{d['summary'][:25]}")
    else:
        disc_lines = [disc_header, "✅ 本周无折扣率异常日"]

    elems.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "\n".join(disc_lines)},
    })

    elems.append({"tag": "hr"})

    # ── 烤鸭销量趋势 ──────────────────────────────────────
    duck_trend_str = "　".join(stats["duck_trend"])
    elems.append({
        "tag": "div",
        "text": {"tag": "lark_md",
                 "content": (
                     f"**🦆 烤鸭销量趋势**　"
                     f"周累计 {stats['duck_total_week']:.0f} 只　"
                     f"日均 {stats['duck_daily_avg']:.1f} 只\n"
                     f"{duck_trend_str}"
                 )},
    })

    elems.append({"tag": "hr"})

    # ── 天气 / 节气观察（确定性附加层） ───────────────────
    ws = analysis.get("weather_solar_summary") or {}
    ws_lines = ws.get("lines") or []
    if ws_lines:
        ws_content = ["**🌤️ 天气 / 节气观察**", *ws_lines]
        elems.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(ws_content)},
        })
        elems.append({"tag": "hr"})

    # ── 本周主要问题（LLM） ───────────────────────────────
    issues = analysis.get("main_issues", [])
    if issues:
        issue_lines = ["**⚠️ 本周主要问题**"]
        for i, iss in enumerate(issues, 1):
            issue_lines.append(f"{i}. {iss}")
        elems.append({"tag": "div",
                      "text": {"tag": "lark_md", "content": "\n".join(issue_lines)}})
        elems.append({"tag": "hr"})

    # ── 下周经营建议（LLM） ───────────────────────────────
    sugs = analysis.get("next_week_suggestions", [])
    if sugs:
        sug_lines = ["**💡 下周经营建议**"]
        for i, s in enumerate(sugs, 1):
            sug_lines.append(f"{i}. {s}")
        elems.append({"tag": "div",
                      "text": {"tag": "lark_md", "content": "\n".join(sug_lines)}})

    # ── 警示统计 + 数据范围（note） ───────────────────────
    warn_str = (f"🟢健康{wc.get('健康',0)}天　"
                f"🟡警示{wc.get('警示',0)}天　"
                f"🔴异常{wc.get('异常',0)}天")
    focus = analysis.get("focus_metric", "")
    note_parts = [f"数据范围：{s_date} ～ {e_date}（已有{n_days}/{expected_days}天）　{warn_str}"]
    if missing_dates:
        note_parts.append(f"本周缺失数据：{'、'.join(missing_dates)}")
    else:
        note_parts.append("本周数据完整")
    if focus:
        note_parts.append(f"🔎 下周重点指标：{focus}")
    elems.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "　|　".join(note_parts)}],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": header_color,
        },
        "elements": elems,
    }


# ─────────────────────────────────────────────────────────
# 5. 推送
# ─────────────────────────────────────────────────────────
def push(card: dict) -> None:
    import requests
    feishu_bot._check_webhook()
    resp = requests.post(
        feishu_bot.WEBHOOK,
        json={"msg_type": "interactive", "card": card},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书推送失败: {data}")
    print("[weekly] ✅ 周报已推送到飞书群")


# ─────────────────────────────────────────────────────────
# 6. 入口
# ─────────────────────────────────────────────────────────
def _last_week_range() -> tuple[date, date]:
    """返回上周一和上周日的日期。

    无论今天是星期几，都指向「已结束的上一整周」。
    例：今天 2026-06-01（周一）→ 2026-05-25 ～ 2026-05-31
        今天 2026-06-03（周三）→ 2026-05-25 ～ 2026-05-31
    """
    today = date.today()
    # weekday(): 周一=0, 周日=6
    # 距离「上周一」的天数 = 今天是本周第几天(0-based) + 7
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday


def main():
    ap = argparse.ArgumentParser(description="生成并推送经营周报")
    ap.add_argument("--store",     default="便宜坊马连道",
                    help="门店名称（同 store_history.csv 里的 store_name）")
    ap.add_argument("--last-week", action="store_true",
                    help="统计上周一～上周日（cron 自动推送推荐用此参数）")
    ap.add_argument("--days",  type=int, default=7,
                    help="统计最近 N 天，默认 7（--last-week 优先）")
    ap.add_argument("--start", help="起始日期 YYYY-MM-DD（与 --end 配合使用）")
    ap.add_argument("--end",   help="结束日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印统计和卡片 JSON，不推送飞书")
    args = ap.parse_args()
    strict_weekly_date_check = config.STRICT_WEEKLY_DATE_CHECK

    # 确定日期范围（优先级：--last-week > --start/--end > --days）
    if args.last_week:
        start, end = _last_week_range()
        print(f"[weekly] --last-week 模式：统计上周 {start}（周一）～ {end}（周日）")
    elif args.start:
        start = date.fromisoformat(args.start)
        end   = date.fromisoformat(args.end) if args.end else date.today()
    else:
        end   = date.fromisoformat(args.end) if args.end else date.today()
        start = end - timedelta(days=args.days - 1)

    print(f"[weekly] 门店: {args.store}  范围: {start} ～ {end}")

    # 1. 读数据
    rows = load_rows(args.store, start, end)
    if not rows:
        print(f"[weekly] ❌ 在 {HISTORY_FILE} 中没有找到 {args.store} 在 {start}～{end} 的数据。")
        print("[weekly]    请先运行 main.py 生成日报以积累历史数据。")
        sys.exit(1)
    print(f"[weekly] 找到 {len(rows)} 天数据（{rows[0]['_date']} ～ {rows[-1]['_date']}）")

    # 2. 统计
    stats = calc_stats(rows)
    expected = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    found = {r["_date"] for r in rows}
    stats["period_start_date"] = str(start)
    stats["period_end_date"] = str(end)
    stats["expected_days"] = len(expected)
    stats["missing_dates"] = [str(d) for d in expected if d not in found]
    if stats["missing_dates"]:
        print(f"[weekly] 本周缺失数据: {', '.join(stats['missing_dates'])}")
        if strict_weekly_date_check:
            print("[weekly] strict_weekly_date_check=true，缺少日期，停止推送。")
            sys.exit(1)
    print(f"[weekly] 本周总收入: ¥{stats['total_revenue']:,.2f}　"
          f"日均: ¥{stats['daily_avg_revenue']:,.2f}　"
          f"烤鸭: {stats['duck_total_week']}只")

    # 3. AI 分析
    print(f"[weekly] AI 分析 (model={config.LLM_MODEL})...")
    analysis = analyze(stats)
    print(f"[weekly] 趋势总结: {analysis.get('trend_summary', '')}")

    # 4. 构造卡片
    card = build_card(stats, analysis)

    if args.dry_run:
        print("\n[weekly] --dry-run 模式，卡片 JSON 如下：")
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return

    # 5. 推送
    push(card)


if __name__ == "__main__":
    main()
