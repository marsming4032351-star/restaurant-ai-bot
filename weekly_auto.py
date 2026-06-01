"""Automatic weekly report trigger after a successful Sunday daily report."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import config
import weekly_report


ROOT_DIR = Path(__file__).resolve().parent
WEEKLY_STATE = config.DATA_DIR / "weekly_state.json"


def now_iso() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).replace(microsecond=0).isoformat()


def today_in_business_timezone() -> date:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).date()


def load_weekly_state(path: Path = WEEKLY_STATE) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {"version": "1.0", "updated_at": "", "pushed_periods": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", "1.0")
    data.setdefault("updated_at", "")
    data.setdefault("pushed_periods", {})
    return data


def save_weekly_state(state: dict, path: Path = WEEKLY_STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def natural_week_range(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def expected_dates(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def period_key(store: str, start: date, end: date) -> str:
    return f"{store}:{start}_{end}"


def _default_push_weekly(payload: dict) -> None:
    stats = weekly_report.calc_stats(payload["rows"])
    stats["period_start_date"] = payload["start_date"]
    stats["period_end_date"] = payload["end_date"]
    stats["expected_days"] = 7
    stats["missing_dates"] = payload["missing_dates"]
    stats["date_check_status"] = payload["date_check_status"]
    analysis = weekly_report.analyze(stats)
    card = weekly_report.build_card(stats, analysis)
    weekly_report.push(card)
    _push_weekly_dashboard(payload)


def _push_weekly_dashboard(payload: dict) -> None:
    dashboard_script = ROOT_DIR / "skills" / "weekly_dashboard" / "render_weekly_dashboard.py"
    if not dashboard_script.exists():
        print(f"[weekly-auto] 周报看板脚本不存在，跳过增强看板: {dashboard_script}")
        return

    cmd = [
        sys.executable,
        str(dashboard_script),
        "--store",
        payload["store_name"],
        "--start-date",
        payload["start_date"],
        "--end-date",
        payload["end_date"],
    ]
    if config.FEISHU_APP_ID and config.FEISHU_APP_SECRET:
        cmd.append("--send-to-feishu")

    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "周报看板生成失败")
        print(f"[weekly-auto] 增强看板已生成: {payload['start_date']}～{payload['end_date']}")
        if config.FEISHU_APP_ID and config.FEISHU_APP_SECRET:
            print(f"[weekly-auto] 增强看板已尝试发送到飞书: {payload['start_date']}～{payload['end_date']}")
    except Exception as exc:
        print(f"[weekly-auto] 增强看板失败: {type(exc).__name__}: {exc}")


def check_and_push(
    store: str,
    completed_date: str,
    *,
    run_date: date | None = None,
    history_path: Path | None = None,
    state_path: Path = WEEKLY_STATE,
    push_weekly: Callable[[dict], None] | None = None,
    strict_weekly_date_check: bool | None = None,
) -> dict:
    """Push last week's report after Monday successfully sends Sunday's daily report.

    The weekly report is based on existing rows in store_history.csv. Missing
    dates are reported, never invented.
    """
    trigger_date = date.fromisoformat(completed_date)
    if trigger_date.weekday() != 6:
        return {
            "triggered": False,
            "reason": "not_sunday",
            "trigger_date": completed_date,
        }

    actual_run_date = run_date or today_in_business_timezone()
    if actual_run_date.weekday() != 0:
        return {
            "triggered": False,
            "reason": "run_date_not_monday",
            "run_date": str(actual_run_date),
            "trigger_date": completed_date,
        }

    expected_business_date = actual_run_date - timedelta(days=1)
    if trigger_date != expected_business_date:
        return {
            "triggered": False,
            "reason": "business_date_not_yesterday",
            "run_date": str(actual_run_date),
            "trigger_date": completed_date,
            "expected_business_date": str(expected_business_date),
        }

    start, end = natural_week_range(trigger_date)
    key = period_key(store, start, end)
    state = load_weekly_state(state_path)
    if key in state.get("pushed_periods", {}):
        return {
            "triggered": False,
            "reason": "already_pushed",
            "period_key": key,
            "start_date": str(start),
            "end_date": str(end),
            "trigger_date": completed_date,
        }

    original_history_file = weekly_report.HISTORY_FILE
    if history_path is not None:
        weekly_report.HISTORY_FILE = history_path
    try:
        rows = weekly_report.load_rows(store, start, end)
    finally:
        weekly_report.HISTORY_FILE = original_history_file

    expected = expected_dates(start, end)
    found = {row["_date"] for row in rows}
    missing = [str(day) for day in expected if day not in found]
    strict = config.STRICT_WEEKLY_DATE_CHECK if strict_weekly_date_check is None else strict_weekly_date_check
    if not rows:
        return {
            "triggered": False,
            "reason": "no_data",
            "period_key": key,
            "start_date": str(start),
            "end_date": str(end),
            "trigger_date": completed_date,
            "missing_dates": missing,
            "date_check_status": "missing_all_dates",
        }
    if missing and strict:
        return {
            "triggered": False,
            "reason": "missing_dates_strict",
            "period_key": key,
            "start_date": str(start),
            "end_date": str(end),
            "trigger_date": completed_date,
            "missing_dates": missing,
            "date_check_status": "missing_dates_blocked",
        }

    payload = {
        "store_name": store,
        "start_date": str(start),
        "end_date": str(end),
        "trigger_date": completed_date,
        "rows": rows,
        "missing_dates": missing,
        "date_check_status": "missing_dates_allowed" if missing else "complete",
    }
    (push_weekly or _default_push_weekly)(payload)

    pushed_at = now_iso()
    state["updated_at"] = pushed_at
    state.setdefault("pushed_periods", {})[key] = {
        "store_name": store,
        "start_date": str(start),
        "end_date": str(end),
        "trigger_date": completed_date,
        "pushed_at": pushed_at,
        "days_found": len(rows),
        "missing_dates": missing,
        "date_check_status": payload["date_check_status"],
        "source": "store_history.csv",
        "status": "done",
    }
    save_weekly_state(state, state_path)
    return {
        "triggered": True,
        "status": "pushed",
        "period_key": key,
        "start_date": str(start),
        "end_date": str(end),
        "trigger_date": completed_date,
        "days_found": len(rows),
        "missing_dates": missing,
        "date_check_status": payload["date_check_status"],
    }
