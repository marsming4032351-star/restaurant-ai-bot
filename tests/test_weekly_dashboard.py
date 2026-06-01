import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


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
    def test_dashboard_renders_new_sections(self):
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
            html_text = html.read_text(encoding="utf-8")
            self.assertIn("每日营业额 + 客流双轴趋势", html_text)
            self.assertIn("会员与活动", html_text)
            self.assertIn("关键品类销量 TOP", html_text)
            self.assertIn("烤鸭专项分析", html_text)
            self.assertIn("本周经营诊断", html_text)

    def test_missing_date_is_still_reported(self):
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

    def test_png_width_is_fixed_and_height_expands_for_long_diagnosis(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            history_path = base / "store_history.csv"
            write_history(history_path, [f"2026-05-{day:02d}" for day in range(25, 32)])

            short_output = base / "short"
            short_result = dashboard.render_dashboard(
                store="便宜坊马连道",
                start_date="2026-05-25",
                end_date="2026-05-31",
                history_path=history_path,
                output_dir=short_output,
            )
            with Image.open(short_result["png_path"]) as img:
                short_size = img.size

            long_output = base / "long"
            long_piece = "这是一段非常长的经营诊断文本，用来验证长图会随着底部内容自动增高，确保中文换行后仍然完整显示且不会裁切。"
            long_lines = [
                long_piece * 4,
                long_piece * 4,
                long_piece * 4,
                long_piece * 4,
                long_piece * 4,
            ]
            with patch.object(dashboard, "build_weekly_diagnosis", return_value=long_lines):
                long_result = dashboard.render_dashboard(
                    store="便宜坊马连道",
                    start_date="2026-05-25",
                    end_date="2026-05-31",
                    history_path=history_path,
                    output_dir=long_output,
                )
            with Image.open(long_result["png_path"]) as img:
                long_size = img.size

            self.assertEqual(short_size[0], 1920)
            self.assertEqual(long_size[0], 1920)
            self.assertGreaterEqual(short_size[1], 1080)
            self.assertGreater(long_size[1], short_size[1])

    def test_send_to_feishu_uses_existing_helpers(self):
        dashboard = load_dashboard_module()
        with tempfile.TemporaryDirectory() as tmp:
            png_path = Path(tmp) / "dashboard.png"
            png_path.write_bytes(b"png-bytes")
            with (
                patch("feishu_bot._has_app_creds", return_value=True),
                patch("feishu_bot._upload_image", return_value="img_v2_123") as upload_image,
                patch("feishu_bot.send_text") as send_text,
                patch("feishu_bot._send_image_key") as send_image_key,
            ):
                dashboard.send_dashboard_to_feishu(
                    png_path,
                    "便宜坊马连道",
                    "2026-05-25",
                    "2026-05-31",
                )

            upload_image.assert_called_once_with(png_path)
            send_text.assert_called_once_with(
                "便宜坊马连道｜2026-05-25 至 2026-05-31 周报可视化看板\n"
                "本看板基于已校验周报数据生成，业务日期来自图片表头日期。",
                ensure_keyword=False,
            )
            send_image_key.assert_called_once_with("img_v2_123")


if __name__ == "__main__":
    unittest.main()
