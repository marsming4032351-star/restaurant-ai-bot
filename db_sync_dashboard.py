#!/usr/bin/env python3
"""把本地 CSV 数据同步进飞书妙搭应用的 daily_sales 表（全表镜像）。

背景：妙搭应用已升级为 DB+API 架构，前端从 daily_sales 表实时读数。本脚本是
本地日报流水线 → 妙搭 DB 的桥：每次 DELETE 全表 + 重新 INSERT 当前 CSV 全部行。

为什么全表镜像而非增量 UPSERT：表很小（数十行），本地 CSV 是唯一真相源，
全替换彻底幂等、且绕开未知 SQL 方言的 UPSERT/ON CONFLICT 差异。DELETE+INSERT
放在同一条多语句 SQL 里提交，尽量原子。

环境：该应用为单环境库，数据在 online（dev 未初始化），故固定 --env online。
本脚本不读取/打印任何 token 或 secret。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path

import render_dashboard

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_APP_ID = os.environ.get("DASHBOARD_APP_ID", "app_4kdvcqjv319yh")
DEFAULT_CLI = os.environ.get("LARK_APPS_CLI", str(BASE_DIR / "bin" / "lark-cli-apps"))
TABLE = "daily_sales"

# build_rows() 的键 -> daily_sales 列名
COLUMN_MAP = {
    "date": "date",
    "weekday": "weekday",
    "isWeekend": "is_weekend",
    "revenue": "revenue",
    "customers": "customers",
    "avgTicket": "avg_ticket",
    "discountRate": "discount_rate",
    "dineInRatio": "dine_in_ratio",
    "takeawayRatio": "takeaway_ratio",
    "roastDuck": "roast_duck",
    "dine_in_revenue": "dine_in_revenue",
    "takeaway_revenue": "takeaway_revenue",
    "online_revenue": "online_revenue",
    "member_revenue": "member_revenue",
    "member_recharge": "member_recharge",
    "member_consumption": "member_consumption",
    "coupon_amount": "coupon_amount",
}
# 写入时额外补的列
EXTRA_COLUMNS = ["id", "sync_status"]


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    # 字符串：转义单引号
    return "'" + str(value).replace("'", "''") + "'"


def build_sync_sql(rows: list[dict]) -> str:
    columns = list(COLUMN_MAP.values()) + EXTRA_COLUMNS
    col_list = ", ".join(columns)
    values_rows = []
    for r in rows:
        vals = []
        for key, col in COLUMN_MAP.items():
            v = r[key]
            if col == "date":  # 日期补成妙搭存储的 datetime 形态
                v = f"{v}T00:00:00Z"
            vals.append(_sql_literal(v))
        vals.append(_sql_literal(str(uuid.uuid4())))  # id
        vals.append(_sql_literal("synced"))            # sync_status
        values_rows.append("(" + ", ".join(vals) + ")")
    insert = f"INSERT INTO {TABLE} ({col_list}) VALUES\n" + ",\n".join(values_rows) + ";"
    return f"DELETE FROM {TABLE};\n{insert}"


def run_sql(sql: str, app_id: str, cli_bin: str, *, dry_run: bool = False) -> dict:
    cli = Path(cli_bin)
    if not cli.exists():
        raise FileNotFoundError(
            f"未找到支持妙搭(apps)的 lark-cli: {cli_bin}；用 LARK_APPS_CLI 指向 apps 域构建"
        )
    cmd = [
        str(cli), "apps", "+db-execute",
        "--app-id", app_id, "--env", "online", "--as", "user",
        "--sql", sql, "--yes", "--format", "json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in {"http_proxy", "https_proxy", "all_proxy"}}
    env.update({"HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "",
                "http_proxy": "", "https_proxy": "", "all_proxy": ""})
    proc = subprocess.run(cmd, cwd=BASE_DIR, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"妙搭 DB 同步失败 (exit {proc.returncode}): {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw": proc.stdout.strip()}


def sync(store: str, *, app_id: str = DEFAULT_APP_ID, cli_bin: str = DEFAULT_CLI,
         dry_run: bool = False) -> dict:
    rows = render_dashboard.build_rows(store)
    if not rows:
        raise RuntimeError(f"没有 {store} 的数据，无法同步")
    sql = build_sync_sql(rows)
    result = run_sql(sql, app_id, cli_bin, dry_run=dry_run)
    print(f"[db-sync] {'(dry-run) ' if dry_run else ''}已同步 {len(rows)} 天"
          f"（{rows[0]['date']} ~ {rows[-1]['date']}）-> {TABLE}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="把 CSV 同步进妙搭 daily_sales 表（全表镜像）")
    parser.add_argument("--store", default="便宜坊马连道")
    parser.add_argument("--app-id", default=DEFAULT_APP_ID)
    parser.add_argument("--cli", default=DEFAULT_CLI)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-sql", action="store_true", help="只打印将执行的 SQL，不调用")
    args = parser.parse_args()

    if args.print_sql:
        rows = render_dashboard.build_rows(args.store)
        print(build_sync_sql(rows))
        return 0

    result = sync(args.store, app_id=args.app_id, cli_bin=args.cli, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False)[:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
