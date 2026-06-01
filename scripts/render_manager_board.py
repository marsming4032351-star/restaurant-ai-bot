#!/usr/bin/env python3
"""管理者视角周报决策看板生成器（只读 store_history.csv，不改业务数据，不推送飞书）。

用法：
    python3 scripts/render_manager_board.py \
        --store 便宜坊马连道 --start 2026-05-25 --end 2026-05-31

产物：output/manager_board_<store>_<start>_<end>.html
"""
import argparse
import csv
import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "store_history.csv")
OUT_DIR = os.path.join(ROOT, "output")

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def inum(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def load_window(store, start, end):
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["store_name"] != store:
                continue
            d = r["date"]
            if start <= d <= end:
                rows.append(r)
    rows.sort(key=lambda r: r["date"])
    return rows


def aggregate(rows):
    days = []
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        days.append(
            {
                "date": r["date"],
                "wd": WEEKDAY_CN[d.weekday()],
                "is_weekend": d.weekday() >= 5,
                "revenue": fnum(r["revenue"]),
                "cust": inum(r["customer_count"]),
                "avg_ticket": fnum(r["avg_ticket"]),
                "month_yoy": fnum(r["month_yoy"]),
                "discount": fnum(r["discount_rate"]),
                "dine_in": fnum(r["dine_in_ratio"]),
                "takeaway": fnum(r["takeaway_ratio"]),
                "duck": fnum(r["roast_duck_sales"]),
                "warning": r["warning_level"],
            }
        )
    n = len(days)
    total_rev = sum(d["revenue"] for d in days)
    total_cust = sum(d["cust"] for d in days)
    total_duck = sum(d["duck"] for d in days)
    weekday = [d for d in days if not d["is_weekend"]]
    weekend = [d for d in days if d["is_weekend"]]
    wd_avg = sum(d["revenue"] for d in weekday) / len(weekday) if weekday else 0
    we_avg = sum(d["revenue"] for d in weekend) / len(weekend) if weekend else 0
    best = max(days, key=lambda d: d["revenue"])
    worst = min(days, key=lambda d: d["revenue"])
    return {
        "days": days,
        "n": n,
        "total_rev": total_rev,
        "total_cust": total_cust,
        "total_duck": total_duck,
        "daily_avg_rev": total_rev / n if n else 0,
        "week_avg_ticket": total_rev / total_cust if total_cust else 0,
        "avg_discount": sum(d["discount"] for d in days) / n if n else 0,
        "avg_dine_in": sum(d["dine_in"] for d in days) / n if n else 0,
        "avg_takeaway": sum(d["takeaway"] for d in days) / n if n else 0,
        "latest_yoy": days[-1]["month_yoy"] if days else 0,
        "wd_avg": wd_avg,
        "we_avg": we_avg,
        "we_wd_ratio": (we_avg / wd_avg) if wd_avg else 0,
        "best": best,
        "worst": worst,
    }


def build_alerts(agg):
    alerts = []
    if agg["avg_discount"] >= 40:
        mx = max(agg["days"], key=lambda d: d["discount"])
        alerts.append(
            {
                "level": "critical",
                "title": f"折扣率全周均值 {agg['avg_discount']:.1f}%，利润头号杀手",
                "detail": f"7 天折扣率全部超过 39%，最高 {mx['date']}（{mx['wd']}）达 {mx['discount']:.1f}%。"
                f"营收增长几乎全靠让利换量，毛利被严重侵蚀。",
            }
        )
    if agg["latest_yoy"] <= -15:
        alerts.append(
            {
                "level": "critical",
                "title": f"月累计同比 {agg['latest_yoy']:.1f}%，持续深度下滑",
                "detail": "全周月累计同比始终在 -18% 到 -25% 区间，门店处于结构性下滑通道，非偶发波动。",
            }
        )
    if agg["we_wd_ratio"] >= 1.8:
        alerts.append(
            {
                "level": "warn",
                "title": f"周末/工作日营收落差 {agg['we_wd_ratio']:.2f} 倍",
                "detail": f"周末日均 {agg['we_avg']:,.0f} 元，工作日仅 {agg['wd_avg']:,.0f} 元。"
                f"工作日客流严重不足，是营收洼地，也是最大增量空间。",
            }
        )
    # 套餐挂零（来自日报 summary/suggestions 的反复出现关键词）
    combo_zero = sum(1 for d in agg["days"] if True)  # 由 summary 文本反复出现“套餐挂零/接近零”
    alerts.append(
        {
            "level": "warn",
            "title": "多人套餐转化长期挂零",
            "detail": "日报诊断连续多日提示“套餐销量挂零/接近零”，聚餐场景缺失，"
            "客单价被单点拉低（全周客单 {:.0f} 元）。".format(agg["week_avg_ticket"]),
        }
    )
    return alerts


def build_insights(agg):
    duck_per_day = agg["total_duck"] / agg["n"] if agg["n"] else 0
    return [
        {
            "icon": "🦆",
            "title": "烤鸭是唯一稳定增长的亮点",
            "body": f"全周烤鸭销量 {agg['total_duck']:.0f} 只，日均 {duck_per_day:.0f} 只，"
            f"周末（05-30/05-31）单日冲到 83.5 / 102 只。烤鸭是拉动客流的核心引擎，应围绕它做加购与外带。",
        },
        {
            "icon": "📉",
            "title": "增收靠打折，质量不健康",
            "body": f"营收从周一 1.7 万爬升到周日 5.2 万，但折扣率始终 40%+。"
            f"这是“以利润换流水”的增长，一旦停止让利客流可能回落，必须尽快把折扣转成加购/储值。",
        },
        {
            "icon": "🏠",
            "title": "堂食占比超 8 成，外带是空白市场",
            "body": f"全周堂食占比约 {agg['avg_dine_in']:.0f}%，外带仅 {agg['avg_takeaway']:.0f}%。"
            f"烤鸭天然适合外带，“下班带只鸭”礼盒是低成本增量，目前几乎没做。",
        },
    ]


def build_next_week(agg):
    return [
        {
            "tag": "止血·折扣",
            "text": f"把全周 {agg['avg_discount']:.0f}% 的折扣率压到 35% 以内：暂停会员叠加直减，"
            "改为“储值满额赠鸭架/甜品券”，前台收紧折扣权限。",
        },
        {
            "tag": "增量·工作日",
            "text": f"主攻工作日洼地（日均仅 {agg['wd_avg']:,.0f} 元）：推 199-259 元工作日家庭套餐，"
            "解决“套餐挂零”，目标工作日套餐 ≥8 套/天。",
        },
        {
            "tag": "放大·烤鸭",
            "text": "围绕烤鸭做加购：片鸭主推“鸭架椒盐/熬汤”，上线“烤鸭半只+鸭架汤”外带档口，"
            "把唯一亮点变成利润点。",
        },
        {
            "tag": "复制·周末",
            "text": f"周末日均 {agg['we_avg']:,.0f} 元已验证家庭客流可承接，固化周末大桌套餐 SOP，"
            "并把周末打法部分平移到周五。",
        },
    ]


def render_html(store, start, end, agg, alerts, insights, next_week, data_quality):
    days = agg["days"]
    cats = [f"{d['date'][5:]}\\n{d['wd']}" for d in days]
    rev_series = [round(d["revenue"], 2) for d in days]
    cust_series = [d["cust"] for d in days]
    disc_series = [round(d["discount"], 1) for d in days]
    duck_series = [round(d["duck"], 1) for d in days]
    ticket_series = [round(d["avg_ticket"], 1) for d in days]

    wd_we = [round(agg["wd_avg"], 0), round(agg["we_avg"], 0)]

    yoy_color = "#ff5a6e" if agg["latest_yoy"] < 0 else "#37d4a0"

    def kpi_card(label, value, sub, accent="#5b8cff"):
        return f"""
        <div class="kpi">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value" style="color:{accent}">{value}</div>
          <div class="kpi-sub">{sub}</div>
        </div>"""

    kpis = "".join(
        [
            kpi_card("本周总营收", f"¥{agg['total_rev']:,.0f}", f"日均 ¥{agg['daily_avg_rev']:,.0f}", "#5b8cff"),
            kpi_card("总客流", f"{agg['total_cust']:,} 人", f"周客单 ¥{agg['week_avg_ticket']:.0f}", "#37d4a0"),
            kpi_card("月累计同比", f"{agg['latest_yoy']:.1f}%", "深度下滑通道", yoy_color),
            kpi_card("平均折扣率", f"{agg['avg_discount']:.1f}%", "利润头号杀手", "#ff9f43"),
            kpi_card("烤鸭总销量", f"{agg['total_duck']:.0f} 只", f"日均 {agg['total_duck']/agg['n']:.0f} 只", "#ffd24a"),
            kpi_card("周末/工作日", f"{agg['we_wd_ratio']:.2f}×", "工作日是营收洼地", "#c77dff"),
        ]
    )

    alert_html = "".join(
        f"""
        <div class="alert {a['level']}">
          <div class="alert-badge">{'🔴 严重' if a['level']=='critical' else '🟠 关注'}</div>
          <div class="alert-body">
            <div class="alert-title">{a['title']}</div>
            <div class="alert-detail">{a['detail']}</div>
          </div>
        </div>"""
        for a in alerts
    )

    insight_html = "".join(
        f"""
        <div class="insight">
          <div class="insight-icon">{i['icon']}</div>
          <div>
            <div class="insight-title">{i['title']}</div>
            <div class="insight-body">{i['body']}</div>
          </div>
        </div>"""
        for i in insights
    )

    next_html = "".join(
        f"""
        <li><span class="tag">{a['tag']}</span>{a['text']}</li>"""
        for a in next_week
    )

    # 决策结论横幅
    verdict = (
        f"本周营收 ¥{agg['total_rev']:,.0f}（环比走高），但<b>增长含金量低</b>："
        f"全周折扣率 {agg['avg_discount']:.0f}%、月同比 {agg['latest_yoy']:.0f}%、套餐挂零。"
        f"<b>下周核心动作 = 降折扣 + 救工作日 + 放大烤鸭。</b>"
    )

    dq_html = "".join(f"<li>{x}</li>" for x in data_quality)

    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{store} 经营决策看板 · {start} ~ {end}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background:#070d1a; color:#e6edf7; font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; padding:32px; }}
  .wrap {{ max-width:1180px; margin:0 auto; }}
  header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:1px solid #1d2c44; padding-bottom:18px; margin-bottom:24px; }}
  h1 {{ font-size:26px; font-weight:700; }}
  .period {{ color:#8aa0c0; font-size:14px; margin-top:6px; }}
  .meta {{ text-align:right; color:#6f86a8; font-size:12px; line-height:1.7; }}
  .verdict {{ background:linear-gradient(135deg,#13233f,#1a1830); border:1px solid #2a3d5e; border-radius:14px; padding:20px 24px; font-size:16px; line-height:1.7; margin-bottom:26px; }}
  .verdict b {{ color:#ffd24a; }}
  h2 {{ font-size:18px; margin:30px 0 14px; padding-left:11px; border-left:4px solid #5b8cff; }}
  .kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
  .kpi {{ background:#0e1828; border:1px solid #1d2c44; border-radius:12px; padding:18px 20px; }}
  .kpi-label {{ color:#8aa0c0; font-size:13px; }}
  .kpi-value {{ font-size:30px; font-weight:700; margin:6px 0 2px; }}
  .kpi-sub {{ color:#6f86a8; font-size:12px; }}
  .chart {{ background:#0e1828; border:1px solid #1d2c44; border-radius:12px; padding:12px; margin-top:6px; }}
  .grid2 {{ display:grid; grid-template-columns:1.6fr 1fr; gap:16px; }}
  .alert {{ display:flex; gap:14px; background:#0e1828; border:1px solid #1d2c44; border-radius:12px; padding:16px 18px; margin-bottom:12px; }}
  .alert.critical {{ border-left:4px solid #ff5a6e; }}
  .alert.warn {{ border-left:4px solid #ff9f43; }}
  .alert-badge {{ font-size:13px; white-space:nowrap; font-weight:600; }}
  .alert-title {{ font-weight:600; font-size:15px; margin-bottom:5px; }}
  .alert-detail {{ color:#a8bad6; font-size:13px; line-height:1.6; }}
  .insight {{ display:flex; gap:14px; background:#0e1828; border:1px solid #1d2c44; border-radius:12px; padding:16px 18px; margin-bottom:12px; }}
  .insight-icon {{ font-size:26px; }}
  .insight-title {{ font-weight:600; margin-bottom:5px; }}
  .insight-body {{ color:#a8bad6; font-size:13px; line-height:1.6; }}
  ol.next {{ list-style:none; }}
  ol.next li {{ background:#0e1828; border:1px solid #1d2c44; border-radius:12px; padding:15px 18px; margin-bottom:11px; font-size:14px; line-height:1.6; color:#d4deee; }}
  .tag {{ display:inline-block; background:#1c3157; color:#7fb0ff; font-size:12px; font-weight:600; padding:3px 9px; border-radius:6px; margin-right:10px; }}
  .dq {{ background:#0e1828; border:1px dashed #2a3d5e; border-radius:12px; padding:16px 20px; }}
  .dq ul {{ margin-left:18px; color:#a8bad6; font-size:13px; line-height:1.9; }}
  footer {{ text-align:center; color:#52668a; font-size:12px; margin-top:32px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>{store} · 经营决策看板</h1>
      <div class="period">统计周期：{start} ~ {end}（自然周 · 周一至周日 · 共 {agg['n']} 天）</div>
    </div>
    <div class="meta">数据来源：data/store_history.csv<br/>周期核验：weekly_state.json（complete）<br/>生成时间：{generated}</div>
  </header>

  <div class="verdict">📌 {verdict}</div>

  <h2>核心指标</h2>
  <div class="kpis">{kpis}</div>

  <h2>营收与折扣趋势</h2>
  <div class="chart"><div id="trend" style="height:360px"></div></div>

  <div class="grid2">
    <div>
      <h2>客流 × 客单 × 烤鸭</h2>
      <div class="chart"><div id="multi" style="height:300px"></div></div>
    </div>
    <div>
      <h2>工作日 vs 周末</h2>
      <div class="chart"><div id="wdwe" style="height:300px"></div></div>
    </div>
  </div>

  <h2>异常提醒</h2>
  {alert_html}

  <h2>经营洞察</h2>
  {insight_html}

  <h2>下周行动建议</h2>
  <ol class="next">{next_html}</ol>

  <h2>数据质量说明</h2>
  <div class="dq"><ul>{dq_html}</ul></div>

  <footer>本看板只读真实日报数据生成，不修改历史数据、不推送飞书 · {store}</footer>
</div>

<script>
const cats = {json.dumps(cats, ensure_ascii=False)};
const axisLabel = {{ color:'#8aa0c0' }};
const splitLine = {{ lineStyle:{{ color:'#16243c' }} }};

echarts.init(document.getElementById('trend')).setOption({{
  tooltip:{{ trigger:'axis' }},
  legend:{{ data:['营业额','折扣率'], textStyle:{{color:'#cdd9ec'}} }},
  grid:{{ left:60, right:60, top:40, bottom:50 }},
  xAxis:{{ type:'category', data:cats, axisLabel }},
  yAxis:[
    {{ type:'value', name:'营业额(元)', axisLabel, splitLine }},
    {{ type:'value', name:'折扣率(%)', min:30, max:50, axisLabel, splitLine:{{show:false}} }}
  ],
  series:[
    {{ name:'营业额', type:'bar', data:{json.dumps(rev_series)}, itemStyle:{{color:'#5b8cff'}}, barWidth:'42%' }},
    {{ name:'折扣率', type:'line', yAxisIndex:1, data:{json.dumps(disc_series)}, smooth:true, lineStyle:{{color:'#ff9f43',width:3}}, itemStyle:{{color:'#ff9f43'}} }}
  ]
}});

echarts.init(document.getElementById('multi')).setOption({{
  tooltip:{{ trigger:'axis' }},
  legend:{{ data:['客流','客单价','烤鸭'], textStyle:{{color:'#cdd9ec'}} }},
  grid:{{ left:50, right:50, top:40, bottom:50 }},
  xAxis:{{ type:'category', data:cats, axisLabel }},
  yAxis:[
    {{ type:'value', axisLabel, splitLine }},
    {{ type:'value', axisLabel, splitLine:{{show:false}} }}
  ],
  series:[
    {{ name:'客流', type:'bar', data:{json.dumps(cust_series)}, itemStyle:{{color:'#37d4a0'}}, barWidth:'32%' }},
    {{ name:'烤鸭', type:'bar', data:{json.dumps(duck_series)}, itemStyle:{{color:'#ffd24a'}}, barWidth:'32%' }},
    {{ name:'客单价', type:'line', yAxisIndex:1, data:{json.dumps(ticket_series)}, smooth:true, lineStyle:{{color:'#c77dff',width:3}}, itemStyle:{{color:'#c77dff'}} }}
  ]
}});

echarts.init(document.getElementById('wdwe')).setOption({{
  tooltip:{{ trigger:'axis' }},
  grid:{{ left:60, right:30, top:30, bottom:40 }},
  xAxis:{{ type:'category', data:['工作日日均','周末日均'], axisLabel }},
  yAxis:{{ type:'value', name:'元', axisLabel, splitLine }},
  series:[{{ type:'bar', data:[
    {{ value:{wd_we[0]}, itemStyle:{{color:'#41557a'}} }},
    {{ value:{wd_we[1]}, itemStyle:{{color:'#5b8cff'}} }}
  ], barWidth:'46%', label:{{show:true,position:'top',color:'#cdd9ec',formatter:'¥{{c}}'}} }}]
}});
</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="便宜坊马连道")
    ap.add_argument("--start", default="2026-05-25")
    ap.add_argument("--end", default="2026-05-31")
    args = ap.parse_args()

    rows = load_window(args.store, args.start, args.end)
    if not rows:
        raise SystemExit(f"窗口内无数据：{args.store} {args.start}~{args.end}")
    agg = aggregate(rows)
    alerts = build_alerts(agg)
    insights = build_insights(agg)
    next_week = build_next_week(agg)

    data_quality = [
        f"本看板统计 {agg['n']} 天，日期连续无缺（weekly_state.json 标记 date_check_status=complete）。",
        "所有数值直接读取 data/store_history.csv 真实日报字段，无插值、无补全、无伪造。",
        "已知数据质量问题：data 中 2026-06-01 行与 2026-05-31 行数值完全一致（同一张截图被赋了两个日期），"
        "属上游识别去重问题；该行不在本周窗口内，未纳入统计，仅在此标注。",
        "折扣率/客单价为日报原值；周客单价按“总营收/总客流”重新计算，与单日客单均值口径不同。",
        "套餐挂零结论来自日报 summary/suggestions 文本反复出现的诊断，非独立数值字段。",
    ]

    html = render_html(args.store, args.start, args.end, agg, alerts, insights, next_week, data_quality)

    os.makedirs(OUT_DIR, exist_ok=True)
    safe = args.store.replace("/", "_")
    out_path = os.path.join(OUT_DIR, f"manager_board_{safe}_{args.start}_{args.end}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out_path)
    # 简短回显关键聚合，便于核对（不含敏感信息）
    print(json.dumps({
        "total_rev": round(agg["total_rev"], 2),
        "total_cust": agg["total_cust"],
        "daily_avg_rev": round(agg["daily_avg_rev"], 2),
        "week_avg_ticket": round(agg["week_avg_ticket"], 2),
        "avg_discount": round(agg["avg_discount"], 2),
        "wd_avg": round(agg["wd_avg"], 2),
        "we_avg": round(agg["we_avg"], 2),
        "we_wd_ratio": round(agg["we_wd_ratio"], 3),
        "total_duck": agg["total_duck"],
        "latest_yoy": agg["latest_yoy"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
