"""Import structured daily JSON rows into data/store_history.csv.

The importer is intentionally small and conservative:
- dry-run validates data without writing
- duplicate date + store rows stop the import
- only the canonical store_history.csv columns are written
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import history


DAILY_DIR = Path(__file__).parent / "daily"
REQUIRED_FIELDS = history.COLUMNS


def _load_daily(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        row = json.load(f)
    if "store_history_row" in row:
        row = row["store_history_row"]
    return row


def _validate(row: dict) -> list[str]:
    errors = []
    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        errors.append(f"missing fields: {missing}")

    empty = [field for field in REQUIRED_FIELDS if str(row.get(field, "")).strip() == ""]
    if empty:
        errors.append(f"empty fields: {empty}")

    numeric_fields = [
        "revenue",
        "customer_count",
        "avg_ticket",
        "month_yoy",
        "discount_rate",
        "dine_in_ratio",
        "takeaway_ratio",
        "roast_duck_sales",
    ]
    for field in numeric_fields:
        try:
            float(row.get(field, ""))
        except (TypeError, ValueError):
            errors.append(f"invalid numeric field: {field}={row.get(field)!r}")

    if row.get("warning_level") not in {"健康", "警示", "异常"}:
        errors.append(f"invalid warning_level: {row.get('warning_level')!r}")

    return errors


def _read_existing() -> list[dict]:
    return history._read_existing()


def _has_duplicate(row: dict, existing: list[dict]) -> bool:
    return any(
        r.get("date") == row.get("date") and r.get("store_name") == row.get("store_name")
        for r in existing
    )


def _append(row: dict) -> None:
    history.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    need_header = not history.HISTORY_FILE.exists() or history.HISTORY_FILE.stat().st_size == 0
    with open(history.HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=history.COLUMNS, extrasaction="ignore")
        if need_header:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in history.COLUMNS})


def main() -> int:
    parser = argparse.ArgumentParser(description="Import daily JSON into store_history.csv")
    parser.add_argument(
        "--file",
        default=str(DAILY_DIR / "2026-05-27.json"),
        help="daily JSON file path",
    )
    parser.add_argument("--dry-run", action="store_true", help="validate only; do not write")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"[import] missing file: {path}", file=sys.stderr)
        return 1

    row = _load_daily(path)
    errors = _validate(row)
    if errors:
        print("[import] validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    existing = _read_existing()
    if _has_duplicate(row, existing):
        print(
            f"[import] duplicate exists: {row['store_name']} · {row['date']}; import stopped",
            file=sys.stderr,
        )
        return 2

    print(f"[import] valid row: {row['store_name']} · {row['date']}")
    print(
        "[import] "
        f"revenue={row['revenue']} customers={row['customer_count']} "
        f"avg_ticket={row['avg_ticket']} warning={row['warning_level']}"
    )

    if args.dry_run:
        print("[import] dry-run only; no write performed")
        return 0

    _append(row)
    print(f"[import] appended to {history.HISTORY_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
