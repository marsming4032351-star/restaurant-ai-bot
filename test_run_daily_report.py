import csv
import json
import tempfile
import unittest
from pathlib import Path

import run_daily_report as R


class RunDailyReportTests(unittest.TestCase):
    def test_default_input_dir_is_maliandao_desktop_folder(self):
        expected = Path("/Users/ming/Desktop/临时/马连道")

        self.assertEqual(R.INPUT_DIR, expected)

    def test_extract_json_from_markdown_block(self):
        text = '结果如下：\n```json\n{"本日收入": 123.45, "来客数": 9}\n```'

        self.assertEqual(R.extract_json_object(text), {"本日收入": 123.45, "来客数": 9})

    def test_pipeline_log_upgrade_and_success_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline_log.csv"
            path.write_text(
                "date,store_name,feishu_pushed,status,notes\n"
                "2026-05-28,便宜坊马连道,true,done,\n",
                encoding="utf-8",
            )

            R.append_pipeline_log(
                path,
                {
                    "date": "2026-05-29",
                    "store_name": "便宜坊马连道",
                    "feishu_pushed": "true",
                    "feishu_push_success": "true",
                    "status": "done",
                    "notes": "",
                },
            )

            with path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertIn("feishu_push_success", rows[0])
            self.assertIn("error_message", rows[0])
            self.assertEqual(rows[-1]["date"], "2026-05-29")
            self.assertEqual(rows[-1]["feishu_push_success"], "true")
            self.assertEqual(rows[-1]["status"], "done")

    def test_is_already_pushed_reads_new_or_old_success_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline_log.csv"
            path.write_text(
                "date,store_name,feishu_pushed,feishu_push_success,status\n"
                "2026-05-29,便宜坊马连道,true,,done\n"
                "2026-05-30,便宜坊马连道,false,true,done\n",
                encoding="utf-8",
            )

            self.assertTrue(R.is_already_pushed(path, "2026-05-29", "便宜坊马连道"))
            self.assertTrue(R.is_already_pushed(path, "2026-05-30", "便宜坊马连道"))
            self.assertFalse(R.is_already_pushed(path, "2026-05-31", "便宜坊马连道"))

    def test_write_pipeline_state_advances_target_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipeline_state.json"

            R.write_pipeline_state(path, "便宜坊马连道", "2026-05-29", "2026-05-30T10:00:00+08:00")

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["current_target_date"], "2026-05-30")
            self.assertEqual(data["last_completed_date"], "2026-05-29")
            self.assertTrue(data["last_feishu_pushed"])
            self.assertEqual(data["updated_by"], "codex")

    def test_store_history_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store_history.csv"
            path.write_text(
                "date,store_name,revenue\n"
                "2026-05-29,便宜坊马连道,35447.22\n",
                encoding="utf-8",
            )

            self.assertTrue(R.store_history_has_row(path, "2026-05-29", "便宜坊马连道"))
            self.assertFalse(R.store_history_has_row(path, "2026-05-30", "便宜坊马连道"))


if __name__ == "__main__":
    unittest.main()
