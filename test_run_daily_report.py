import csv
import json
import tempfile
import unittest
from pathlib import Path

import run_daily_report as R
import watch_daily_folder as W


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

    def test_watch_state_skips_same_file_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "daily.png"
            image.write_bytes(b"abc")
            state_path = Path(tmp) / "watch_state.json"

            signature = W.file_signature(image)
            self.assertTrue(W.should_process({}, image, signature))

            state = {}
            W.mark_processed(state, image, signature, "2026-05-30T10:00:00+08:00")
            self.assertFalse(W.should_process(state, image, signature))

    def test_find_candidate_images_sorted_by_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            old = folder / "old.png"
            new = folder / "new.webp"
            ignored = folder / "note.txt"
            old.write_bytes(b"old")
            new.write_bytes(b"new")
            ignored.write_text("ignore", encoding="utf-8")

            images = W.find_candidate_images(folder)

            self.assertEqual(images[-1], new)
            self.assertNotIn(ignored, images)

    def test_launchd_scripts_define_expected_service_contract(self):
        install = Path("scripts/install_watcher_launchd.sh").read_text(encoding="utf-8")
        uninstall = Path("scripts/uninstall_watcher_launchd.sh").read_text(encoding="utf-8")
        status = Path("scripts/status_watcher_launchd.sh").read_text(encoding="utf-8")

        self.assertIn("com.restaurant.daily-watcher", install)
        self.assertIn("/usr/bin/python3", install)
        self.assertIn("/Users/ming/Restaurant/restaurant-ai-bot/watch_daily_folder.py", install)
        self.assertIn("/Users/ming/Restaurant/restaurant-ai-bot/logs/watch_daily_folder.log", install)
        self.assertIn("<key>KeepAlive</key>", install)
        self.assertIn("<key>RunAtLoad</key>", install)
        self.assertRegex(install, r"launchctl (bootstrap|load)")
        self.assertRegex(install, r"launchctl (kickstart|start)")

        self.assertIn("launchctl", uninstall)
        self.assertIn("rm -f \"$PLIST_PATH\"", uninstall)
        self.assertIn("watch_daily_folder.py", status)
        self.assertIn("tail -50", status)


if __name__ == "__main__":
    unittest.main()
