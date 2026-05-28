"""第 3 层:出图。

便宜坊场景 4 张关键图:
  1. 核心 KPI 卡(本日收入 / 来客数 / 客单价 / 月累计同比)
  2. 收入结构饼图(堂食 / 外卖打包 / 线上外卖)
  3. 会员消费构成(原价 / 会员消费 / 其他优惠)
  4. 各品类销量横向对比 + 烤鸭明细

务必压到 500KB 内,飞书上传才不超时。
"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from PIL import Image
import config

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "STHeiti", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

COLOR_MAIN = "#2563eb"
COLOR_ACCENT = "#f97316"
COLOR_GREEN = "#16a34a"
COLOR_RED = "#dc2626"
COLOR_YELLOW = "#f59e0b"
COLOR_BG = "#ffffff"


def _save(fig, path: Path, max_kb: int = 500) -> Path:
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor=COLOR_BG)
    plt.close(fig)
    if path.stat().st_size / 1024 > max_kb:
        img = Image.open(path).convert("RGB")
        if img.width > 1200:
            img = img.resize((1200, int(img.height * 1200 / img.width)))
        img.save(path, "PNG", optimize=True)
    return path


# ---------- 图 1:核心 KPI 卡 ----------
def chart_kpi(daily: dict) -> Path:
    rev = daily["revenue"]
    traf = daily["traffic"]
    der = daily["derived"]
    meta = daily["meta"]

    fig, axes = plt.subplots(1, 4, figsize=(13, 3.5))

    yoy_pct = der.get("yoy_pct", 0) * 100
    yoy_color = COLOR_GREEN if yoy_pct >= 0 else COLOR_RED
    yoy_arrow = "▲" if yoy_pct >= 0 else "▼"

    metrics = [
        ("本日收入", f"¥{rev.get('revenue_today', 0):,.0f}", "", ""),
        ("来客数", f"{traf.get('customer_count', 0):.0f}", "", ""),
        ("客单价", f"¥{traf.get('avg_check', 0):.2f}", "", ""),
        ("月累计同比", f"{yoy_arrow} {yoy_pct:+.1f}%", yoy_color,
         f"差额 ¥{rev.get('revenue_yoy_delta', 0):,.0f}"),
    ]

    for ax, (name, val, color, sub) in zip(axes, metrics):
        ax.axis("off")
        ax.text(0.5, 0.78, name, ha="center", fontsize=12, color="#6b7280", transform=ax.transAxes)
        ax.text(0.5, 0.43, val, ha="center", fontsize=22, fontweight="bold",
                color=color or "#111827", transform=ax.transAxes)
        if sub:
            ax.text(0.5, 0.13, sub, ha="center", fontsize=10, color=color or "#6b7280", transform=ax.transAxes)

    fig.suptitle(f"{meta['store_name']} · {meta['date']} 核心指标",
                 fontsize=15, fontweight="bold", y=1.02)
    return _save(fig, config.OUTPUT_DIR / f"kpi_{meta['store_id']}_{meta['date']}.png")


# ---------- 图 2:收入结构饼图 ----------
def chart_revenue_structure(daily: dict) -> Path | None:
    rev = daily["revenue"]
    parts = [
        ("堂食", rev.get("dine_in_revenue", 0), COLOR_MAIN),
        ("堂食外卖", rev.get("dine_in_takeaway_revenue", 0), COLOR_ACCENT),
        ("线上外卖", rev.get("online_takeaway_revenue", 0), COLOR_GREEN),
    ]
    total = sum(v for _, v, _ in parts)
    if total <= 0:
        return None

    labels = [n for n, _, _ in parts]
    sizes = [v for _, v, _ in parts]
    colors = [c for _, _, c in parts]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    ax1.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%",
            startangle=90, wedgeprops={"edgecolor": "white", "linewidth": 2},
            textprops={"fontsize": 11})
    ax1.set_title("收入结构占比", fontsize=13, fontweight="bold", pad=10)

    # 右边出数字明细
    ax2.axis("off")
    y = 0.85
    ax2.text(0.05, 0.95, "金额明细", fontsize=13, fontweight="bold", transform=ax2.transAxes)
    for (name, val, color) in parts:
        pct = val / total * 100
        ax2.add_patch(plt.Rectangle((0.05, y - 0.02), 0.04, 0.04, color=color, transform=ax2.transAxes))
        ax2.text(0.12, y, f"{name}: ¥{val:,.2f}  ({pct:.1f}%)",
                 fontsize=11, transform=ax2.transAxes, va="center")
        y -= 0.12

    meta = daily["meta"]
    fig.suptitle(f"{meta['store_name']} · {meta['date']} 收入结构",
                 fontsize=14, fontweight="bold", y=1.0)
    return _save(fig, config.OUTPUT_DIR / f"revenue_struct_{meta['store_id']}_{meta['date']}.png")


# ---------- 图 3:会员消费构成 ----------
def chart_member_breakdown(daily: dict) -> Path | None:
    m = daily["member_consumption"]
    parts = [
        ("原价消费", m.get("full_price_revenue", 0), m.get("full_price_ratio", 0), COLOR_GREEN),
        ("会员消费", m.get("member_revenue", 0), m.get("member_revenue_ratio", 0), COLOR_MAIN),
        ("其他优惠", m.get("discount_revenue", 0), m.get("discount_ratio", 0), COLOR_RED),
    ]
    if sum(v for _, v, _, _ in parts) <= 0:
        return None

    labels = [p[0] for p in parts]
    vals = [p[1] for p in parts]
    colors = [p[3] for p in parts]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    bars = ax.barh(labels, vals, color=colors, alpha=0.85)
    for bar, (_, v, ratio, _) in zip(bars, parts):
        # 占比兼容两种格式:0.4374 或 43.74
        ratio_pct = ratio * 100 if ratio < 1 else ratio
        ax.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height() / 2,
                f"¥{v:,.0f}  ({ratio_pct:.2f}%)", va="center", fontsize=11)

    ax.set_title("堂食会员消费构成(警惕优惠占比过高)", fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel("金额(元)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(0, max(vals) * 1.25)

    # 红线警示:优惠占比 > 40%
    discount_ratio = parts[2][2]
    discount_pct = discount_ratio * 100 if discount_ratio < 1 else discount_ratio
    if discount_pct > 40:
        ax.text(0.5, -0.18, f"[警示] 优惠占比 {discount_pct:.2f}% 偏高,利润被打折侵蚀",
                ha="center", fontsize=11, color=COLOR_RED, transform=ax.transAxes, fontweight="bold")

    meta = daily["meta"]
    return _save(fig, config.OUTPUT_DIR / f"member_{meta['store_id']}_{meta['date']}.png")


# ---------- 图 4:品类销量横向对比 ----------
def chart_categories(daily: dict) -> Path | None:
    cats = daily.get("dishes_by_category", {})
    if not cats:
        return None

    # 每个大类的销量汇总(剔除占比等非销量字段)
    SKIP_KEYS = {"sesame_cake_ratio", "duck_rack_ratio"}
    cat_totals = {}
    for cat_name, fields in cats.items():
        total = sum(v for k, v in fields.items()
                    if isinstance(v, (int, float)) and k not in SKIP_KEYS)
        cat_totals[cat_name] = total

    if not any(cat_totals.values()):
        return None

    # 左图:大类总销量;右图:烤鸭明细(主打品类拆开看)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.5))

    names = list(cat_totals.keys())
    vals = list(cat_totals.values())
    colors_list = [COLOR_MAIN, COLOR_ACCENT, COLOR_GREEN, COLOR_YELLOW, "#a855f7"]
    bars = ax1.barh(names[::-1], vals[::-1], color=colors_list[:len(names)][::-1], alpha=0.85)
    for bar, v in zip(bars, vals[::-1]):
        ax1.text(bar.get_width() * 1.01 if bar.get_width() > 0 else 0.5,
                 bar.get_y() + bar.get_height() / 2,
                 f"{v:.1f}", va="center", fontsize=11)
    ax1.set_title("各品类销量汇总(份)", fontsize=13, fontweight="bold", pad=10)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    if max(vals) > 0:
        ax1.set_xlim(0, max(vals) * 1.2)

    # 烤鸭明细
    duck = cats.get("烤鸭类", {})
    duck_items = [
        ("堂食烤鸭", duck.get("roasted_duck_dine_in", 0)),
        ("迷你烤鸭", duck.get("mini_duck", 0)),
        ("线上烤鸭", duck.get("roasted_duck_online", 0)),
        ("椒盐鸭架", duck.get("spiced_duck_rack", 0)),
        ("鸭架烧饼", duck.get("duck_rack_sesame_cake", 0)),
        ("烤鸭小料", duck.get("duck_sauce", 0)),
    ]
    duck_names = [n for n, _ in duck_items]
    duck_vals = [v for _, v in duck_items]

    ax2.barh(duck_names[::-1], duck_vals[::-1], color=COLOR_MAIN, alpha=0.85)
    for i, v in enumerate(duck_vals[::-1]):
        ax2.text(v + max(duck_vals) * 0.02 if max(duck_vals) > 0 else 0.5,
                 i, f"{v:.1f}", va="center", fontsize=10)
    ax2.set_title("烤鸭主品类明细(份)", fontsize=13, fontweight="bold", pad=10)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    if max(duck_vals) > 0:
        ax2.set_xlim(0, max(duck_vals) * 1.25)

    meta = daily["meta"]
    fig.suptitle(f"{meta['store_name']} · {meta['date']} 品类销量分析",
                 fontsize=14, fontweight="bold", y=1.02)
    return _save(fig, config.OUTPUT_DIR / f"categories_{meta['store_id']}_{meta['date']}.png")


# ---------- 统一入口 ----------
def make_all_charts(daily: dict) -> list[Path]:
    charts = []
    for fn in (chart_kpi, chart_revenue_structure, chart_member_breakdown, chart_categories):
        try:
            p = fn(daily)
            if p:
                charts.append(p)
        except Exception as e:
            import traceback
            print(f"[visualizer] {fn.__name__} 出错: {e}")
            traceback.print_exc()
    return charts
