"""历史数据管理：每次跑完日报后把结构化字段追加到 data/store_history.csv。

特性：
- 自动创建 data/ 目录和 CSV 文件（含表头）
- 检测重复（同一天同一门店），提示用户选择覆盖或跳过
- cron / 非交互模式下，重复时自动跳过（不报错）
- 可用 --force 标志强制覆盖
"""
from __future__ import annotations
import csv
from pathlib import Path
import config

HISTORY_FILE = config.DATA_DIR / "store_history.csv"

COLUMNS = [
    "date",
    "store_name",
    "revenue",
    "customer_count",
    "avg_ticket",
    "month_yoy",        # 月累计同比，单位 %，负数表示下滑
    "discount_rate",    # 折扣率，单位 %
    "dine_in_ratio",    # 堂食占比，单位 %
    "takeaway_ratio",   # 线上外卖占比，单位 %
    "roast_duck_sales", # 烤鸭日销售总量（份）
    "warning_level",    # 健康 / 警示 / 异常
    "summary",          # AI 一句话总结
    "suggestions",      # AI 建议（用 " | " 分隔）
]


def _extract_row(daily: dict, report: dict) -> dict:
    """从 daily + report 提取 CSV 行字段。"""
    rev  = daily.get("revenue", {})
    trf  = daily.get("traffic", {})
    der  = daily.get("derived", {})
    meta = daily.get("meta", {})
    sugs = report.get("suggestions", [])

    def pct(val) -> float:
        """将 0-1 小数转为保留2位的百分数。"""
        return round((val or 0) * 100, 2)

    return {
        "date":           str(meta.get("date", "")),
        "store_name":     meta.get("store_name", meta.get("store_id", "")),
        "revenue":        rev.get("revenue_today", ""),
        "customer_count": int(trf.get("customer_count") or 0),
        "avg_ticket":     round(trf.get("avg_check") or 0, 2),
        "month_yoy":      pct(der.get("yoy_pct")),
        "discount_rate":  pct(der.get("discount_rate")),
        "dine_in_ratio":  pct(der.get("dine_in_share")),
        "takeaway_ratio": pct(der.get("online_share")),
        "roast_duck_sales": der.get("duck_total", ""),
        "warning_level":  report.get("health_level", ""),
        "summary":        report.get("headline", ""),
        "suggestions":    " | ".join(sugs),
    }


def _read_existing() -> list[dict]:
    """读取现有 CSV，返回行列表；文件不存在则返回空列表。"""
    if not HISTORY_FILE.exists() or HISTORY_FILE.stat().st_size == 0:
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_all(rows: list[dict], new_row: dict) -> None:
    """整体重写 CSV（用于覆盖已有行的场景）。"""
    with open(HISTORY_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        writer.writerow(new_row)


def _append_row(new_row: dict) -> None:
    """追加一行；若文件不存在则先写表头。"""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    need_header = not HISTORY_FILE.exists() or HISTORY_FILE.stat().st_size == 0
    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if need_header:
            writer.writeheader()
        writer.writerow(new_row)


def save(daily: dict, report: dict, force: bool = False) -> bool:
    """把今日数据追加到 store_history.csv。

    Args:
        daily:  parser 输出的结构化字典
        report: analyst 输出的诊断字典
        force:  True = 不询问直接覆盖重复行

    Returns:
        True  = 成功写入
        False = 用户选择跳过（或非交互模式下检测到重复）
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    row       = _extract_row(daily, report)
    date_val  = row["date"]
    store_val = row["store_name"]

    existing  = _read_existing()
    dup_idx   = [i for i, r in enumerate(existing)
                 if r.get("date") == date_val and r.get("store_name") == store_val]

    if dup_idx:
        if force:
            # 静默覆盖
            for i in sorted(dup_idx, reverse=True):
                existing.pop(i)
            _write_all(existing, row)
            print(f"[history] ✅ 已覆盖: {store_val} · {date_val}")
            return True

        # 交互模式：询问
        print(f"\n[history] ⚠️  {store_val} · {date_val} 已有历史记录。")
        print("[history]    输入 y 覆盖，其他键跳过：", end="", flush=True)
        try:
            answer = input().strip().lower()
        except EOFError:
            # cron / 管道模式，无法交互 → 跳过
            answer = "n"

        if answer != "y":
            print("[history] 跳过，保留原有记录。")
            return False

        for i in sorted(dup_idx, reverse=True):
            existing.pop(i)
        _write_all(existing, row)
        print(f"[history] ✅ 已覆盖: {store_val} · {date_val} → {HISTORY_FILE.name}")
        return True

    # 无重复，直接追加
    _append_row(row)
    print(f"[history] ✅ 已追加: {store_val} · {date_val} → {HISTORY_FILE.name}")
    return True


def show_recent(n: int = 7) -> None:
    """打印最近 n 条历史记录（调试用）。"""
    rows = _read_existing()
    if not rows:
        print("[history] 暂无历史数据。")
        return
    recent = rows[-n:]
    header = f"{'日期':<12} {'门店':<12} {'收入':>10} {'来客':>6} {'客单价':>8} {'同比':>8} {'折扣率':>8} {'警示':<6}"
    print(header)
    print("-" * len(header))
    for r in recent:
        print(f"{r['date']:<12} {r['store_name']:<12} "
              f"{float(r['revenue'] or 0):>10,.0f} "
              f"{r['customer_count']:>6} "
              f"{float(r['avg_ticket'] or 0):>8.2f} "
              f"{float(r['month_yoy'] or 0):>+7.1f}% "
              f"{float(r['discount_rate'] or 0):>7.1f}% "
              f"{r['warning_level']:<6}")
