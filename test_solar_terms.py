"""节气确定性表 + 上下文的锚点测试。

节气是确定性天文事件，本测试用权威发布日期做硬断言：
- 任何对 data/solar_terms_cn.json 的误改都会让测试大声失败（绝不静默漂移）。
- 表外年份必须诚实降级为 no_data，绝不伪造。
"""

import unittest
from datetime import date

import solar_terms


class TestSolarTermTable(unittest.TestCase):
    def test_authoritative_anchor_dates_2026(self):
        table = solar_terms.load_solar_terms()
        y = table["2026"]
        # 紫金山天文台权威发布日期
        self.assertEqual(y["立春"], "2026-02-04")
        self.assertEqual(y["春分"], "2026-03-20")
        self.assertEqual(y["芒种"], "2026-06-05")
        self.assertEqual(y["夏至"], "2026-06-21")
        self.assertEqual(y["秋分"], "2026-09-23")
        self.assertEqual(y["冬至"], "2026-12-22")

    def test_authoritative_anchor_dates_2027(self):
        table = solar_terms.load_solar_terms()
        y = table["2027"]
        self.assertEqual(y["立春"], "2027-02-04")
        self.assertEqual(y["夏至"], "2027-06-21")
        self.assertEqual(y["冬至"], "2027-12-22")

    def test_each_year_has_24_terms(self):
        table = solar_terms.load_solar_terms()
        for yr in ("2026", "2027"):
            self.assertEqual(len(table[yr]), 24, f"{yr} 必须恰好 24 个节气")


class TestSolarTermContext(unittest.TestCase):
    def test_on_term_day(self):
        ctx = solar_terms.solar_term_context(date(2026, 6, 5))
        self.assertEqual(ctx["solar_term_status"], "ok")
        self.assertTrue(ctx["is_solar_term_day"])
        self.assertEqual(ctx["solar_term_today"], "芒种")
        self.assertEqual(ctx["current_solar_term"], "芒种")
        self.assertEqual(ctx["days_into_current_term"], 0)

    def test_between_terms(self):
        ctx = solar_terms.solar_term_context(date(2026, 6, 10))
        self.assertEqual(ctx["solar_term_status"], "ok")
        self.assertFalse(ctx["is_solar_term_day"])
        self.assertEqual(ctx["current_solar_term"], "芒种")
        self.assertEqual(ctx["days_into_current_term"], 5)
        self.assertEqual(ctx["next_solar_term"], "夏至")
        self.assertEqual(ctx["days_to_next_term"], 11)

    def test_year_not_covered_degrades_to_no_data(self):
        ctx = solar_terms.solar_term_context(date(2030, 6, 5))
        self.assertEqual(ctx["solar_term_status"], "no_data")
        self.assertIsNone(ctx["current_solar_term"])
        self.assertIsNone(ctx["solar_term_today"])


if __name__ == "__main__":
    unittest.main()
