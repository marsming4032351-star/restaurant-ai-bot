import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path("skills/weekly_dashboard/render_weekly_dashboard.py")


def load_dashboard_module():
    spec = importlib.util.spec_from_file_location("weekly_dashboard", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_history(path: Path) -> None:
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
        for i, day in enumerate(range(25, 32), 1):
            writer.writerow(
                {
                    "date": f"2026-05-{day:02d}",
                    "store_name": "便宜坊马连道",
                    "revenue": 10000 + i * 1000,
                    "customer_count": 100 + i * 10,
                    "avg_ticket": 100 + i,
                    "month_yoy": -10,
                    "discount_rate": 35,
                    "dine_in_ratio": 80,
                    "takeaway_ratio": 10,
                    "roast_duck_sales": 20 + i,
                    "warning_level": "警示",
                    "summary": f"2026-05-{day:02d} summary",
                    "suggestions": "",
                }
            )


def write_report(path: Path) -> None:
    payload = {
        "daily": {
            "meta": {
                "date": "2026-05-31",
                "weekday": "Sunday",
                "store_id": "MLD",
                "store_name": "便宜坊马连道",
            },
            "revenue": {
                "revenue_today": 51910.05,
                "revenue_month_to_date": 1051202.74,
                "revenue_today_before_discount": 88706.72,
                "revenue_mtd_before_discount": 1758410.06,
                "revenue_same_period_last_year": 1310715.71,
                "revenue_yoy_delta": -259512.97,
                "dine_in_revenue": 43472.38,
                "dine_in_takeaway_revenue": 2021.0,
                "online_takeaway_revenue": 6416.67,
                "member_recharge_today": 22000.0,
                "member_recharge_mtd": 447237.81,
                "free_amount": 6.0,
                "purchase_amount": 16649.92,
            },
            "member_consumption": {
                "member_revenue": 32806.0,
                "member_revenue_ratio": 72.11,
                "full_price_revenue": 2232.0,
                "full_price_ratio": 4.91,
                "discount_revenue": 10455.38,
                "discount_ratio": 22.98,
            },
            "traffic": {
                "customer_count": 371.0,
                "avg_check": 117.1762264,
                "rebate_coupon_issued": 6.0,
                "rebate_coupon_redeemed": 0,
                "coupon_revenue": 0,
                "cash_coupon_redeemed": 0.0,
                "cash_coupon_revenue": 0.0,
            },
            "dishes_by_category": {
                "烤鸭类": {
                    "roasted_duck_dine_in": 58.0,
                    "mini_duck": 12.0,
                    "roasted_duck_online": 32.0,
                    "spiced_duck_rack": 27.0,
                    "sesame_cake": 191.0,
                    "duck_sauce": 284.0,
                    "sesame_cake_ratio": 67.25,
                    "duck_rack_ratio": 62.79,
                },
                "套餐类": {
                    "set_meal_3p": 0.0,
                    "set_meal_6p": 1.0,
                    "set_meal_8p": 0.0,
                    "set_meal_10p": 1.0,
                    "set_meal_12p": 1.0,
                    "crab_set_meal": 3.0,
                    "pigeon": 33.0,
                },
                "鱼类_牛掌": {
                    "mandarin_fish": 5.0,
                    "fish_total": 9.0,
                    "sea_cucumber_beef_paw": 8.0,
                },
                "位吃_甜品": {
                    "dessert": 0.0,
                    "per_seat_dish": 135.0,
                    "sweet": 22.0,
                    "house_drink": 27.0,
                },
                "精酿": {"craft_beer": 0.0},
            },
            "derived": {
                "dine_in_share": 0.8375,
                "online_share": 0.1236,
                "takeaway_share": 0.0389,
                "discount_rate": 0.4148,
                "effective_price_ratio": 0.5852,
                "yoy_pct": -0.198,
                "duck_total": 102.0,
                "set_meal_total": 39.0,
            },
            "report": {
                "health_level": "异常",
                "headline": "月累同比跌19.8%亏26万，客流回升但折扣率偏高",
                "diagnosis": {},
                "suggestions": [],
                "watch_tomorrow": "",
            },
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class WeeklyFieldEnhancerTests(unittest.TestCase):
    def test_load_weekly_enriched_fields_prefers_report_json_and_keeps_missing_none(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            output_dir = base / "output"
            write_history(history_path)
            write_report(output_dir / "report_MLD_2026-05-31.json")

            enriched = dashboard.load_weekly_enriched_fields(
                "便宜坊马连道",
                "2026-05-25",
                "2026-05-31",
                history_path=history_path,
                output_dir=output_dir,
            )

            self.assertIn("revenue", enriched["field_map_sections"])
            self.assertIn("dish_categories", enriched["field_map_sections"])
            self.assertEqual(enriched["available_reports"], 1)
            self.assertEqual(enriched["revenue_total"], 132910.05)
            self.assertEqual(enriched["member_recharge"], 22000.0)
            self.assertEqual(enriched["duck_total"], 102.0)
            self.assertIsNone(enriched["child_card_issue"])
            self.assertIsNone(enriched["child_card_total"])
            self.assertEqual(len(enriched["daily_series"]), 7)
            self.assertTrue(enriched["daily_series"][-1]["has_report"])
            self.assertFalse(enriched["daily_series"][0]["has_report"])
            self.assertEqual(enriched["daily_series"][-1]["revenue"], 51910.05)
            self.assertEqual(enriched["daily_series"][0]["revenue"], 11000.0)

    def test_zero_values_are_preserved_as_zero_not_missing(self):
        dashboard = load_dashboard_module()
        row = {"value": 0, "text": "0"}
        self.assertEqual(dashboard._value_or_none(row["value"]), 0.0)
        self.assertEqual(dashboard._value_or_none(row["text"]), 0.0)
        self.assertIsNone(dashboard._value_or_none(""))
        self.assertIsNone(dashboard._value_or_none(None))


if __name__ == "__main__":
    unittest.main()
