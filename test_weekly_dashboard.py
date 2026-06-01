import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path("skills/weekly_dashboard/render_weekly_dashboard.py")


def load_dashboard_module():
    spec = importlib.util.spec_from_file_location("weekly_dashboard", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
                    "revenue": 10000 + i * 1000,
                    "customer_count": 90 + i * 10,
                    "avg_ticket": 100 + i,
                    "month_yoy": -10,
                    "discount_rate": 35 + i,
                    "dine_in_ratio": 80,
                    "takeaway_ratio": 10,
                    "roast_duck_sales": 20 + i,
                    "warning_level": "警示" if i % 2 else "健康",
                    "summary": f"{day} summary",
                    "suggestions": "",
                }
            )


class WeeklyDashboardTests(unittest.TestCase):
    def test_generates_html_and_png_for_explicit_week_range(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            output_dir = base / "output"
            dates = [f"2026-05-{day:02d}" for day in range(25, 32)]
            write_history(history_path, dates)

            result = dashboard.render_dashboard(
                store="便宜坊马连道",
                start_date="2026-05-25",
                end_date="2026-05-31",
                history_path=history_path,
                output_dir=output_dir,
            )

            html = Path(result["html_path"])
            png = Path(result["png_path"])
            self.assertTrue(html.exists())
            self.assertTrue(png.exists())
            self.assertGreater(png.stat().st_size, 0)
            html_text = html.read_text(encoding="utf-8")
            self.assertIn("Apache ECharts", html_text)
            self.assertIn("便宜坊马连道 · 2026-05-25 至 2026-05-31 周报经营看板", html_text)
            self.assertEqual(result["date_check_status"], "complete")
            self.assertEqual(result["missing_dates"], [])

    def test_missing_date_is_rendered_without_fabricating_data(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            output_dir = base / "output"
            dates = ["2026-05-25", "2026-05-26", "2026-05-27", "2026-05-29", "2026-05-30", "2026-05-31"]
            write_history(history_path, dates)

            result = dashboard.render_dashboard(
                store="便宜坊马连道",
                start_date="2026-05-25",
                end_date="2026-05-31",
                history_path=history_path,
                output_dir=output_dir,
            )

            self.assertEqual(result["missing_dates"], ["2026-05-28"])
            html_text = Path(result["html_path"]).read_text(encoding="utf-8")
            self.assertIn("缺失日期提示：2026-05-28", html_text)
            self.assertNotIn("2026-05-28 summary", html_text)

    def test_strict_mode_blocks_missing_dates(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            output_dir = base / "output"
            write_history(history_path, ["2026-05-25", "2026-05-26", "2026-05-31"])

            with self.assertRaisesRegex(ValueError, "缺失日期"):
                dashboard.render_dashboard(
                    store="便宜坊马连道",
                    start_date="2026-05-25",
                    end_date="2026-05-31",
                    history_path=history_path,
                    output_dir=output_dir,
                    strict_weekly_date_check=True,
                )

            self.assertFalse(output_dir.exists())

    def test_requires_explicit_week_range_and_never_uses_system_date(self):
        dashboard = load_dashboard_module()
        with self.assertRaisesRegex(ValueError, "必须显式传入"):
            dashboard.render_dashboard(store="便宜坊马连道", start_date=None, end_date="2026-05-31")
        with self.assertRaisesRegex(ValueError, "必须显式传入"):
            dashboard.render_dashboard(store="便宜坊马连道", start_date="2026-05-25", end_date=None)


if __name__ == "__main__":
    unittest.main()
