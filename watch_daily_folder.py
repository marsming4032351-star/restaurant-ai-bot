"""Watch the daily screenshot folder and run the one-command report flow.

Default folder:
    /Users/ming/Restaurant/daily-input/马连道

Run:
    python3 watch_daily_folder.py

Stop:
    Ctrl+C in the foreground, or kill the background process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import run_daily_report


WATCH_DIR = run_daily_report.INPUT_DIR
WATCH_STATE = run_daily_report.BASE_DIR / "data" / "watch_state.json"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def load_watch_state(path: Path = WATCH_STATE) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {"processed": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("processed", {})
    return data


def save_watch_state(state: dict, path: Path = WATCH_STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_candidate_images(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    images = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    ]
    return sorted(images, key=lambda p: p.stat().st_mtime_ns)


def file_signature(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return {
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "sha256": digest.hexdigest(),
    }


def wait_until_stable(path: Path, checks: int = 2, interval: float = 1.0, timeout: float = 30.0) -> dict:
    """Wait until size/mtime/hash stay unchanged for consecutive checks."""
    deadline = time.time() + timeout
    previous = None
    stable_count = 0
    while time.time() < deadline:
        current = file_signature(path)
        if current == previous:
            stable_count += 1
            if stable_count >= checks:
                return current
        else:
            previous = current
            stable_count = 0
        time.sleep(interval)
    raise TimeoutError(f"等待文件写入完成超时: {path}")


def should_process(state: dict, path: Path, signature: dict) -> bool:
    record = state.get("processed", {}).get(str(path))
    if not record:
        return True
    return any(record.get(key) != signature.get(key) for key in ("mtime_ns", "size", "sha256"))


def mark_processed(state: dict, path: Path, signature: dict, processed_at: str) -> None:
    state.setdefault("processed", {})[str(path)] = {
        **signature,
        "processed_at": processed_at,
    }


def run_report(image_path: Path, store: str, processing_date: str | None = None) -> None:
    cmd = [
        sys.executable,
        str(run_daily_report.BASE_DIR / "run_daily_report.py"),
        "--image",
        str(image_path),
        "--store",
        store,
    ]
    if processing_date:
        cmd.extend(["--date", processing_date])
    subprocess.run(cmd, cwd=run_daily_report.BASE_DIR, check=True)


def process_once(folder: Path, state_path: Path, store: str, processing_date: str | None = None) -> int:
    state = load_watch_state(state_path)
    processed = 0
    for image in find_candidate_images(folder):
        signature = wait_until_stable(image)
        if not should_process(state, image, signature):
            continue
        print(f"[watch] 发现新截图或更新: {image}")
        run_report(image, store, processing_date)
        mark_processed(state, image, signature, run_daily_report.now_iso())
        save_watch_state(state, state_path)
        processed += 1
    return processed


def watch_loop(folder: Path, state_path: Path, store: str, poll_interval: float) -> None:
    print(f"[watch] 监听目录: {folder}")
    print("[watch] 按 Ctrl+C 停止")
    while True:
        try:
            process_once(folder, state_path, store)
        except Exception as exc:
            print(f"[watch] 处理失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        time.sleep(poll_interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="监听日报截图文件夹并自动触发日报流程")
    parser.add_argument("--folder", default=str(WATCH_DIR), help="截图文件夹")
    parser.add_argument("--store", default="便宜坊马连道", help="门店名称")
    parser.add_argument("--date", default=None, help="处理日期 YYYY-MM-DD；仅供日志/识别参考，日报业务日期以图片表头为准")
    parser.add_argument("--state", default=str(WATCH_STATE), help="监听去重状态文件")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="轮询间隔秒数")
    parser.add_argument("--once", action="store_true", help="只扫描处理一次后退出")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    folder = Path(args.folder)
    state_path = Path(args.state)
    folder.mkdir(parents=True, exist_ok=True)
    if args.once:
        count = process_once(folder, state_path, args.store, args.date)
        print(f"[watch] 本次处理 {count} 张图片")
        return 0
    watch_loop(folder, state_path, args.store, args.poll_interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
