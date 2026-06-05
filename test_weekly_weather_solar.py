"""周报天气 / 节气增强层测试。

覆盖：
1. report_*.json 带 daily.context → 看板读取到天气 / 节气
2. report_*.json 无 context → 不报错，降级为「暂无 / 弱参考」
3. 节气信息进入周报文字卡片
4. 天气缺失不影响周报生成
另：build_weather_solar_observation 的确定性行为（节气来自权威表）。
"""
from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import weekly_report


MODULE_PATH = Path("skills/weekly_dashboard/render_weekly_dashboard.py")


def load_dashboard_module():
    spec = importlib.util.spec_from_file_location("weekly_dashboard_ws", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HISTORY_COLUMNS = [
    "date", "store_name", "revenue", "customer_count", "avg_ticket",
    "month_yoy", "discount_rate", "dine_in_ratio", "takeaway_ratio",
    "roast_duck_sales", "warning_level", "summary", "suggestions",
]


def write_history(path: Path, dates: list[str], store: str = "便宜坊马连道") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        writer.writeheader()
        for i, day in enumerate(dates, 1):
            writer.writerow({
                "date": day, "store_name": store, "revenue": 10000 + i * 1000,
                "customer_count": 90 + i * 10, "avg_ticket": 100 + i,
                "month_yoy": -10, "discount_rate": 35 + i, "dine_in_ratio": 80,
                "takeaway_ratio": 10, "roast_duck_sales": 20 + i,
                "warning_level": "健康", "summary": f"{day} summary", "suggestions": "",
            })


def write_report(output_dir: Path, day: str, context: dict | None,
                 store: str = "便宜坊马连道") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    daily = {"meta": {"date": day, "store_name": store},
             "revenue": {"revenue_today": 12345}}
    if context is not None:
        daily["context"] = context
    payload = {"daily": daily, "report": {}}
    (output_dir / f"report_MLD_{day}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class BuildObservationTests(unittest.TestCase):
    def test_solar_term_day_in_week_is_detected(self):
        # 2026 芒种 = 2026-06-05，落在 06-01 ~ 06-07 周内
        obs = weekly_report.build_weather_solar_observation("2026-06-01", "2026-06-07")
        self.assertEqual(obs["solar_term_status"], "ok")
        self.assertIn("芒种", obs["solar_term_text"])
        self.assertTrue(obs["hints"])  # 芒种应有经营提示
        self.assertTrue(any("芒种" in line for line in obs["lines"]))

    def test_week_without_term_day_uses_current_term(self):
        # 05-25 ~ 05-31 无节气日，应落在当前所处节气（小满）
        obs = weekly_report.build_weather_solar_observation("2026-05-25", "2026-05-31")
        self.assertEqual(obs["solar_term_status"], "ok")
        self.assertIn("无关键节气", obs["solar_term_text"])

    def test_missing_weather_degrades_without_fabrication(self):
        obs = weekly_report.build_weather_solar_observation("2026-06-01", "2026-06-07")
        self.assertFalse(obs["weather_available"])
        self.assertIn("天气数据不完整", obs["weather_text"])

    def test_present_weather_is_used(self):
        obs = weekly_report.build_weather_solar_observation(
            "2026-06-01", "2026-06-07", weather_text="多云 22~30℃")
        self.assertTrue(obs["weather_available"])
        self.assertEqual(obs["weather_text"], "多云 22~30℃")

    def test_uncovered_year_returns_no_data(self):
        obs = weekly_report.build_weather_solar_observation("1999-06-01", "1999-06-07")
        self.assertEqual(obs["solar_term_status"], "no_data")
        self.assertIn("暂无", obs["solar_term_text"])


class WeeklyCardTextTests(unittest.TestCase):
    def test_build_card_renders_weather_solar_paragraph(self):
        stats = {
            "store_name": "便宜坊马连道", "week_num": 23, "year": 2026,
            "start_date": "2026-06-01", "end_date": "2026-06-07", "n_days": 7,
            "total_revenue": 70000, "daily_avg_revenue": 10000,
            "total_customers": 700, "avg_ticket": 100,
            "best_day": {"date": "2026-06-05", "revenue": 12000, "summary": "好"},
            "worst_day": {"date": "2026-06-01", "revenue": 9000, "summary": "弱"},
            "avg_discount_rate": 35, "high_discount_days": [],
            "duck_trend": ["06/01 —20只"], "duck_total_week": 140, "duck_daily_avg": 20,
            "warning_counts": {"健康": 7, "警示": 0, "异常": 0},
        }
        observation = weekly_report.build_weather_solar_observation(
            "2026-06-01", "2026-06-07")
        analysis = {"main_issues": [], "next_week_suggestions": [],
                    "trend_summary": "平稳", "focus_metric": "客流",
                    "weather_solar_summary": observation}
        card = weekly_report.build_card(stats, analysis)
        blob = json.dumps(card, ensure_ascii=False)
        self.assertIn("天气 / 节气观察", blob)
        self.assertIn("芒种", blob)

    def test_build_card_without_weather_solar_still_works(self):
        stats = {
            "store_name": "便宜坊马连道", "week_num": 23, "year": 2026,
            "start_date": "2026-06-01", "end_date": "2026-06-07", "n_days": 7,
            "total_revenue": 70000, "daily_avg_revenue": 10000,
            "total_customers": 700, "avg_ticket": 100,
            "best_day": {"date": "2026-06-05", "revenue": 12000, "summary": "好"},
            "worst_day": {"date": "2026-06-01", "revenue": 9000, "summary": "弱"},
            "avg_discount_rate": 35, "high_discount_days": [],
            "duck_trend": ["06/01 —20只"], "duck_total_week": 140, "duck_daily_avg": 20,
            "warning_counts": {"健康": 7, "警示": 0, "异常": 0},
        }
        analysis = {"main_issues": [], "next_week_suggestions": [],
                    "trend_summary": "平稳", "focus_metric": "客流"}
        card = weekly_report.build_card(stats, analysis)  # 不应抛错
        self.assertNotIn("天气 / 节气观察", json.dumps(card, ensure_ascii=False))


class DashboardEnrichmentTests(unittest.TestCase):
    def _dates(self) -> list[str]:
        return [f"2026-06-0{day}" for day in range(1, 8)]

    def test_dashboard_reads_weather_and_solar_from_report_context(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            output_dir = base / "output"
            dates = self._dates()
            write_history(history_path, dates)
            # 06-05 带完整运营上下文（业务日天气有值 + 芒种）
            write_report(output_dir, "2026-06-05", {
                "weather": {"weather_for_business_date": "多云 22~30℃",
                            "weather_status": "ok"},
                "solar_term": {"solar_term_today": "芒种",
                               "current_solar_term": "芒种"},
            })

            enriched = dashboard.load_weekly_enriched_fields(
                "便宜坊马连道", "2026-06-01", "2026-06-07",
                history_path=history_path, output_dir=output_dir)

            self.assertIn("weather_solar", enriched)
            self.assertIn("芒种", enriched["solar_term_text"])
            self.assertEqual(enriched["weather_text"], "多云 22~30℃")

            context = dashboard.weekly_context(
                "便宜坊马连道", "2026-06-01", "2026-06-07", history_path)
            diag_blob = "".join(context["diagnosis"])
            self.assertIn("🌤️", diag_blob)
            self.assertIn("芒种", diag_blob)

    def test_dashboard_without_context_degrades_gracefully(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            output_dir = base / "output"
            dates = self._dates()
            write_history(history_path, dates)
            # report 无 context
            write_report(output_dir, "2026-06-05", None)

            enriched = dashboard.load_weekly_enriched_fields(
                "便宜坊马连道", "2026-06-01", "2026-06-07",
                history_path=history_path, output_dir=output_dir)

            # 节气仍可确定性派生；天气降级为弱参考，不伪造
            self.assertIn("芒种", enriched["solar_term_text"])
            self.assertIn("天气数据不完整", enriched["weather_text"])

    def test_dashboard_with_no_reports_at_all_does_not_crash(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            write_history(history_path, self._dates())
            enriched = dashboard.load_weekly_enriched_fields(
                "便宜坊马连道", "2026-06-01", "2026-06-07",
                history_path=history_path, output_dir=base / "output")
            self.assertIn("weather_solar", enriched)
            self.assertFalse(enriched["weather_solar"]["weather_available"])


if __name__ == "__main__":
    unittest.main()
