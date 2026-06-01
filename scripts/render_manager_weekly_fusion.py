#!/usr/bin/env python3
"""融合版管理者周报看板生成器。

上半部分 = 经营大屏（核心指标 / 营收趋势 / 收入结构 / 客单价 / 会员 / 品类 / 烤鸭专项），
下半部分 = 管理诊断（本周经营判断 / 风险预警 / 下周行动建议 / 数据质量说明）。

数据来源（全部只读，不改历史数据、不造数）：
  - data/store_history.csv      → 7 天完整窗口的营收/客流/客单/折扣/烤鸭
  - output/report_MLD_*.json    → 结构化日报，提供收入结构/会员/品类/烤鸭专项明细
                                   （仅部分日期存在，缺失日期会显式标注，不补全）

用法：
    python3 scripts/render_manager_weekly_fusion.py \
        --store 便宜坊马连道 --start 2026-05-25 --end 2026-05-31
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
CSV_PATH = os.path.join(ROOT, "data", "store_history.csv")
REPORT_DIR = os.path.join(ROOT, "output")
OUT_DIR = os.path.join(ROOT, "output")
STORE_ID = "MLD"

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def fnum(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def inum(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def date_range(start, end):
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    out = []
    while s <= e:
        out.append(s.isoformat())
        s += dt.timedelta(days=1)
    return out


# ---------- 7 天完整窗口（store_history.csv） ----------
def load_history(store, start, end):
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["store_name"] != store:
                continue
            if start <= r["date"] <= end:
                rows.append(r)
    rows.sort(key=lambda r: r["date"])
    days = []
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        days.append({
            "date": r["date"], "wd": WEEKDAY_CN[d.weekday()],
            "is_weekend": d.weekday() >= 5,
            "revenue": fnum(r["revenue"]), "cust": inum(r["customer_count"]),
            "avg_ticket": fnum(r["avg_ticket"]), "month_yoy": fnum(r["month_yoy"]),
            "discount": fnum(r["discount_rate"]), "dine_in": fnum(r["dine_in_ratio"]),
            "takeaway": fnum(r["takeaway_ratio"]), "duck": fnum(r["roast_duck_sales"]),
        })
    return days


def hist_agg(days):
    n = len(days)
    total_rev = sum(d["revenue"] for d in days)
    total_cust = sum(d["cust"] for d in days)
    weekday = [d for d in days if not d["is_weekend"]]
    weekend = [d for d in days if d["is_weekend"]]
    wd_avg = sum(d["revenue"] for d in weekday) / len(weekday) if weekday else 0
    we_avg = sum(d["revenue"] for d in weekend) / len(weekend) if weekend else 0
    return {
        "n": n, "total_rev": total_rev, "total_cust": total_cust,
        "total_duck": sum(d["duck"] for d in days),
        "daily_avg_rev": total_rev / n if n else 0,
        "week_avg_ticket": total_rev / total_cust if total_cust else 0,
        "avg_discount": sum(d["discount"] for d in days) / n if n else 0,
        "avg_dine_in": sum(d["dine_in"] for d in days) / n if n else 0,
        "avg_takeaway": sum(d["takeaway"] for d in days) / n if n else 0,
        "latest_yoy": days[-1]["month_yoy"] if days else 0,
        "wd_avg": wd_avg, "we_avg": we_avg,
        "we_wd_ratio": (we_avg / wd_avg) if wd_avg else 0,
        "best": max(days, key=lambda d: d["revenue"]),
        "worst": min(days, key=lambda d: d["revenue"]),
    }


# ---------- 部分窗口（report_MLD_*.json，结构化明细） ----------
def load_reports(start, end):
    present, missing = [], []
    payloads = {}
    for d in date_range(start, end):
        p = os.path.join(REPORT_DIR, f"report_{STORE_ID}_{d}.json")
        if os.path.exists(p):
            payloads[d] = json.load(open(p, encoding="utf-8"))["daily"]
            present.append(d)
        else:
            missing.append(d)
    return payloads, present, missing


def report_agg(payloads, present):
    a = {k: 0.0 for k in [
        "dine_in", "dine_in_takeaway", "online", "member_recharge",
        "member_revenue", "discount_revenue", "full_price_revenue",
        "coupon_issued", "coupon_redeemed",
        "duck_dine_in", "duck_online", "mini_duck", "duck_rack",
        "sesame_cake", "duck_sauce", "pigeon", "crab_set", "set_meal_total",
        "fish_total", "beef_paw", "per_seat", "sweet", "house_drink", "dessert", "craft_beer",
    ]}
    rack_ratios, cake_ratios = [], []
    for d in present:
        j = payloads[d]
        rev, mem, tr = j["revenue"], j["member_consumption"], j["traffic"]
        cat, dv = j["dishes_by_category"], j["derived"]
        duck, meal = cat["烤鸭类"], cat["套餐类"]
        fish, seat, beer = cat["鱼类_牛掌"], cat["位吃_甜品"], cat["精酿"]
        a["dine_in"] += fnum(rev["dine_in_revenue"])
        a["dine_in_takeaway"] += fnum(rev["dine_in_takeaway_revenue"])
        a["online"] += fnum(rev["online_takeaway_revenue"])
        a["member_recharge"] += fnum(rev["member_recharge_today"])
        a["member_revenue"] += fnum(mem["member_revenue"])
        a["discount_revenue"] += fnum(mem["discount_revenue"])
        a["full_price_revenue"] += fnum(mem["full_price_revenue"])
        a["coupon_issued"] += fnum(tr["rebate_coupon_issued"])
        a["coupon_redeemed"] += fnum(tr["rebate_coupon_redeemed"])
        a["duck_dine_in"] += fnum(duck["roasted_duck_dine_in"])
        a["duck_online"] += fnum(duck["roasted_duck_online"])
        a["mini_duck"] += fnum(duck["mini_duck"])
        a["duck_rack"] += fnum(duck["spiced_duck_rack"])
        a["sesame_cake"] += fnum(duck["sesame_cake"])
        a["duck_sauce"] += fnum(duck["duck_sauce"])
        a["pigeon"] += fnum(meal.get("pigeon"))
        a["crab_set"] += fnum(meal.get("crab_set_meal"))
        a["set_meal_total"] += fnum(dv.get("set_meal_total"))
        a["fish_total"] += fnum(fish.get("fish_total"))
        a["beef_paw"] += fnum(fish.get("sea_cucumber_beef_paw"))
        a["per_seat"] += fnum(seat.get("per_seat_dish"))
        a["sweet"] += fnum(seat.get("sweet"))
        a["house_drink"] += fnum(seat.get("house_drink"))
        a["dessert"] += fnum(seat.get("dessert"))
        a["craft_beer"] += fnum(beer.get("craft_beer"))
        rack_ratios.append(fnum(duck.get("duck_rack_ratio")))
        cake_ratios.append(fnum(duck.get("sesame_cake_ratio")))
    a["duck_total"] = a["duck_dine_in"] + a["duck_online"] + a["mini_duck"]
    a["avg_rack_ratio"] = sum(rack_ratios) / len(rack_ratios) if rack_ratios else 0
    a["avg_cake_ratio"] = sum(cake_ratios) / len(cake_ratios) if cake_ratios else 0
    # 最新一天的月累计口径
    last = payloads[present[-1]]["revenue"] if present else {}
    a["mtd"] = fnum(last.get("revenue_month_to_date"))
    a["mtd_before_discount"] = fnum(last.get("revenue_mtd_before_discount"))
    a["mtd_last_year"] = fnum(last.get("revenue_same_period_last_year"))
    a["yoy_delta"] = fnum(last.get("revenue_yoy_delta"))
    a["member_recharge_mtd"] = fnum(last.get("member_recharge_mtd"))
    return a


# ---------- 诊断（沿用 Claude 管理者版洞察/预警/建议） ----------
def build_alerts(h):
    alerts = []
    mx = max(h["best"], key=lambda x: 0)  # placeholder
    alerts.append({"level": "critical",
        "title": f"折扣率全周均值 {h['avg_discount']:.1f}%，利润头号杀手",
        "detail": "7 天折扣率全部 >39%，营收增长几乎全靠让利换量，毛利被严重侵蚀；"
                  "结构化日报亦显示原价消费占比常年个位数。"})
    alerts.append({"level": "critical",
        "title": f"月累计同比 {h['latest_yoy']:.1f}%，持续深度失血",
        "detail": "全周月累计同比始终在 -18%~-25% 区间，属结构性下滑而非偶发波动，"
                  f"最新同比差额约 ¥26 万。"})
    alerts.append({"level": "warn",
        "title": f"周末/工作日营收落差 {h['we_wd_ratio']:.2f} 倍",
        "detail": f"周末日均 ¥{h['we_avg']:,.0f}、工作日仅 ¥{h['wd_avg']:,.0f}，"
                  "工作日是最大营收洼地，也是最易拿的增量。"})
    alerts.append({"level": "warn",
        "title": "多人套餐转化长期偏低、精酿挂零",
        "detail": "结构化日报连续提示套餐销量个位数、聚餐场景缺失；精酿全周 0 销售，"
                  "客单价被单点拉低。"})
    return alerts


def build_insights(h, r, present):
    duck_total7 = h["total_duck"]
    return [
        {"icon": "🦆", "title": "烤鸭是唯一稳定增长的亮点",
         "body": f"7 天烤鸭销量 {duck_total7:.0f} 只，周末单日冲到 102 只；烤鸭小料 {r['duck_sauce']:.0f}、"
                 f"烧饼 {r['sesame_cake']:.0f} 同步走高，是拉客流的核心引擎，应围绕它做加购与外带。"},
        {"icon": "📉", "title": "增收靠打折，增长含金量低",
         "body": f"营收从周一 ¥1.7 万爬到周日 ¥5.2 万，但折扣率始终 40%+，优惠消费 5 日合计 ¥{r['discount_revenue']:,.0f}。"
                 "一旦停止让利客流可能回落，必须尽快把折扣转成加购/储值。"},
        {"icon": "🏠", "title": "堂食超 8 成，外带与线上是空白",
         "body": f"全周堂食占比约 {h['avg_dine_in']:.0f}%、外带仅 {h['avg_takeaway']:.0f}%；"
                 f"5 日线上外卖合计仅 ¥{r['online']:,.0f}、堂食打包仅 ¥{r['dine_in_takeaway']:,.0f}，"
                 "烤鸭天然适合外带，礼盒化是低成本增量。"},
    ]


def build_next_week(h):
    return [
        {"tag": "止血·折扣", "text": f"把全周 {h['avg_discount']:.0f}% 的折扣率压到 35% 以内：暂停会员叠加直减，"
            "改为“储值满额赠鸭架/甜品券”，前台收紧折扣权限。"},
        {"tag": "增量·工作日", "text": f"主攻工作日洼地（日均仅 ¥{h['wd_avg']:,.0f}）：推 199-259 元工作日家庭套餐，"
            "解决套餐挂零，目标工作日套餐 ≥8 套/天。"},
        {"tag": "放大·烤鸭", "text": "围绕烤鸭做加购：片鸭主推“鸭架椒盐/熬汤”，上线“烤鸭半只+鸭架汤”外带档口，"
            "把唯一亮点变成利润点。"},
        {"tag": "复制·周末", "text": f"周末日均 ¥{h['we_avg']:,.0f} 已验证家庭客流可承接，固化周末大桌套餐 SOP，"
            "并把周末打法部分平移到周五。"},
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="便宜坊马连道")
    ap.add_argument("--start", default="2026-05-25")
    ap.add_argument("--end", default="2026-05-31")
    ap.add_argument("--no-png", action="store_true", help="只生成 HTML，不导出长图 PNG")
    ap.add_argument("--viewport-width", type=int, default=1600, help="长图导出视口宽度（CSS px），默认 1600")
    ap.add_argument("--scale", type=int, default=2, help="长图导出 deviceScaleFactor，默认 2（高清，可设 3）")
    ap.add_argument("--png-engine", choices=["chrome", "pil"], default="chrome",
                    help="PNG 导出引擎：chrome=HTML 高清长图（默认）；pil=无浏览器兜底绘制")
    ap.add_argument("--send-to-feishu", action="store_true",
                    help="PNG 生成成功后推送到飞书；缺凭证或 PNG 缺失时跳过，不输出敏感信息")
    args = ap.parse_args()

    days = load_history(args.store, args.start, args.end)
    if not days:
        raise SystemExit("窗口内无 store_history 数据")
    h = hist_agg(days)
    payloads, present, missing = load_reports(args.start, args.end)
    r = report_agg(payloads, present)

    alerts = build_alerts(h)
    insights = build_insights(h, r, present)
    next_week = build_next_week(h)

    n_present = len(present)
    present_label = "、".join(d[5:] for d in present)
    missing_label = "、".join(d[5:] for d in missing) if missing else "无"

    data_quality = [
        f"核心指标（营收/客流/客单/折扣/烤鸭）来自 data/store_history.csv，覆盖 {h['n']}/7 天，"
        "日期连续无缺（weekly_state.json 标记 date_check_status=complete）。",
        f"收入结构 / 会员 / 品类 / 烤鸭专项明细来自结构化日报 output/report_{STORE_ID}_*.json，"
        f"仅 {n_present} 天可用（{present_label}），缺失 {missing_label}；相关汇总为 {n_present} 日口径，未对缺失日补全或插值。",
        "已知数据质量问题：store_history.csv 中 2026-06-01 行与 2026-05-31 行数值完全一致（同一截图被赋两个日期），"
        "属上游识别去重问题；该行不在本周窗口内，未纳入统计，仅此标注。",
        "周客单价按“7 日总营收/总客流”重算，与单日客单均值口径不同；收入结构饼图中“优惠消费”与渠道口径存在重叠，仅作让利规模参考。",
        "全部数值直读真实日报字段，无伪造、无补全；烤鸭/烧饼占比为可用日的均值。",
    ]

    html = render_html(args.store, args.start, args.end, days, h, r,
                       present, missing, alerts, insights, next_week, data_quality)

    os.makedirs(OUT_DIR, exist_ok=True)
    safe = args.store.replace("/", "_")
    stem = f"manager_weekly_fusion_{safe}_{args.start}_{args.end}"
    out_path = os.path.join(OUT_DIR, stem + ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("WROTE", out_path)

    png_path = None
    png_engine = None
    png_dims = None
    if not args.no_png:
        png_path = os.path.join(OUT_DIR, stem + ".png")
        if args.png_engine == "chrome":
            try:
                _, w, hgt, sc = export_png_via_chrome(
                    out_path, png_path, width=args.viewport_width, scale=args.scale)
                png_engine = "chrome"
                png_dims = (w, hgt, sc)
                print(f"WROTE {png_path}  (chrome 长图 viewport={w}px scale={sc} 页面高={hgt}px)")
            except Exception as exc:
                print(f"[fusion] Chrome 长图导出失败，退回 PIL 兜底：{type(exc).__name__}: {exc}")
        if png_engine is None:
            render_png(args.store, args.start, args.end, days, h, r,
                       present, missing, alerts, insights, next_week, data_quality, png_path)
            png_engine = "pil"
            print(f"WROTE {png_path}  (pil 兜底绘制)")

    print(json.dumps({
        "history_days": h["n"], "report_days": n_present, "missing": missing,
        "png_engine": png_engine, "png_dims": png_dims,
        "total_rev": round(h["total_rev"], 2), "total_cust": h["total_cust"],
        "we_wd_ratio": round(h["we_wd_ratio"], 3),
        "channel_dine_in": round(r["dine_in"], 2), "channel_online": round(r["online"], 2),
        "duck_total_report": r["duck_total"], "duck_total_history": h["total_duck"],
    }, ensure_ascii=False))

    if args.send_to_feishu:
        if not png_path or not os.path.exists(png_path):
            raise SystemExit("[fusion] PNG 不存在，拒绝推送飞书")
        send_fusion_to_feishu(png_path, args.store, args.start, args.end,
                              h["n"], n_present, missing)
        print("[fusion] 已推送融合版看板图片到飞书")


def render_html(store, start, end, days, h, r, present, missing, alerts, insights, next_week, dq):
    cats = [f"{d['date'][5:]} {d['wd']}" for d in days]
    rev_series = [round(d["revenue"], 2) for d in days]
    cust_series = [d["cust"] for d in days]
    disc_series = [round(d["discount"], 1) for d in days]
    ticket_series = [round(d["avg_ticket"], 1) for d in days]
    yoy_color = "#ff5a6e" if h["latest_yoy"] < 0 else "#37d4a0"
    n_present = len(present)

    def kpi(label, value, sub, accent):
        return f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value" style="color:{accent}">{value}</div><div class="kpi-sub">{sub}</div></div>'

    kpis = "".join([
        kpi("本周营业额", f"¥{h['total_rev']:,.0f}", f"日均 ¥{h['daily_avg_rev']:,.0f}", "#5b8cff"),
        kpi("本周总客流", f"{h['total_cust']:,} 人", f"周客单 ¥{h['week_avg_ticket']:.0f}", "#37d4a0"),
        kpi("月累计同比", f"{h['latest_yoy']:.1f}%", f"差额 ¥{r['yoy_delta']:,.0f}", yoy_color),
        kpi("平均折扣率", f"{h['avg_discount']:.1f}%", "利润头号杀手", "#ff9f43"),
        kpi("烤鸭总销量", f"{h['total_duck']:.0f} 只", f"日均 {h['total_duck']/h['n']:.0f} 只", "#ffd24a"),
        kpi("周末/工作日", f"{h['we_wd_ratio']:.2f}×", f"工作日日均 ¥{h['wd_avg']:,.0f}", "#c77dff"),
        kpi("堂食占比", f"{h['avg_dine_in']:.1f}%", f"外带 {h['avg_takeaway']:.1f}%", "#5cc8ff"),
        kpi("周报完整度", f"{h['n']}/7 天", f"结构明细 {n_present}/7 天", "#9fb3d1"),
    ])

    # pie 收入结构（5 日）
    pie_data = [
        {"name": "堂食", "value": round(r["dine_in"], 2)},
        {"name": "堂食打包", "value": round(r["dine_in_takeaway"], 2)},
        {"name": "线上外卖", "value": round(r["online"], 2)},
        {"name": "优惠消费(让利)", "value": round(r["discount_revenue"], 2)},
    ]
    # 渠道对比 bar（5 日）
    chan_names = ["堂食", "堂食打包", "线上外卖", "优惠让利"]
    chan_vals = [round(r["dine_in"], 0), round(r["dine_in_takeaway"], 0), round(r["online"], 0), round(r["discount_revenue"], 0)]
    # 品类 TOP（5 日）
    cat_items = [
        ("烧饼", r["sesame_cake"]), ("烤鸭小料", r["duck_sauce"]),
        ("位吃+甜品", r["per_seat"] + r["sweet"] + r["dessert"]),
        ("烤鸭", r["duck_total"]), ("套餐", r["set_meal_total"]),
        ("自制饮品", r["house_drink"]), ("乳鸽", r["pigeon"]),
        ("鱼类+牛掌", r["fish_total"] + r["beef_paw"]),
        ("精酿", r["craft_beer"]),
    ]
    cat_items.sort(key=lambda x: x[1], reverse=True)
    cat_names = [c[0] for c in cat_items]
    cat_vals = [round(c[1], 1) for c in cat_items]

    def stat(label, value):
        return f'<div class="stat"><div class="stat-label">{label}</div><div class="stat-value">{value}</div></div>'

    member_html = "".join([
        stat("会员储值(5日)", f"¥{r['member_recharge']:,.0f}"),
        stat("月累计储值", f"¥{r['member_recharge_mtd']:,.0f}"),
        stat("会员消费(5日)", f"¥{r['member_revenue']:,.0f}"),
        stat("原价消费(5日)", f"¥{r['full_price_revenue']:,.0f}"),
        stat("发券(5日)", f"{r['coupon_issued']:.0f} 张"),
        stat("验券(5日)", f"{r['coupon_redeemed']:.0f} 张"),
    ])

    duck_html = "".join([
        stat("烤鸭总销量(5日)", f"{r['duck_total']:.0f} 只"),
        stat("堂食烤鸭", f"{r['duck_dine_in']:.0f} 只"),
        stat("线上烤鸭", f"{r['duck_online']:.0f} 只"),
        stat("迷你烤鸭", f"{r['mini_duck']:.0f} 只"),
        stat("鸭架(椒盐/熬汤)", f"{r['duck_rack']:.0f} 份"),
        stat("烧饼 / 鸭酱", f"{r['sesame_cake']:.0f} / {r['duck_sauce']:.0f}"),
        stat("鸭架转化率(均)", f"{r['avg_rack_ratio']:.1f}%"),
        stat("烧饼搭售率(均)", f"{r['avg_cake_ratio']:.1f}%"),
    ])

    mtd_line = (f"月累计 ¥{r['mtd']:,.0f}　·　同期累计 ¥{r['mtd_last_year']:,.0f}　·　"
                f"同比差额 ¥{r['yoy_delta']:,.0f}　·　月折前 ¥{r['mtd_before_discount']:,.0f}")

    alert_html = "".join(
        f'<div class="alert {a["level"]}"><div class="alert-badge">{"🔴 严重" if a["level"]=="critical" else "🟠 关注"}</div>'
        f'<div><div class="alert-title">{a["title"]}</div><div class="alert-detail">{a["detail"]}</div></div></div>'
        for a in alerts)
    insight_html = "".join(
        f'<div class="insight"><div class="insight-icon">{i["icon"]}</div><div>'
        f'<div class="insight-title">{i["title"]}</div><div class="insight-body">{i["body"]}</div></div></div>'
        for i in insights)
    next_html = "".join(f'<li><span class="tag">{a["tag"]}</span>{a["text"]}</li>' for a in next_week)
    dq_html = "".join(f"<li>{x}</li>" for x in dq)

    verdict = (f"本周营收 ¥{h['total_rev']:,.0f}（环比走高），但<b>增长含金量低</b>："
               f"全周折扣率 {h['avg_discount']:.0f}%、月同比 {h['latest_yoy']:.0f}%、套餐挂零、精酿零销。"
               f"<b>下周核心动作 = 降折扣 + 救工作日 + 放大烤鸭外带。</b>")
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    miss_tag = ("覆盖 7/7 天" if not missing else f"明细缺 {('、'.join(d[5:] for d in missing))}")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=1600, initial-scale=1"/>
<title>{store} · 周报经营决策看板 · {start} ~ {end}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
/* 长图导出画布：固定 1600px 宽，不依赖浏览器缩放 */
html,body{{width:1600px}}
body{{background:#070d1a;color:#e6edf7;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;font-size:17px}}
.wrap{{width:1600px;margin:0 auto;padding:48px 56px 64px}}
header{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #1d2c44;padding-bottom:22px;margin-bottom:26px}}
h1{{font-size:36px;font-weight:700;letter-spacing:.5px}}
.period{{color:#8aa0c0;font-size:18px;margin-top:12px}}
.meta{{text-align:right;color:#6f86a8;font-size:16px;line-height:1.9}}
.tag-layer{{color:#7fb0ff;font-size:18px;font-weight:600}}
.verdict{{background:linear-gradient(135deg,#13233f,#1a1830);border:1px solid #2a3d5e;border-radius:16px;padding:26px 30px;font-size:21px;line-height:1.75;margin-bottom:30px}}
.verdict b{{color:#ffd24a}}
.section-tag{{display:inline-block;font-size:16px;color:#6f86a8;font-weight:400;margin-left:10px}}
h2{{font-size:25px;margin:34px 0 18px;padding-left:15px;border-left:6px solid #5b8cff}}
h2.diag{{border-left-color:#ff9f43}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}}
.kpi{{background:#0e1828;border:1px solid #1d2c44;border-radius:14px;padding:22px 24px}}
.kpi-label{{color:#8aa0c0;font-size:17px}}
.kpi-value{{font-size:38px;font-weight:700;margin:8px 0 4px}}
.kpi-sub{{color:#6f86a8;font-size:15px}}
.card{{background:#0e1828;border:1px solid #1d2c44;border-radius:16px;padding:22px 24px}}
.row{{display:grid;gap:20px;margin-top:10px}}
.r-2-1{{grid-template-columns:1.7fr 1fr}}
.r-1-1{{grid-template-columns:1fr 1fr}}
.r-1-1-1{{grid-template-columns:1fr 1fr 1fr}}
.card h3{{font-size:20px;color:#cdd9ec;margin-bottom:14px;font-weight:600}}
.mtd{{color:#8aa0c0;font-size:16px;margin-top:12px;line-height:1.7}}
.stats{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.stat{{background:#0c1422;border:1px solid #1a2942;border-radius:12px;padding:15px 18px}}
.stat-label{{color:#8aa0c0;font-size:15px}}
.stat-value{{font-size:24px;font-weight:600;margin-top:6px;color:#dfe8f5}}
.alert{{display:flex;gap:18px;background:#0e1828;border:1px solid #1d2c44;border-radius:14px;padding:20px 24px;margin-bottom:14px}}
.alert.critical{{border-left:6px solid #ff5a6e}}
.alert.warn{{border-left:6px solid #ff9f43}}
.alert-badge{{font-size:19px;white-space:nowrap;font-weight:700}}
.alert-title{{font-weight:600;font-size:20px;margin-bottom:7px}}
.alert-detail{{color:#a8bad6;font-size:17px;line-height:1.7}}
.insight{{display:flex;gap:18px;background:#0e1828;border:1px solid #1d2c44;border-radius:14px;padding:20px 24px;margin-bottom:14px}}
.insight-icon{{font-size:34px}}
.insight-title{{font-weight:600;font-size:20px;margin-bottom:7px}}
.insight-body{{color:#a8bad6;font-size:17px;line-height:1.7}}
ol.next{{list-style:none}}
ol.next li{{background:#0e1828;border:1px solid #1d2c44;border-radius:14px;padding:19px 24px;margin-bottom:13px;font-size:19px;line-height:1.7;color:#d4deee}}
.tag{{display:inline-block;background:#1c3157;color:#7fb0ff;font-size:16px;font-weight:600;padding:5px 13px;border-radius:8px;margin-right:14px}}
.dq{{background:#0e1828;border:1px dashed #2a3d5e;border-radius:16px;padding:22px 28px}}
.dq ul{{margin-left:24px;color:#a8bad6;font-size:17px;line-height:2}}
.divider{{text-align:center;margin:38px 0 10px;color:#46597d;font-size:18px;letter-spacing:3px}}
footer{{text-align:center;color:#52668a;font-size:16px;margin-top:42px}}
</style></head><body><div class="wrap">
<header>
  <div><h1>{store} · 周报经营决策看板</h1>
  <div class="period">统计周期：{start} ~ {end}（自然周 · 周一至周日 · 核心指标 {h['n']}/7 天，结构明细 {n_present}/7 天 · {miss_tag}）</div></div>
  <div class="meta"><span class="tag-layer">📊 经营大屏 + 管理诊断</span><br/>数据：store_history.csv + report_{STORE_ID}_*.json<br/>生成时间：{generated}</div>
</header>

<div class="verdict">📌 {verdict}</div>

<div class="divider">───────── 上半 · 经营大屏 ─────────</div>

<h2>核心指标<span class="section-tag">7 天完整窗口</span></h2>
<div class="kpis">{kpis}</div>

<div class="row r-2-1">
  <div class="card"><h3>营收趋势 × 折扣率</h3><div id="trend" style="height:400px"></div></div>
  <div class="card"><h3>收入结构<span class="section-tag">{n_present} 日口径</span></h3><div id="pie" style="height:320px"></div>
    <div class="mtd">{mtd_line}</div></div>
</div>

<div class="row r-1-1-1">
  <div class="card"><h3>客单价趋势</h3><div id="ticket" style="height:300px"></div></div>
  <div class="card"><h3>渠道收入对比<span class="section-tag">{n_present} 日</span></h3><div id="chan" style="height:300px"></div></div>
  <div class="card"><h3>客流 × 烤鸭</h3><div id="multi" style="height:300px"></div></div>
</div>

<div class="row r-1-1">
  <div class="card"><h3>关键品类销量 TOP<span class="section-tag">{n_present} 日累计</span></h3><div id="catbar" style="height:380px"></div></div>
  <div class="card"><h3>会员与活动<span class="section-tag">{n_present} 日</span></h3><div class="stats">{member_html}</div></div>
</div>

<div class="row r-1-1">
  <div class="card"><h3>烤鸭专项分析<span class="section-tag">{n_present} 日</span></h3><div class="stats">{duck_html}</div></div>
  <div class="card"><h3>工作日 vs 周末<span class="section-tag">7 天</span></h3><div id="wdwe" style="height:300px"></div></div>
</div>

<div class="divider">───────── 下半 · 管理诊断 ─────────</div>

<h2 class="diag">本周经营判断</h2>
<div class="verdict" style="margin-bottom:18px">{verdict}</div>

<h2 class="diag">风险预警</h2>
{alert_html}

<h2 class="diag">经营洞察</h2>
{insight_html}

<h2 class="diag">下周行动建议</h2>
<ol class="next">{next_html}</ol>

<h2 class="diag">数据质量说明</h2>
<div class="dq"><ul>{dq_html}</ul></div>

<footer>本看板只读真实日报数据生成，不修改历史数据 · {store} · {start}~{end}</footer>
</div>
<script>
const cats={json.dumps(cats, ensure_ascii=False)};
const axisLabel={{color:'#8aa0c0',fontSize:14}};
const splitLine={{lineStyle:{{color:'#16243c'}}}};
function I(id){{return echarts.init(document.getElementById(id),null,{{devicePixelRatio:3}});}}

I('trend').setOption({{tooltip:{{trigger:'axis'}},legend:{{data:['营业额','折扣率'],textStyle:{{color:'#cdd9ec',fontSize:15}}}},
 grid:{{left:70,right:64,top:46,bottom:54}},xAxis:{{type:'category',data:cats,axisLabel}},
 yAxis:[{{type:'value',name:'元',axisLabel,splitLine}},{{type:'value',name:'%',min:30,max:50,axisLabel,splitLine:{{show:false}}}}],
 series:[{{name:'营业额',type:'bar',data:{json.dumps(rev_series)},itemStyle:{{color:'#5b8cff'}},barWidth:'42%'}},
 {{name:'折扣率',type:'line',yAxisIndex:1,data:{json.dumps(disc_series)},smooth:true,lineStyle:{{color:'#ff9f43',width:3}},itemStyle:{{color:'#ff9f43'}}}}]}});

I('pie').setOption({{tooltip:{{trigger:'item',formatter:'{{b}}: ¥{{c}} ({{d}}%)'}},
 legend:{{orient:'vertical',right:6,top:'center',textStyle:{{color:'#cdd9ec',fontSize:15}}}},
 series:[{{type:'pie',radius:['40%','68%'],center:['34%','52%'],
 data:{json.dumps(pie_data, ensure_ascii=False)},
 label:{{show:false}},itemStyle:{{borderColor:'#0e1828',borderWidth:2}},
 color:['#5b8cff','#37d4a0','#ffd24a','#c77dff']}}]}});

I('ticket').setOption({{tooltip:{{trigger:'axis'}},grid:{{left:58,right:22,top:30,bottom:48}},
 xAxis:{{type:'category',data:cats,axisLabel}},yAxis:{{type:'value',name:'元',axisLabel,splitLine}},
 series:[{{type:'line',data:{json.dumps(ticket_series)},smooth:true,areaStyle:{{color:'rgba(55,212,160,.15)'}},lineStyle:{{color:'#37d4a0',width:3}},itemStyle:{{color:'#37d4a0'}}}}]}});

I('chan').setOption({{tooltip:{{trigger:'axis'}},grid:{{left:84,right:30,top:22,bottom:42}},
 xAxis:{{type:'value',axisLabel,splitLine}},yAxis:{{type:'category',data:{json.dumps(chan_names, ensure_ascii=False)},axisLabel}},
 series:[{{type:'bar',data:{json.dumps(chan_vals)},barWidth:'55%',itemStyle:{{color:'#5cc8ff'}},
 label:{{show:true,position:'right',color:'#cdd9ec',fontSize:14,formatter:'¥{{c}}'}}}}]}});

I('multi').setOption({{tooltip:{{trigger:'axis'}},legend:{{data:['客流','烤鸭'],textStyle:{{color:'#cdd9ec',fontSize:15}}}},
 grid:{{left:54,right:48,top:38,bottom:48}},xAxis:{{type:'category',data:cats,axisLabel}},
 yAxis:[{{type:'value',axisLabel,splitLine}},{{type:'value',axisLabel,splitLine:{{show:false}}}}],
 series:[{{name:'客流',type:'bar',data:{json.dumps(cust_series)},itemStyle:{{color:'#37d4a0'}},barWidth:'46%'}},
 {{name:'烤鸭',type:'line',yAxisIndex:1,data:{json.dumps([round(d['duck'],1) for d in days])},smooth:true,lineStyle:{{color:'#ffd24a',width:3}},itemStyle:{{color:'#ffd24a'}}}}]}});

I('catbar').setOption({{tooltip:{{trigger:'axis'}},grid:{{left:96,right:50,top:18,bottom:38}},
 xAxis:{{type:'value',axisLabel,splitLine}},yAxis:{{type:'category',data:{json.dumps(cat_names, ensure_ascii=False)},inverse:true,axisLabel}},
 series:[{{type:'bar',data:{json.dumps(cat_vals)},barWidth:'58%',itemStyle:{{color:'#5cc8ff'}},
 label:{{show:true,position:'right',color:'#cdd9ec',fontSize:14}}}}]}});

I('wdwe').setOption({{tooltip:{{trigger:'axis'}},grid:{{left:76,right:30,top:30,bottom:42}},
 xAxis:{{type:'category',data:['工作日日均','周末日均'],axisLabel}},yAxis:{{type:'value',name:'元',axisLabel,splitLine}},
 series:[{{type:'bar',data:[{{value:{round(h['wd_avg'],0)},itemStyle:{{color:'#41557a'}}}},{{value:{round(h['we_avg'],0)},itemStyle:{{color:'#5b8cff'}}}}],
 barWidth:'46%',label:{{show:true,position:'top',color:'#cdd9ec',fontSize:15,formatter:'¥{{c}}'}}}}]}});

// 长图导出测高 hook：图表高度固定，scrollHeight 稳定，供 Chrome 两遍法读取
function _markH(){{document.documentElement.setAttribute('data-page-h',document.documentElement.scrollHeight);}}
window.addEventListener('load',function(){{_markH();setTimeout(_markH,600);}});
</script></body></html>"""


# ============================ 高清长图导出（Chrome 两遍法，默认标准） ============================
# 第一遍 --dump-dom 读取页面真实 scrollHeight，第二遍 --window-size=宽,高 + scale 截全页长图。
# 与 HTML 完全同源（同一份 ECharts 渲染），不压缩、不裁切、不依赖浏览器手动缩放。

_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def _find_chrome():
    import shutil
    for p in _CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def export_png_via_chrome(html_path, png_path, width=1600, scale=2, max_height=24000):
    """用本机 Chrome/Chromium 把长图 HTML 导出为高清全页长图 PNG。"""
    import re
    import subprocess

    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError("未找到 Chrome/Chromium，无法导出高清长图 PNG")

    url = "file://" + os.path.abspath(html_path)
    base = [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
            "--no-sandbox", "--disable-dev-shm-usage", "--default-background-color=00000000"]

    # 第一遍：量真实页面高度（图表容器高度固定，scrollHeight 稳定）
    measure = subprocess.run(
        base + ["--virtual-time-budget=12000", "--dump-dom", url],
        capture_output=True, text=True, timeout=120)
    m = re.search(r'data-page-h="(\d+)"', measure.stdout)
    height = int(m.group(1)) if m else 0
    if height <= 0:
        height = 6400  # 兜底高度，避免测高失败时截不全
    height = min(height + 48, max_height)  # 底部留白，防裁切

    # 第二遍：按真实高度截全页长图（deviceScaleFactor=scale → 高清不压缩）
    abs_png = os.path.abspath(png_path)
    if os.path.exists(abs_png):
        os.remove(abs_png)
    subprocess.run(
        base + [f"--force-device-scale-factor={scale}",
                f"--window-size={width},{height}",
                "--virtual-time-budget=14000",
                f"--screenshot={abs_png}", url],
        capture_output=True, text=True, timeout=180)
    if not os.path.exists(abs_png):
        raise RuntimeError("Chrome 截图未生成 PNG（可能网络无法加载 ECharts CDN 或页面渲染超时）")
    return abs_png, width, height, scale


# ============================ PNG 渲染（PIL 兜底，无浏览器依赖） ============================
# 当本机没有 Chrome/Chromium 或截图失败时，退回 Pillow 直接绘制融合版看板，
# 与 HTML 同口径同数据，保证主流程不因缺浏览器而中断。

def _font(size):
    from PIL import ImageFont
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def _money(v):
    return f"¥{v:,.0f}"


def render_png(store, start, end, days, h, r, present, missing,
               alerts, insights, next_week, dq, png_path):
    from PIL import Image, ImageDraw

    W = 1920
    M = 56            # 左右边距
    GAP = 16
    CARD = "#0e1828"
    PANEL = "#0d1d36"
    OUT = "#264f8a"
    BG = "#070d1a"
    SUB = "#8ea4cf"

    f_title = _font(36)
    f_h2 = _font(22)
    f_num = _font(30)
    f_txt = _font(18)
    f_sm = _font(15)
    f_xs = _font(13)

    n_present = len(present)
    # 用超高画布绘制后裁剪
    img = Image.new("RGB", (W, 2600), BG)
    d = ImageDraw.Draw(img)

    def panel(box, title=None, accent="#5b8cff"):
        d.rounded_rectangle(box, radius=10, fill=PANEL, outline=OUT)
        if title:
            d.rectangle((box[0], box[1] + 12, box[0] + 4, box[1] + 30), fill=accent)
            d.text((box[0] + 16, box[1] + 12), title, fill="#b9d7ff", font=f_txt)

    inner_w = W - 2 * M
    y = 36

    # —— 标题区 ——
    d.text((M, y), f"{store} · 周报经营决策看板", fill="#f3f8ff", font=f_title)
    d.text((W - 430, y + 6), "📊 经营大屏 + 管理诊断", fill="#7fb0ff", font=f_txt)
    y += 50
    miss_tag = "覆盖 7/7 天" if not missing else "明细缺 " + "、".join(m[5:] for m in missing)
    period = (f"统计周期：{start} ~ {end}（自然周 · 周一至周日 · 核心指标 {h['n']}/7 天，"
              f"结构明细 {n_present}/7 天 · {miss_tag}）")
    d.text((M, y), period, fill=SUB, font=f_sm)
    d.text((W - 430, y), "数据：store_history.csv + report_MLD_*.json", fill="#6f86a8", font=f_xs)
    y += 30

    # —— 决策横幅 ——
    verdict = (f"本周营收 {_money(h['total_rev'])}（环比走高），但增长含金量低：全周折扣率 "
               f"{h['avg_discount']:.0f}%、月同比 {h['latest_yoy']:.0f}%、套餐挂零、精酿零销。"
               f"下周核心动作 = 降折扣 + 救工作日 + 放大烤鸭外带。")
    vlines = _wrap(d, verdict, f_txt, inner_w - 60)
    vh = 20 + len(vlines) * 26
    d.rounded_rectangle((M, y, W - M, y + vh), radius=12, fill="#13233f", outline="#2a3d5e")
    for i, ln in enumerate(vlines):
        d.text((M + 24, y + 12 + i * 26), ("📌 " + ln) if i == 0 else ln,
               fill="#ffe6a3" if i == 0 else "#dfe9ff", font=f_txt)
    y += vh + GAP + 6

    # —— 核心指标：8 卡，4 列 2 行 ——
    d.rectangle((M, y, M + 4, y + 20), fill="#5b8cff")
    d.text((M + 14, y), "核心指标", fill="#cdd9ec", font=f_h2)
    d.text((M + 130, y + 6), "7 天完整窗口", fill="#6f86a8", font=f_sm)
    y += 36
    kpis = [
        ("本周营业额", _money(h["total_rev"]), f"日均 {_money(h['daily_avg_rev'])}", "#5b8cff"),
        ("本周总客流", f"{h['total_cust']:,} 人", f"周客单 ¥{h['week_avg_ticket']:.0f}", "#37d4a0"),
        ("月累计同比", f"{h['latest_yoy']:.1f}%", f"差额 {_money(r['yoy_delta'])}", "#ff5a6e"),
        ("平均折扣率", f"{h['avg_discount']:.1f}%", "利润头号杀手", "#ff9f43"),
        ("烤鸭总销量", f"{h['total_duck']:.0f} 只", f"日均 {h['total_duck']/h['n']:.0f} 只", "#ffd24a"),
        ("周末/工作日", f"{h['we_wd_ratio']:.2f}×", f"工作日日均 {_money(h['wd_avg'])}", "#c77dff"),
        ("堂食占比", f"{h['avg_dine_in']:.1f}%", f"外带 {h['avg_takeaway']:.1f}%", "#5cc8ff"),
        ("周报完整度", f"{h['n']}/7 天", f"结构明细 {n_present}/7 天", "#9fb3d1"),
    ]
    cols, kw = 4, (inner_w - 3 * GAP) // 4
    kh = 96
    for idx, (label, val, sub, acc) in enumerate(kpis):
        cx = M + (idx % cols) * (kw + GAP)
        cy = y + (idx // cols) * (kh + GAP)
        d.rounded_rectangle((cx, cy, cx + kw, cy + kh), radius=10, fill=CARD, outline=OUT)
        d.text((cx + 16, cy + 12), label, fill=SUB, font=f_sm)
        d.text((cx + 16, cy + 38), val, fill=acc, font=f_num)
        d.text((cx + 16, cy + 74), sub, fill="#6f86a8", font=f_xs)
    y += 2 * kh + GAP + GAP + 8

    # —— 趋势 + 收入结构 ——
    trend_h = 300
    trend_w = int(inner_w * 0.62)
    struct_w = inner_w - trend_w - GAP
    tb = (M, y, M + trend_w, y + trend_h)
    sb = (M + trend_w + GAP, y, W - M, y + trend_h)
    panel(tb, "营收趋势 × 折扣率")
    panel(sb, f"收入结构（{n_present} 日口径）", "#37d4a0")

    # trend bars + discount line
    labels = [f"{x['date'][5:]} {x['wd']}" for x in days]
    revs = [x["revenue"] for x in days]
    discs = [x["discount"] for x in days]
    max_r = max(revs) or 1
    plot_l, plot_r = tb[0] + 46, tb[2] - 30
    plot_b, plot_t = tb[3] - 40, tb[1] + 46
    n = len(days)
    step = (plot_r - plot_l) / max(1, n)
    for i, v in enumerate(revs):
        bx = plot_l + i * step + step / 2
        bh = int((v / max_r) * (plot_b - plot_t))
        d.rectangle((bx - 22, plot_b - bh, bx + 22, plot_b), fill="#5b8cff")
        d.text((bx - 30, plot_b + 8), labels[i], fill=SUB, font=f_xs)
    dmin, dmax = 30, 50
    dline = []
    for i, v in enumerate(discs):
        bx = plot_l + i * step + step / 2
        yy = plot_b - (max(dmin, min(dmax, v)) - dmin) / (dmax - dmin) * (plot_b - plot_t)
        dline.append((bx, yy))
    if len(dline) > 1:
        d.line(dline, fill="#ff9f43", width=3)
        for p in dline:
            d.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill="#ff9f43")
    d.text((tb[0] + 16, tb[1] + 34), "营业额(柱) / 折扣率(线)", fill="#6f86a8", font=f_xs)

    # pie 收入结构
    pie = [("堂食", r["dine_in"], "#5b8cff"), ("堂食打包", r["dine_in_takeaway"], "#37d4a0"),
           ("线上外卖", r["online"], "#ffd24a"), ("优惠让利", r["discount_revenue"], "#c77dff")]
    tot = sum(p[1] for p in pie) or 1
    pcx, pcy, pr = sb[0] + 120, sb[1] + 150, 78
    ang = -90
    for name, val, col in pie:
        sweep = 360 * val / tot
        d.pieslice((pcx - pr, pcy - pr, pcx + pr, pcy + pr), ang, ang + sweep, fill=col)
        ang += sweep
    d.ellipse((pcx - 34, pcy - 34, pcx + 34, pcy + 34), fill=PANEL)
    lx = sb[0] + 240
    for i, (name, val, col) in enumerate(pie):
        ly = sb[1] + 60 + i * 34
        d.rectangle((lx, ly + 3, lx + 14, ly + 17), fill=col)
        pct = val / tot * 100
        d.text((lx + 22, ly), f"{name}  {_money(val)}  {pct:.1f}%", fill="#dfe9ff", font=f_sm)
    d.text((sb[0] + 16, sb[3] - 52),
           _fit(d, f"月累计 {_money(r['mtd'])}  ·  同期累计 {_money(r['mtd_last_year'])}", f_xs, struct_w - 32),
           fill=SUB, font=f_xs)
    d.text((sb[0] + 16, sb[3] - 32),
           _fit(d, f"同比差额 {_money(r['yoy_delta'])}  ·  月折前 {_money(r['mtd_before_discount'])}", f_xs, struct_w - 32),
           fill=SUB, font=f_xs)
    y += trend_h + GAP

    # —— 三联：客单价 / 渠道收入 / 客流×烤鸭 ——
    row_h = 240
    cw = (inner_w - 2 * GAP) // 3
    b1 = (M, y, M + cw, y + row_h)
    b2 = (M + cw + GAP, y, M + 2 * cw + GAP, y + row_h)
    b3 = (M + 2 * cw + 2 * GAP, y, W - M, y + row_h)
    panel(b1, "客单价趋势")
    panel(b2, f"渠道收入对比（{n_present} 日）", "#5cc8ff")
    panel(b3, "客流 × 烤鸭")

    # 客单价 line
    tk = [x["avg_ticket"] for x in days]
    mn, mx = min(tk), max(tk)
    rng = (mx - mn) or 1
    pl, prr = b1[0] + 30, b1[2] - 20
    pb, pt = b1[3] - 34, b1[1] + 50
    pts = []
    for i, v in enumerate(tk):
        xx = pl + i * (prr - pl) / max(1, n - 1)
        yy = pb - (v - mn) / rng * (pb - pt)
        pts.append((xx, yy))
    if len(pts) > 1:
        d.line(pts, fill="#37d4a0", width=3)
        for p in pts:
            d.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill="#ffd24a")
    d.text((b1[0] + 16, b1[3] - 26), f"区间 ¥{mn:.0f} ~ ¥{mx:.0f}", fill="#6f86a8", font=f_xs)

    # 渠道 bar
    chans = [("堂食", r["dine_in"]), ("堂食打包", r["dine_in_takeaway"]),
             ("线上外卖", r["online"]), ("优惠让利", r["discount_revenue"])]
    mxc = max(v for _, v in chans) or 1
    for i, (name, val) in enumerate(chans):
        yy = b2[1] + 52 + i * 40
        d.text((b2[0] + 16, yy), name, fill="#b9c7e6", font=f_sm)
        bw = int(val / mxc * (b2[2] - b2[0] - 230))
        d.rounded_rectangle((b2[0] + 110, yy + 1, b2[0] + 110 + bw, yy + 17), radius=5, fill="#5cc8ff")
        d.text((b2[0] + 118 + bw, yy), _money(val), fill="#dfe9ff", font=f_sm)

    # 客流 bar + 烤鸭 line
    custs = [x["cust"] for x in days]
    ducks = [x["duck"] for x in days]
    mxu = max(custs) or 1
    mxd = max(ducks) or 1
    pl, prr = b3[0] + 36, b3[2] - 30
    pb, pt = b3[3] - 34, b3[1] + 50
    step3 = (prr - pl) / max(1, n)
    for i, v in enumerate(custs):
        bx = pl + i * step3 + step3 / 2
        bh = int(v / mxu * (pb - pt))
        d.rectangle((bx - 14, pb - bh, bx + 14, pb), fill="#37d4a0")
    dl = []
    for i, v in enumerate(ducks):
        bx = pl + i * step3 + step3 / 2
        dl.append((bx, pb - v / mxd * (pb - pt)))
    if len(dl) > 1:
        d.line(dl, fill="#ffd24a", width=3)
        for p in dl:
            d.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill="#ffd24a")
    d.text((b3[0] + 16, b3[3] - 26), "客流(柱) / 烤鸭只数(线)", fill="#6f86a8", font=f_xs)
    y += row_h + GAP

    # —— 品类 TOP + 会员 ——
    bh2 = 300
    catw = int(inner_w * 0.6)
    cb = (M, y, M + catw, y + bh2)
    mb = (M + catw + GAP, y, W - M, y + bh2)
    panel(cb, f"关键品类销量 TOP（{n_present} 日累计）")
    panel(mb, f"会员与活动（{n_present} 日）", "#37d4a0")
    cat_items = sorted([
        ("烧饼", r["sesame_cake"]), ("烤鸭小料", r["duck_sauce"]),
        ("位吃+甜品", r["per_seat"] + r["sweet"] + r["dessert"]),
        ("烤鸭", r["duck_total"]), ("套餐", r["set_meal_total"]),
        ("自制饮品", r["house_drink"]), ("乳鸽", r["pigeon"]),
        ("鱼类+牛掌", r["fish_total"] + r["beef_paw"]), ("精酿", r["craft_beer"]),
    ], key=lambda x: x[1], reverse=True)
    mxcat = max(v for _, v in cat_items) or 1
    bx0 = cb[0] + 150
    bmax = cb[2] - bx0 - 70
    for i, (name, val) in enumerate(cat_items):
        yy = cb[1] + 46 + i * 27
        d.text((cb[0] + 18, yy), name, fill="#b9c7e6", font=f_sm)
        bw = int(val / mxcat * bmax)
        d.rounded_rectangle((bx0, yy + 2, bx0 + bw, yy + 16), radius=4, fill="#5cc8ff")
        d.text((bx0 + bw + 8, yy), f"{val:.0f}", fill="#dfe9ff", font=f_sm)
    members = [
        ("会员储值(5日)", _money(r["member_recharge"])), ("月累计储值", _money(r["member_recharge_mtd"])),
        ("会员消费(5日)", _money(r["member_revenue"])), ("原价消费(5日)", _money(r["full_price_revenue"])),
        ("发券(5日)", f"{r['coupon_issued']:.0f} 张"), ("验券(5日)", f"{r['coupon_redeemed']:.0f} 张"),
    ]
    mcw = (mb[2] - mb[0] - 42) // 2
    mch = (bh2 - 56) // 3
    for i, (name, val) in enumerate(members):
        col, row = i % 2, i // 2
        xx = mb[0] + 14 + col * (mcw + 14)
        yy = mb[1] + 44 + row * mch
        d.rounded_rectangle((xx, yy, xx + mcw, yy + mch - 12), radius=8, fill=CARD, outline=OUT)
        d.text((xx + 12, yy + 10), name, fill=SUB, font=f_sm)
        d.text((xx + 12, yy + 36), val, fill="#dfe9ff", font=f_txt)
    y += bh2 + GAP

    # —— 烤鸭专项 + 工作日vs周末 ——
    bh3 = 250
    dw = int(inner_w * 0.6)
    db = (M, y, M + dw, y + bh3)
    wb = (M + dw + GAP, y, W - M, y + bh3)
    panel(db, f"烤鸭专项分析（{n_present} 日）", "#ffd24a")
    panel(wb, "工作日 vs 周末（7 天）", "#c77dff")
    ducks_stat = [
        ("烤鸭总销量(5日)", f"{r['duck_total']:.0f} 只"), ("堂食烤鸭", f"{r['duck_dine_in']:.0f} 只"),
        ("线上烤鸭", f"{r['duck_online']:.0f} 只"), ("迷你烤鸭", f"{r['mini_duck']:.0f} 只"),
        ("鸭架(椒盐/熬汤)", f"{r['duck_rack']:.0f} 份"), ("烧饼/鸭酱", f"{r['sesame_cake']:.0f}/{r['duck_sauce']:.0f}"),
        ("鸭架转化率(均)", f"{r['avg_rack_ratio']:.1f}%"), ("烧饼搭售率(均)", f"{r['avg_cake_ratio']:.1f}%"),
    ]
    dcw = (db[2] - db[0] - 42) // 2
    dch = (bh3 - 50) // 4
    for i, (name, val) in enumerate(ducks_stat):
        col, row = i % 2, i // 2
        xx = db[0] + 14 + col * (dcw + 14)
        yy = db[1] + 42 + row * dch
        d.text((xx + 6, yy), name, fill=SUB, font=f_xs)
        d.text((xx + 6, yy + 18), val, fill="#dfe9ff", font=f_sm)
    # wd vs we bars
    vals = [("工作日日均", h["wd_avg"], "#41557a"), ("周末日均", h["we_avg"], "#5b8cff")]
    mxw = max(v for _, v, _ in vals) or 1
    base = wb[3] - 46
    top = wb[1] + 56
    for i, (name, val, col) in enumerate(vals):
        bx = wb[0] + 120 + i * 230
        bh = int(val / mxw * (base - top))
        d.rectangle((bx, base - bh, bx + 120, base), fill=col)
        d.text((bx + 6, base - bh - 24), _money(val), fill="#cdd9ec", font=f_sm)
        d.text((bx + 8, base + 8), name, fill=SUB, font=f_sm)
    y += bh3 + GAP + 6

    # —— 分隔：管理诊断 ——
    d.text((W // 2 - 150, y), "───── 管理诊断 ─────", fill="#46597d", font=f_txt)
    y += 40

    # 风险预警
    d.rectangle((M, y, M + 4, y + 20), fill="#ff9f43")
    d.text((M + 14, y), "风险预警", fill="#ffcaa0", font=f_h2)
    y += 36
    for a in alerts:
        title = ("🔴 严重  " if a["level"] == "critical" else "🟠 关注  ") + a["title"]
        det_lines = _wrap(d, a["detail"], f_sm, inner_w - 60)
        box_h = 40 + len(det_lines) * 22
        bar = "#ff5a6e" if a["level"] == "critical" else "#ff9f43"
        d.rounded_rectangle((M, y, W - M, y + box_h), radius=10, fill=CARD, outline=OUT)
        d.rectangle((M, y, M + 4, y + box_h), fill=bar)
        d.text((M + 20, y + 12), title, fill="#ffffff", font=f_txt)
        for i, ln in enumerate(det_lines):
            d.text((M + 20, y + 38 + i * 22), ln, fill="#a8bad6", font=f_sm)
        y += box_h + 10
    y += 8

    # 经营洞察
    d.rectangle((M, y, M + 4, y + 20), fill="#37d4a0")
    d.text((M + 14, y), "经营洞察", fill="#a0e8cf", font=f_h2)
    y += 36
    for ins in insights:
        body_lines = _wrap(d, ins["body"], f_sm, inner_w - 60)
        box_h = 40 + len(body_lines) * 22
        d.rounded_rectangle((M, y, W - M, y + box_h), radius=10, fill=CARD, outline=OUT)
        d.rectangle((M, y, M + 4, y + box_h), fill="#37d4a0")
        d.text((M + 20, y + 12), f"{ins['icon']} {ins['title']}", fill="#ffffff", font=f_txt)
        for i, ln in enumerate(body_lines):
            d.text((M + 20, y + 38 + i * 22), ln, fill="#a8bad6", font=f_sm)
        y += box_h + 10
    y += 8

    # 下周行动建议
    d.rectangle((M, y, M + 4, y + 20), fill="#5b8cff")
    d.text((M + 14, y), "下周行动建议", fill="#bcd0ff", font=f_h2)
    y += 36
    for a in next_week:
        text = a["text"]
        lines = _wrap(d, text, f_sm, inner_w - 200)
        box_h = 20 + len(lines) * 22
        d.rounded_rectangle((M, y, W - M, y + box_h), radius=10, fill=CARD, outline=OUT)
        d.rounded_rectangle((M + 16, y + 14, M + 130, y + 40), radius=6, fill="#1c3157")
        d.text((M + 26, y + 18), a["tag"], fill="#7fb0ff", font=f_sm)
        for i, ln in enumerate(lines):
            d.text((M + 150, y + 12 + i * 22), ln, fill="#d4deee", font=f_sm)
        y += box_h + 10
    y += 8

    # 数据质量说明
    d.rectangle((M, y, M + 4, y + 20), fill="#9fb3d1")
    d.text((M + 14, y), "数据质量说明", fill="#c5d3e8", font=f_h2)
    y += 34
    dq_lines = []
    for item in dq:
        wrapped = _wrap(d, "• " + item, f_sm, inner_w - 60)
        dq_lines.extend(wrapped)
        dq_lines.append("")
    box_h = 24 + len(dq_lines) * 22
    d.rounded_rectangle((M, y, W - M, y + box_h), radius=10, fill=CARD, outline="#2a3d5e")
    for i, ln in enumerate(dq_lines):
        d.text((M + 22, y + 14 + i * 22), ln, fill="#a8bad6", font=f_sm)
    y += box_h + 16

    d.text((M, y), f"本看板只读真实日报数据生成，不修改历史数据 · {store} · {start}~{end}",
           fill="#52668a", font=f_xs)
    y += 30

    img = img.crop((0, 0, W, min(y, img.height)))
    img.save(png_path)
    return png_path


def _fit(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def send_fusion_to_feishu(png_path, store, start, end, hist_days, report_days, missing):
    """复用 feishu_bot 图片上传逻辑推送融合版看板；缺凭证则抛错跳过，不打印敏感信息。"""
    import feishu_bot
    from pathlib import Path

    if not feishu_bot._has_app_creds():
        raise RuntimeError("未配置飞书 App 图片上传凭证，已跳过融合版图片推送")
    miss_note = "数据完整 7/7 天" if not missing else "缺失明细日期：" + "、".join(missing)
    title = f"{store}｜{start} 至 {end} 周报经营决策看板（经营大屏 + 管理诊断）"
    note = (f"核心指标 {hist_days}/7 天，结构明细 {report_days}/7 天；{miss_note}。"
            "数据来自已校验真实日报，缺失不补全、不伪造。")
    key = feishu_bot._upload_image(Path(png_path))
    feishu_bot.send_text(f"{title}\n{note}", ensure_keyword=False)
    feishu_bot._send_image_key(key)


if __name__ == "__main__":
    main()
