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
from datetime import date, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import weekly_report


WIDTH = 1600
HEIGHT = 900


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


def as_float(row: dict, key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


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

    dine_in = sum(as_float(r, "revenue") * as_float(r, "dine_in_ratio") / 100 for r in rows)
    takeaway = sum(as_float(r, "revenue") * as_float(r, "takeaway_ratio") / 100 for r in rows)
    other = max(stats["total_revenue"] - dine_in - takeaway, 0)
    has_structure = dine_in > 0 or takeaway > 0
    structure = (
        [
            {"name": "堂食", "value": round(dine_in, 2)},
            {"name": "外卖", "value": round(takeaway, 2)},
            {"name": "其他", "value": round(other, 2)},
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
        "missing_dates": missing_dates,
        "date_check_status": stats["date_check_status"],
    }


def echarts_option(context: dict) -> dict:
    return {
        "backgroundColor": "#08111f",
        "color": ["#42d7ff", "#8b5cf6", "#18e3b7", "#ffcf5a", "#ff6b8a"],
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 45, "right": 30, "top": 45, "bottom": 35},
        "xAxis": {"type": "category", "data": context["labels"], "axisLabel": {"color": "#b9c7e6"}},
        "yAxis": {"type": "value", "axisLabel": {"color": "#b9c7e6"}, "splitLine": {"lineStyle": {"color": "#20314f"}}},
        "series": [
            {
                "name": "营业额",
                "type": "bar",
                "barWidth": "42%",
                "data": context["revenues"],
                "itemStyle": {"borderRadius": [6, 6, 0, 0]},
            }
        ],
    }


def render_html(context: dict, html_path: Path) -> Path:
    title = html.escape(context["title"])
    missing = "、".join(context["missing_dates"]) if context["missing_dates"] else "无"
    stats = context["stats"]
    option_json = json.dumps(echarts_option(context), ensure_ascii=False)
    pie_data = json.dumps(context["structure"], ensure_ascii=False)
    top_names = json.dumps([item["date"] for item in reversed(context["top_revenue"])], ensure_ascii=False)
    top_values = json.dumps([item["revenue"] for item in reversed(context["top_revenue"])], ensure_ascii=False)
    line_labels = json.dumps(context["labels"], ensure_ascii=False)
    revenues = json.dumps(context["revenues"], ensure_ascii=False)
    customers = json.dumps(context["customers"], ensure_ascii=False)
    strengths = json.dumps(context["strengths"], ensure_ascii=False)

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
    .kpis {{ display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:16px; }}
    .kpi,.card {{ border:1px solid rgba(91,141,255,.28); background:linear-gradient(180deg,rgba(21,39,75,.88),rgba(8,17,31,.9)); border-radius:8px; box-shadow:0 0 22px rgba(66,215,255,.08) inset; }}
    .kpi {{ padding:14px 16px; min-height:92px; }}
    .kpi span {{ display:block; color:#8ea4cf; font-size:14px; margin-bottom:10px; }}
    .kpi strong {{ font-size:24px; color:#fff; }}
    .grid {{ display:grid; grid-template-columns:2fr 1.15fr 1.15fr; grid-template-rows:245px 245px; gap:14px; }}
    .card {{ padding:12px; min-width:0; }}
    .card-title {{ color:#b9d7ff; font-size:15px; margin:0 0 8px; }}
    .chart {{ width:100%; height:calc(100% - 24px); }}
    .empty {{ height:calc(100% - 24px); display:flex; align-items:center; justify-content:center; color:#7f90b8; border:1px dashed rgba(142,164,207,.35); border-radius:8px; }}
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
    <div class="kpi"><span>本周总营业额</span><strong>¥{stats["total_revenue"]:,.0f}</strong></div>
    <div class="kpi"><span>日均营业额</span><strong>¥{stats["daily_avg_revenue"]:,.0f}</strong></div>
    <div class="kpi"><span>最高营业日</span><strong>{stats["best_day"]["date"]}</strong></div>
    <div class="kpi"><span>最低营业日</span><strong>{stats["worst_day"]["date"]}</strong></div>
    <div class="kpi"><span>周报天数</span><strong>{stats["n_days"]}/{stats["expected_days"]}</strong></div>
    <div class="kpi"><span>缺失日期</span><strong>{html.escape(missing)}</strong></div>
  </section>
  <section class="grid">
    <div class="card"><p class="card-title">本周每日营业额柱状图</p><div id="bar" class="chart"></div></div>
    <div class="card"><p class="card-title">本周每日客流折线图</p><div id="line" class="chart"></div></div>
    <div class="card"><p class="card-title">本周收入结构饼图</p>{'<div id="pie" class="chart"></div>' if context["structure"] else '<div class="empty">暂无分类数据</div>'}</div>
    <div class="card"><p class="card-title">本周营业额趋势面积图</p><div id="area" class="chart"></div></div>
    <div class="card"><p class="card-title">TOP 指标横向条形图</p><div id="top" class="chart"></div></div>
    <div class="card"><p class="card-title">一周经营强弱极坐标图</p><div id="polar" class="chart"></div></div>
  </section>
</main>
<script>
const baseText = {{ color: '#b9c7e6' }};
echarts.init(document.getElementById('bar')).setOption({option_json});
echarts.init(document.getElementById('line')).setOption({{
  tooltip: {{ trigger:'axis' }},
  xAxis: {{ type:'category', data:{line_labels}, axisLabel:baseText }},
  yAxis: {{ type:'value', axisLabel:baseText, splitLine:{{ lineStyle:{{ color:'#20314f' }} }} }},
  series:[{{ name:'客流', type:'line', smooth:true, data:{customers}, lineStyle:{{ width:4 }}, areaStyle:{{ opacity:.08 }} }}]
}});
if (document.getElementById('pie')) echarts.init(document.getElementById('pie')).setOption({{
  tooltip: {{ trigger:'item' }},
  series:[{{ type:'pie', radius:['42%','70%'], data:{pie_data}, label:{{ color:'#dfe9ff' }} }}]
}});
echarts.init(document.getElementById('area')).setOption({{
  tooltip: {{ trigger:'axis' }},
  xAxis: {{ type:'category', data:{line_labels}, axisLabel:baseText }},
  yAxis: {{ type:'value', axisLabel:baseText, splitLine:{{ lineStyle:{{ color:'#20314f' }} }} }},
  series:[{{ name:'营业额趋势', type:'line', smooth:true, data:{revenues}, areaStyle:{{ opacity:.32 }}, lineStyle:{{ width:4 }} }}]
}});
echarts.init(document.getElementById('top')).setOption({{
  grid: {{ left:86, right:20, top:20, bottom:20 }},
  xAxis: {{ type:'value', axisLabel:baseText, splitLine:{{ lineStyle:{{ color:'#20314f' }} }} }},
  yAxis: {{ type:'category', data:{top_names}, axisLabel:baseText }},
  series:[{{ type:'bar', data:{top_values}, itemStyle:{{ borderRadius:[0,6,6,0] }} }}]
}});
echarts.init(document.getElementById('polar')).setOption({{
  angleAxis: {{ type:'category', data:{line_labels}, axisLabel:baseText }},
  radiusAxis: {{ axisLabel:baseText }},
  polar: {{}},
  series:[{{ type:'bar', coordinateSystem:'polar', data:{strengths}, roundCap:true }}]
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
        ("本周总营业额", f"¥{stats['total_revenue']:,.0f}"),
        ("日均营业额", f"¥{stats['daily_avg_revenue']:,.0f}"),
        ("最高营业日", stats["best_day"]["date"]),
        ("最低营业日", stats["worst_day"]["date"]),
        ("周报天数", f"{stats['n_days']}/{stats['expected_days']}"),
        ("缺失日期", "无" if not context["missing_dates"] else "、".join(context["missing_dates"])),
    ]
    card_w = (WIDTH - 112 - 5 * 12) // 6
    for idx, (label, value) in enumerate(kpis):
        x = 56 + idx * (card_w + 12)
        draw.rounded_rectangle((x, y, x + card_w, y + 92), radius=8, fill="#102340", outline="#2b62aa")
        draw.text((x + 14, y + 14), label, fill="#8ea4cf", font=small_font)
        draw.text((x + 14, y + 48), value, fill="#ffffff", font=number_font if idx < 2 else text_font)
    y += 112

    def panel(box, title):
        draw.rounded_rectangle(box, radius=8, fill="#0d1d36", outline="#264f8a")
        draw.text((box[0] + 16, box[1] + 12), title, fill="#b9d7ff", font=text_font)

    panel((56, y, 760, y + 275), "本周每日营业额柱状图")
    panel((780, y, 1160, y + 275), "本周每日客流折线图")
    panel((1180, y, WIDTH - 56, y + 275), "本周收入结构饼图")
    y2 = y + 295
    panel((56, y2, 760, y2 + 275), "本周营业额趋势面积图")
    panel((780, y2, 1160, y2 + 275), "TOP 指标横向条形图")
    panel((1180, y2, WIDTH - 56, y2 + 275), "一周经营强弱极坐标图")

    def plot_area(box):
        x1, y1, x2, y2p = box
        values = [v or 0 for v in context["revenues"]]
        max_v = max(values or [1]) or 1
        points = []
        for i, value in enumerate(values):
            x = x1 + 30 + i * ((x2 - x1 - 70) / max(1, len(values) - 1))
            yv = y2p - 36 - (value / max_v) * (y2p - y1 - 86)
            points.append((x, yv))
        if len(points) > 1:
            draw.polygon([(points[0][0], y2p - 36), *points, (points[-1][0], y2p - 36)], fill="#163d64")
            draw.line(points, fill="#42d7ff", width=4)
        for i, p in enumerate(points):
            draw.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill="#18e3b7")
            draw.text((p[0] - 16, y2p - 26), context["labels"][i], fill="#8ea4cf", font=small_font)

    def plot_line(box):
        x1, y1, x2, y2p = box
        values = [v or 0 for v in context["customers"]]
        max_v = max(values or [1]) or 1
        points = []
        for i, value in enumerate(values):
            x = x1 + 32 + i * ((x2 - x1 - 70) / max(1, len(values) - 1))
            yv = y2p - 36 - (value / max_v) * (y2p - y1 - 86)
            points.append((x, yv))
        if len(points) > 1:
            draw.line(points, fill="#8b5cf6", width=4)
        for i, p in enumerate(points):
            draw.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill="#ffcf5a")
            draw.text((p[0] - 16, y2p - 26), context["labels"][i], fill="#8ea4cf", font=small_font)

    def plot_pie(box):
        x1, y1, x2, y2p = box
        data = context["structure"]
        if not data:
            draw.text((x1 + 120, y1 + 126), "暂无分类数据", fill="#7f90b8", font=text_font)
            return
        total = sum(item["value"] for item in data) or 1
        colors = ["#42d7ff", "#8b5cf6", "#18e3b7"]
        cx1, cy1, cx2, cy2 = x1 + 92, y1 + 74, x1 + 248, y1 + 230
        start_angle = 0
        for idx, item in enumerate(data):
            angle = 360 * item["value"] / total
            draw.pieslice((cx1, cy1, cx2, cy2), start_angle, start_angle + angle, fill=colors[idx % len(colors)])
            draw.rectangle((x1 + 260, y1 + 86 + idx * 34, x1 + 278, y1 + 104 + idx * 34), fill=colors[idx % len(colors)])
            draw.text((x1 + 286, y1 + 84 + idx * 34), item["name"], fill="#dfe9ff", font=small_font)
            start_angle += angle

    def plot_top(box):
        x1, y1, x2, y2p = box
        items = context["top_revenue"][:5]
        max_v = max([item["revenue"] for item in items] or [1])
        for i, item in enumerate(items):
            yv = y1 + 58 + i * 38
            width = int((item["revenue"] / max_v) * (x2 - x1 - 150))
            draw.text((x1 + 18, yv), item["date"][5:], fill="#b9c7e6", font=small_font)
            draw.rounded_rectangle((x1 + 82, yv, x1 + 82 + width, yv + 18), radius=5, fill="#42d7ff")

    def plot_polar(box):
        x1, y1, x2, y2p = box
        cx, cy = (x1 + x2) / 2, (y1 + y2p) / 2 + 12
        radius = 82
        for r in (28, 56, 84):
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline="#20314f")
        points = []
        n = len(context["strengths"])
        for i, score in enumerate(context["strengths"]):
            angle = -math.pi / 2 + 2 * math.pi * i / max(1, n)
            rr = radius * (score / 100)
            px, py = cx + math.cos(angle) * rr, cy + math.sin(angle) * rr
            points.append((px, py))
            lx, ly = cx + math.cos(angle) * (radius + 24), cy + math.sin(angle) * (radius + 24)
            draw.text((lx - 16, ly - 8), context["labels"][i], fill="#8ea4cf", font=small_font)
        if len(points) > 2:
            draw.polygon(points, fill="#1d4f73", outline="#18e3b7")

    values = [v or 0 for v in context["revenues"]]
    max_val = max(values or [1]) or 1
    base_y = y + 238
    bar_area_x = 92
    bar_w = 72
    for i, value in enumerate(values):
        x = bar_area_x + i * 90
        h = int((value / max_val) * 160)
        draw.rectangle((x, base_y - h, x + bar_w, base_y), fill="#42d7ff")
        draw.text((x + 8, base_y + 8), context["labels"][i], fill="#8ea4cf", font=small_font)

    plot_line((780, y, 1160, y + 275))
    plot_pie((1180, y, WIDTH - 56, y + 275))
    plot_area((56, y2, 760, y2 + 275))
    plot_top((780, y2, 1160, y2 + 275))
    plot_polar((1180, y2, WIDTH - 56, y2 + 275))

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


def push_to_feishu(png_path: Path) -> None:
    import feishu_bot

    if not feishu_bot._has_app_creds():
        raise RuntimeError("未配置飞书 App 图片上传凭证，已跳过图片推送")
    key = feishu_bot._upload_image(Path(png_path))
    feishu_bot._send_image_key(key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成周报可视化看板 HTML/PNG")
    parser.add_argument("--store", required=True, help="门店名称，例如 便宜坊马连道")
    parser.add_argument("--start-date", required=True, help="周报开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="周报结束日期 YYYY-MM-DD")
    parser.add_argument("--history-path", default=str(config.DATA_DIR / "store_history.csv"), help="历史数据 CSV")
    parser.add_argument("--output-dir", default=str(config.OUTPUT_DIR), help="输出目录")
    parser.add_argument("--strict-weekly-date-check", action="store_true", help="缺失日期时停止生成")
    parser.add_argument("--push-feishu", action="store_true", help="生成后推送 PNG 到飞书；默认不推送")
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
    if args.push_feishu:
        push_to_feishu(Path(result["png_path"]))
        print("[weekly-dashboard] 已推送看板图片到飞书")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
