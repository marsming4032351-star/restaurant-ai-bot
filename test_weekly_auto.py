import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import weekly_auto
import weekly_report


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


class WeeklyAutoTests(unittest.TestCase):
    def test_saturday_daily_completion_does_not_trigger_weekly_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "store_history.csv"
            state_path = Path(tmp) / "weekly_state.json"
            calls = []
            write_history(history_path, ["2026-05-30"])

            result = weekly_auto.check_and_push(
                "便宜坊马连道",
                "2026-05-30",
                run_date=date(2026, 6, 1),
                history_path=history_path,
                state_path=state_path,
                push_weekly=calls.append,
            )

            self.assertFalse(result["triggered"])
            self.assertEqual(result["reason"], "not_sunday")
            self.assertEqual(calls, [])
            self.assertFalse(state_path.exists())

    def test_monday_run_after_sunday_daily_completion_pushes_previous_week_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "store_history.csv"
            state_path = Path(tmp) / "weekly_state.json"
            days = [str(date(2026, 5, 25) + timedelta(days=i)) for i in range(7)]
            calls = []
            write_history(history_path, days)

            result = weekly_auto.check_and_push(
                "便宜坊马连道",
                "2026-05-31",
                run_date=date(2026, 6, 1),
                history_path=history_path,
                state_path=state_path,
                push_weekly=calls.append,
            )

            self.assertTrue(result["triggered"])
            self.assertEqual(result["start_date"], "2026-05-25")
            self.assertEqual(result["end_date"], "2026-05-31")
            self.assertEqual(result["missing_dates"], [])
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["start_date"], "2026-05-25")
            self.assertEqual(calls[0]["end_date"], "2026-05-31")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("便宜坊马连道:2026-05-25_2026-05-31", state["pushed_periods"])

    def test_sunday_business_date_does_not_trigger_before_monday(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "store_history.csv"
            state_path = Path(tmp) / "weekly_state.json"
            days = [str(date(2026, 5, 25) + timedelta(days=i)) for i in range(7)]
            calls = []
            write_history(history_path, days)

            result = weekly_auto.check_and_push(
                "便宜坊马连道",
                "2026-05-31",
                run_date=date(2026, 5, 31),
                history_path=history_path,
                state_path=state_path,
                push_weekly=calls.append,
            )

            self.assertFalse(result["triggered"])
            self.assertEqual(result["reason"], "run_date_not_monday")
            self.assertEqual(calls, [])
            self.assertFalse(state_path.exists())

    def test_monday_run_does_not_trigger_for_sunday_that_is_not_yesterday(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "store_history.csv"
            state_path = Path(tmp) / "weekly_state.json"
            days = [str(date(2026, 5, 18) + timedelta(days=i)) for i in range(7)]
            calls = []
            write_history(history_path, days)

            result = weekly_auto.check_and_push(
                "便宜坊马连道",
                "2026-05-24",
                run_date=date(2026, 6, 1),
                history_path=history_path,
                state_path=state_path,
                push_weekly=calls.append,
            )

            self.assertFalse(result["triggered"])
            self.assertEqual(result["reason"], "business_date_not_yesterday")
            self.assertEqual(result["expected_business_date"], "2026-05-31")
            self.assertEqual(calls, [])
            self.assertFalse(state_path.exists())

    def test_missing_midweek_day_still_pushes_and_marks_missing_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "store_history.csv"
            state_path = Path(tmp) / "weekly_state.json"
            days = [
                "2026-05-25",
                "2026-05-26",
                "2026-05-27",
                "2026-05-29",
                "2026-05-30",
                "2026-05-31",
            ]
            calls = []
            write_history(history_path, days)

            result = weekly_auto.check_and_push(
                "便宜坊马连道",
                "2026-05-31",
                run_date=date(2026, 6, 1),
                history_path=history_path,
                state_path=state_path,
                push_weekly=calls.append,
            )

            self.assertTrue(result["triggered"])
            self.assertEqual(result["missing_dates"], ["2026-05-28"])
            self.assertEqual(calls[0]["missing_dates"], ["2026-05-28"])

            stats = weekly_report.calc_stats(calls[0]["rows"])
            stats["missing_dates"] = calls[0]["missing_dates"]
            stats["expected_days"] = 7
            card = weekly_report.build_card(
                stats,
                {
                    "trend_summary": "测试趋势",
                    "main_issues": [],
                    "next_week_suggestions": [],
                    "focus_metric": "",
                },
            )
            self.assertIn("本周缺失数据：2026-05-28", json.dumps(card, ensure_ascii=False))

    def test_same_natural_week_is_not_pushed_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "store_history.csv"
            state_path = Path(tmp) / "weekly_state.json"
            days = [str(date(2026, 5, 25) + timedelta(days=i)) for i in range(7)]
            write_history(history_path, days)
            state_path.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "updated_at": "2026-05-31T20:00:00+08:00",
                        "pushed_periods": {
                            "便宜坊马连道:2026-05-25_2026-05-31": {
                                "store_name": "便宜坊马连道",
                                "start_date": "2026-05-25",
                                "end_date": "2026-05-31",
                                "status": "done",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            calls = []

            result = weekly_auto.check_and_push(
                "便宜坊马连道",
                "2026-05-31",
                run_date=date(2026, 6, 1),
                history_path=history_path,
                state_path=state_path,
                push_weekly=calls.append,
            )

            self.assertFalse(result["triggered"])
            self.assertEqual(result["reason"], "already_pushed")
            self.assertEqual(calls, [])

    def test_sunday_with_no_store_data_does_not_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "store_history.csv"
            state_path = Path(tmp) / "weekly_state.json"
            write_history(history_path, ["2026-05-31"], store="其他门店")
            calls = []

            result = weekly_auto.check_and_push(
                "便宜坊马连道",
                "2026-05-31",
                run_date=date(2026, 6, 1),
                history_path=history_path,
                state_path=state_path,
                push_weekly=calls.append,
            )

            self.assertFalse(result["triggered"])
            self.assertEqual(result["reason"], "no_data")
            self.assertEqual(
                result["missing_dates"],
                [
                    "2026-05-25",
                    "2026-05-26",
                    "2026-05-27",
                    "2026-05-28",
                    "2026-05-29",
                    "2026-05-30",
                    "2026-05-31",
                ],
            )
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
