import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import weekly_auto


def write_history(path: Path, dates: list[str], store: str = "便宜坊马连道") -> None:
    columns = [
        "date",
        "store_name",
        "revenue",
        "customer_count",
        "avg_ticket",
        "month_yoy",
        "discount_rate",
        "dine_in_ratio",
        "takeaway_ratio",
        "roast_duck_sales",
        "warning_level",
        "summary",
        "suggestions",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for i, day in enumerate(dates, 1):
            writer.writerow(
                {
                    "date": day,
                    "store_name": store,
                    "revenue": 10000 + i,
                    "customer_count": 100 + i,
                    "avg_ticket": 100,
                    "month_yoy": -10,
                    "discount_rate": 35,
                    "dine_in_ratio": 80,
                    "takeaway_ratio": 10,
                    "roast_duck_sales": 20 + i,
                    "warning_level": "警示",
                    "summary": f"{day} summary",
                    "suggestions": "",
                }
            )


class WeeklyAutoDashboardTests(unittest.TestCase):
    def test_default_push_weekly_triggers_dashboard_side_effect(self):
        payload = {
            "store_name": "便宜坊马连道",
            "start_date": "2026-05-25",
            "end_date": "2026-05-31",
            "rows": [
                {
                    "_date": date(2026, 5, 25),
                    "date": "2026-05-25",
                    "store_name": "便宜坊马连道",
                    "revenue": "10000",
                    "customer_count": "100",
                    "avg_ticket": "100",
                    "discount_rate": "35",
                    "roast_duck_sales": "20",
                    "warning_level": "警示",
                    "summary": "",
                }
            ],
            "missing_dates": [],
            "date_check_status": "complete",
        }

        with (
            patch.object(weekly_auto.weekly_report, "calc_stats", return_value={
                "store_name": "便宜坊马连道",
                "start_date": "2026-05-25",
                "end_date": "2026-05-31",
                "n_days": 1,
                "year": 2026,
                "week_num": 22,
                "total_revenue": 10000,
                "daily_avg_revenue": 10000,
                "total_customers": 100,
                "avg_ticket": 100,
                "best_day": {"date": "2026-05-25", "revenue": 10000, "summary": ""},
                "worst_day": {"date": "2026-05-25", "revenue": 10000, "summary": ""},
                "avg_discount_rate": 35,
                "high_discount_days": [],
                "duck_trend": [],
                "duck_total_week": 20,
                "duck_daily_avg": 20,
                "warning_counts": {"健康": 0, "警示": 1, "异常": 0},
                "raw_rows": [],
            }),
            patch.object(weekly_auto.weekly_report, "analyze", return_value={
                "trend_summary": "测试",
                "main_issues": [],
                "next_week_suggestions": [],
                "focus_metric": "",
            }),
            patch.object(weekly_auto.weekly_report, "build_card", return_value={"card": True}),
            patch.object(weekly_auto.weekly_report, "push") as push_card,
            patch.object(weekly_auto, "_push_weekly_dashboard") as push_dashboard,
        ):
            weekly_auto._default_push_weekly(payload)

        push_card.assert_called_once()
        push_dashboard.assert_called_once_with(payload)

    def test_push_weekly_dashboard_adds_send_flag_when_app_creds_exist(self):
        payload = {
            "store_name": "便宜坊马连道",
            "start_date": "2026-05-25",
            "end_date": "2026-05-31",
        }
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "render_weekly_dashboard.py"
            script.write_text("print('ok')", encoding="utf-8")
            fake_root = Path(tmp)
            dashboard_path = fake_root / "skills" / "weekly_dashboard"
            dashboard_path.mkdir(parents=True, exist_ok=True)
            (dashboard_path / "render_weekly_dashboard.py").write_text("print('ok')", encoding="utf-8")

            with (
                patch.object(weekly_auto, "ROOT_DIR", fake_root),
                patch.object(weekly_auto.config, "FEISHU_APP_ID", "cli_x"),
                patch.object(weekly_auto.config, "FEISHU_APP_SECRET", "sec_x"),
                patch("subprocess.run") as run_cmd,
            ):
                run_cmd.return_value.returncode = 0
                run_cmd.return_value.stdout = "ok"
                run_cmd.return_value.stderr = ""
                weekly_auto._push_weekly_dashboard(payload)

            called_cmd = run_cmd.call_args.args[0]
            self.assertIn("--send-to-feishu", called_cmd)
            self.assertIn("--store", called_cmd)
            self.assertIn("便宜坊马连道", called_cmd)


if __name__ == "__main__":
    unittest.main()
