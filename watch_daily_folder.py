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
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import run_daily_report


WATCH_DIR = run_daily_report.INPUT_DIR
WATCH_STATE = run_daily_report.BASE_DIR / "data" / "watch_state.json"
PROJECT_PYTHON = run_daily_report.BASE_DIR / ".venv" / "bin" / "python"
DEFAULT_PROXY = "http://127.0.0.1:7890"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# 成功完成(OCR→数据→日报→飞书推送)后的归档根目录，按业务月份分桶 YYYY-MM。
ARCHIVE_ROOT = Path("/Users/ming/Restaurant/daily-archive/马连道")
# 处理失败的图片移动到监听目录下的失败区(子目录不会被 find_candidate_images 扫描到)。
FAILED_DIRNAME = "_failed_old"
# run_daily_report.py 成功时会打印 "图片表头业务日期: YYYY-MM-DD"，作为查不到流水时的兜底。
BUSINESS_DATE_OUTPUT_RE = re.compile(r"业务日期[:：]\s*(\d{4}-\d{2}-\d{2})")


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


def run_report(
    image_path: Path, store: str, processing_date: str | None = None
) -> subprocess.CompletedProcess:
    """运行日报子进程并捕获输出。

    不再用 check=True 直接抛异常：调用方根据 returncode 区分成功/失败，
    成功归档、失败移入失败区并保留日志。stdout/stderr 由调用方透传回 watcher 日志。
    """
    cmd = [
        str(PROJECT_PYTHON),
        str(run_daily_report.BASE_DIR / "run_daily_report.py"),
        "--image",
        str(image_path),
        "--store",
        store,
        # 日报推送成功后把当日数据同步进妙搭 daily_sales 表（与主流程解耦、失败只告警）
        "--publish-dashboard",
    ]
    if processing_date:
        cmd.extend(["--date", processing_date])
    env = os.environ.copy()
    env["HTTP_PROXY"] = DEFAULT_PROXY
    env["HTTPS_PROXY"] = DEFAULT_PROXY
    env["http_proxy"] = DEFAULT_PROXY
    env["https_proxy"] = DEFAULT_PROXY
    return subprocess.run(
        cmd, cwd=run_daily_report.BASE_DIR, env=env, capture_output=True, text=True
    )


def pipeline_business_date(image_path: Path) -> str | None:
    """从 pipeline_log.csv 按 source_file 反查业务日期（图片表头真实日期）。"""
    try:
        _cols, rows = run_daily_report._read_pipeline_rows(run_daily_report.PIPELINE_LOG)
    except Exception:
        return None
    target = str(image_path)
    found = None
    for row in rows:
        if row.get("source_file") == target and row.get("business_date"):
            found = row.get("business_date")  # 取最后一条匹配，保证拿到最新值
    return found


def business_date_from_output(text: str | None) -> str | None:
    if not text:
        return None
    match = BUSINESS_DATE_OUTPUT_RE.search(text)
    return match.group(1) if match else None


def archive_dir_for(image_path: Path, stdout: str | None = None) -> Path:
    """按业务日期(YYYY-MM)决定归档目录；绝不用系统日期当业务月份。

    优先用 pipeline_log 的 business_date，其次解析子进程输出；都拿不到才落到
    _unknown-date 桶（不伪造日期），便于人工复核。
    """
    business_date = pipeline_business_date(image_path) or business_date_from_output(stdout)
    month = business_date[:7] if business_date else "_unknown-date"
    return ARCHIVE_ROOT / month


def move_no_clobber(src: Path, dest_dir: Path) -> Path:
    """移动文件到目标目录；同名时加时间戳后缀，绝不覆盖、绝不删除原图。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = dest_dir / f"{src.stem}__{stamp}{src.suffix}"
    shutil.move(str(src), str(dest))
    return dest


def write_failure_log(failed_path: Path, proc: subprocess.CompletedProcess, when: str) -> Path:
    """在失败图片旁写 .log，保留退出码与子进程 stdout/stderr 便于排查。"""
    log_path = failed_path.with_name(failed_path.name + ".log")
    parts = [
        f"failed_at: {when}",
        f"returncode: {getattr(proc, 'returncode', 'NA')}",
        f"original_image: {failed_path.name}",
        "",
        "=== STDOUT ===",
        getattr(proc, "stdout", "") or "",
        "=== STDERR ===",
        getattr(proc, "stderr", "") or "",
    ]
    log_path.write_text("\n".join(parts), encoding="utf-8")
    return log_path


def process_once(folder: Path, state_path: Path, store: str, processing_date: str | None = None) -> int:
    state = load_watch_state(state_path)
    failed_dir = folder / FAILED_DIRNAME
    processed = 0
    for image in find_candidate_images(folder):
        signature = wait_until_stable(image)
        if not should_process(state, image, signature):
            continue
        print(f"[watch] 发现新截图或更新: {image}")
        proc = run_report(image, store, processing_date)
        # 把子进程输出透传回 watcher 日志（launchd 日志可见），同时用于失败留档
        if proc.stdout:
            sys.stdout.write(proc.stdout)
            sys.stdout.flush()
        if proc.stderr:
            sys.stderr.write(proc.stderr)
            sys.stderr.flush()
        when = run_daily_report.now_iso()
        if proc.returncode == 0:
            # 成功：先记去重状态，再按业务月份归档。归档失败只告警，不影响已成功的业务。
            mark_processed(state, image, signature, when)
            save_watch_state(state, state_path)
            try:
                dest = move_no_clobber(image, archive_dir_for(image, proc.stdout))
                print(f"[watch] 处理成功并已推送，归档到: {dest}")
            except Exception as move_exc:
                print(
                    f"[watch] 警告: 业务已成功但归档移动失败(原图仍在监听目录): "
                    f"{type(move_exc).__name__}: {move_exc}",
                    file=sys.stderr,
                )
            processed += 1
        else:
            # 失败：移动到失败区并保留日志，不删除原图。
            print(f"[watch] 处理失败 (exit {proc.returncode}): {image}", file=sys.stderr)
            try:
                dest = move_no_clobber(image, failed_dir)
                log_path = write_failure_log(dest, proc, when)
                print(f"[watch] 已移到失败区: {dest}（日志: {log_path.name}）", file=sys.stderr)
            except Exception as move_exc:
                # 移动失败才标记已处理，防止对同一张坏图无限重试；移动成功则不标记，
                # 用户修好后重新投放同名/新图仍可被重新处理。
                print(
                    f"[watch] 警告: 失败图片移动失败，标记跳过以防重试风暴: "
                    f"{type(move_exc).__name__}: {move_exc}",
                    file=sys.stderr,
                )
                mark_processed(state, image, signature, when)
                save_watch_state(state, state_path)
    return processed


def archive_existing(folder: Path, state_path: Path) -> int:
    """一次性迁移：把当前仍留在监听目录、且已成功处理过的图片按业务月份归档。

    “已成功处理”以监听去重状态 watch_state.processed 为准（仅成功才会写入）。
    未见成功记录的图片留在原地，交给正常监听流程处理，不在此迁移。
    """
    state = load_watch_state(state_path)
    processed_paths = set(state.get("processed", {}).keys())
    moved = 0
    for image in find_candidate_images(folder):
        if str(image) not in processed_paths:
            print(f"[archive] 跳过(无成功处理记录，留给监听流程): {image.name}")
            continue
        business_date = pipeline_business_date(image)
        dest = move_no_clobber(image, archive_dir_for(image))
        moved += 1
        print(f"[archive] {image.name} (业务日期 {business_date or '未知'}) -> {dest}")
    return moved


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
    parser.add_argument(
        "--archive-existing",
        action="store_true",
        help="一次性迁移：把监听目录里已成功处理过的图片按业务月份归档到 daily-archive，然后退出",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    folder = Path(args.folder)
    state_path = Path(args.state)
    folder.mkdir(parents=True, exist_ok=True)
    if args.archive_existing:
        count = archive_existing(folder, state_path)
        print(f"[archive] 本次归档迁移 {count} 张已完成图片")
        return 0
    if args.once:
        count = process_once(folder, state_path, args.store, args.date)
        print(f"[watch] 本次处理 {count} 张图片")
        return 0
    watch_loop(folder, state_path, args.store, args.poll_interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
