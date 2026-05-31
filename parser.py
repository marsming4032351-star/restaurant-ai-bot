"""第 1 层:解析便宜坊门店日报。

输入:形如"便宜坊_马连道_2026-05-27.xlsx"或"20260527.xlsx"的二维报表
输出:结构化 dict,字段名见 field_map.yaml

设计思路:
- 不依赖列名(因为是二维布局,没"列名"概念)
- 关键字定位法:遍历所有 cell,找到中文字段名 → 取它右边一格的数值
- 字段映射独立在 field_map.yaml,以后你改表格只动 yaml
"""
from __future__ import annotations
import re
import yaml
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional
import openpyxl
import config


# ---------- 加载字段映射 ----------
def load_field_map() -> dict:
    fp = Path(__file__).parent / "field_map.yaml"
    return yaml.safe_load(fp.read_text(encoding="utf-8"))


# ---------- 从文件名抓日期 ----------
def extract_date_from_filename(filename: str, patterns: list) -> Optional[date]:
    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return date(y, mo, d)
            except ValueError:
                continue
    return None


# ---------- 扫描 Excel 所有 cell,建索引 ----------
def scan_cells(xlsx_path: Path) -> list[tuple[int, int, object, str]]:
    """返回 [(row, col, value, sheet_name), ...]。
    便宜坊日报通常单 sheet,但兼容多 sheet。"""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    cells = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cells.append((cell.row, cell.column, cell.value, ws.title))
    return cells


def extract_date_from_cells(cells: list[tuple[int, int, object, str]]) -> Optional[date]:
    """Read the business date from report title/header cells."""
    patterns = [
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})",
        r"(\d{4})(\d{2})(\d{2})",
    ]
    for _row, _col, value, _sheet in cells:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            continue
        for pattern in patterns:
            match = re.search(pattern, value)
            if not match:
                continue
            y, mo, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                return date(y, mo, d)
            except ValueError:
                continue
    return None


def find_value_right_of(cells, keyword: str, sheet: str = None) -> Optional[float]:
    """找到 cell 文本完全等于(或包含)keyword 的格子,返回它右边一格的数值。
    去除空格、全角符号、下划线等噪声后匹配。"""
    key_norm = _normalize(keyword)
    for r, c, v, s in cells:
        if sheet and s != sheet:
            continue
        if not isinstance(v, str):
            continue
        if _normalize(v) == key_norm or key_norm in _normalize(v):
            # 找右边最近的数字 cell(允许跨 1-2 格,有些表格中间会有合并/空格)
            for offset in (1, 2, 3):
                for r2, c2, v2, s2 in cells:
                    if s2 == s and r2 == r and c2 == c + offset and isinstance(v2, (int, float)):
                        return float(v2)
            # 找下面一格(有些"月累计"在下方)
            for r2, c2, v2, s2 in cells:
                if s2 == s and r2 == r + 1 and c2 == c and isinstance(v2, (int, float)):
                    return float(v2)
    return None


def _normalize(s: str) -> str:
    """统一中英文/全半角/分隔符,提高匹配命中率。"""
    if not isinstance(s, str):
        return ""
    return (s.replace(" ", "")
             .replace("\u3000", "")
             .replace("/", "_")
             .replace("/", "_")
             .replace("(", "(").replace(")", ")")
             .strip())


# ---------- 主入口 ----------
def load_daily(file_path: Path, report_date: Optional[date] = None) -> dict:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"日报不存在:{file_path}")

    fmap = load_field_map()

    # 1) 扫所有 cell
    cells = scan_cells(file_path)
    print(f"      扫描到 {len(cells)} 个非空 cell")

    # 2) 日期:优先用报表表头，其次用参数，最后从文件名抓。
    header_date = extract_date_from_cells(cells)
    if header_date is not None:
        if report_date is not None and report_date != header_date:
            print(f"      ⚠️  忽略传入日期 {report_date}，使用报表表头业务日期 {header_date}")
        report_date = header_date
    elif report_date is None:
        report_date = extract_date_from_filename(file_path.name, fmap["meta"]["date_patterns"])
    if report_date is None:
        raise ValueError(f"无法从报表表头或文件名 {file_path.name} 抓出日期,请用 --date 参数指定")

    # 3) 按 yaml 抽字段
    def extract_group(group_dict: dict) -> dict:
        result = {}
        miss = []
        for cn_key, std_key in group_dict.items():
            val = find_value_right_of(cells, cn_key)
            if val is None:
                miss.append(cn_key)
                result[std_key] = 0
            else:
                result[std_key] = val
        if miss:
            print(f"      ⚠️  未找到字段: {miss}")
        return result

    revenue = extract_group(fmap["revenue"])
    member = extract_group(fmap["member_consumption"])
    traffic = extract_group(fmap["traffic"])

    # 菜品按大类组织
    dishes_by_category = {}
    for cat_name, cat_fields in fmap["dish_categories"].items():
        dishes_by_category[cat_name] = extract_group(cat_fields)

    # 4) 派生指标
    derived = _derive_metrics(revenue, member, traffic, dishes_by_category)

    return {
        "meta": {
            "date": str(report_date),
            "weekday": report_date.strftime("%A"),
            "store_id": fmap["meta"]["store_id"],
            "store_name": fmap["meta"]["store_name"],
        },
        "revenue": revenue,
        "member_consumption": member,
        "traffic": traffic,
        "dishes_by_category": dishes_by_category,
        "derived": derived,
    }


def _derive_metrics(revenue, member, traffic, dishes) -> dict:
    """从原始字段派生分析指标。"""
    d = {}

    # 收入结构占比
    today_rev = revenue.get("revenue_today", 0)
    if today_rev > 0:
        d["dine_in_share"] = round(revenue.get("dine_in_revenue", 0) / today_rev, 4)
        d["online_share"] = round(revenue.get("online_takeaway_revenue", 0) / today_rev, 4)
        d["takeaway_share"] = round(revenue.get("dine_in_takeaway_revenue", 0) / today_rev, 4)

    # 折扣健康度:折前 vs 实收
    before = revenue.get("revenue_today_before_discount", 0)
    if before > 0 and today_rev > 0:
        d["discount_rate"] = round(1 - today_rev / before, 4)   # 整体折扣率
        d["effective_price_ratio"] = round(today_rev / before, 4)

    # 同比健康度(用月累计)
    mtd = revenue.get("revenue_month_to_date", 0)
    last_year_mtd = revenue.get("revenue_same_period_last_year", 0)
    if last_year_mtd > 0:
        d["yoy_pct"] = round((mtd - last_year_mtd) / last_year_mtd, 4)

    # 客单价(优先用报表自带的,没有则算)
    cnt = traffic.get("customer_count", 0)
    if traffic.get("avg_check", 0) == 0 and cnt > 0:
        traffic["avg_check"] = round(today_rev / cnt, 2)

    # 烤鸭总销量(主打品类汇总)
    duck_cat = dishes.get("烤鸭类", {})
    d["duck_total"] = (duck_cat.get("roasted_duck_dine_in", 0)
                       + duck_cat.get("mini_duck", 0)
                       + duck_cat.get("roasted_duck_online", 0))

    # 套餐健康度(套餐全 0 是个警讯)
    set_cat = dishes.get("套餐类", {})
    d["set_meal_total"] = sum(v for k, v in set_cat.items() if isinstance(v, (int, float)))

    return d


# ---------- 历史累积(简单 parquet) ----------
def append_history(daily: dict, history_path: Optional[Path] = None) -> Path:
    history_path = history_path or (config.DATA_DIR / "history.parquet")
    flat = {
        "date": daily["meta"]["date"],
        "store_id": daily["meta"]["store_id"],
        **daily["revenue"],
        **daily["member_consumption"],
        **daily["traffic"],
        **daily["derived"],
    }
    new = pd.DataFrame([flat])
    new["date"] = pd.to_datetime(new["date"]).dt.date

    if history_path.exists():
        hist = pd.read_parquet(history_path)
        hist = hist[~((hist["date"] == new["date"].iloc[0]) &
                      (hist["store_id"] == new["store_id"].iloc[0]))]
        out = pd.concat([hist, new], ignore_index=True)
    else:
        out = new
    out.to_parquet(history_path, index=False)
    return history_path


def enrich_with_history(daily: dict, history_path: Optional[Path] = None) -> dict:
    history_path = history_path or (config.DATA_DIR / "history.parquet")
    if not history_path.exists():
        return daily

    hist = pd.read_parquet(history_path)
    hist["date"] = pd.to_datetime(hist["date"]).dt.date
    store = daily["meta"]["store_id"]
    today_dt = pd.to_datetime(daily["meta"]["date"]).date()
    hist = hist[hist["store_id"] == store].sort_values("date")

    def _row_on(target: date):
        m = hist[hist["date"] == target]
        return m.iloc[0].to_dict() if not m.empty else None

    daily["yesterday"] = _row_on(today_dt - timedelta(days=1))
    daily["last_week_same_day"] = _row_on(today_dt - timedelta(days=7))

    last7 = hist[(hist["date"] < today_dt) & (hist["date"] >= today_dt - timedelta(days=7))]
    if not last7.empty and "revenue_today" in last7.columns:
        daily["last_7d_avg"] = {
            "revenue_today": round(last7["revenue_today"].mean(), 2),
            "customer_count": round(last7["customer_count"].mean(), 1)
                              if "customer_count" in last7 else 0,
        }
    return daily
