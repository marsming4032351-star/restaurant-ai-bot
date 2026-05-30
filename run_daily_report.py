"""One-command daily report workflow.

Example:
    python3 run_daily_report.py --image "/Users/ming/Restaurant/daily-input/马连道/0529.png" --store 便宜坊马连道 --date 2026-05-29

The script intentionally orchestrates existing modules instead of replacing them:
image -> JSON -> Excel -> main.run() -> pipeline files -> git commit/push.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import re
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import config
import image_to_excel


BASE_DIR = Path(__file__).parent
INPUT_DIR = Path("/Users/ming/Restaurant/daily-input/马连道")
PIPELINE_STATE = BASE_DIR / "data" / "pipeline_state.json"
PIPELINE_LOG = BASE_DIR / "data" / "pipeline_log.csv"
STARTUP_DOCS = [
    BASE_DIR / "PROJECT_MEMORY.md",
    BASE_DIR / "docs" / "WORKFLOWS.md",
    PIPELINE_STATE,
]
PIPELINE_COLUMNS = [
    "date",
    "store_name",
    "source_type",
    "source_file",
    "excel_file",
    "normalized_json",
    "report_file",
    "feishu_pushed",
    "feishu_push_success",
    "pushed_at",
    "agent",
    "workflow_version",
    "status",
    "notes",
    "error_message",
    "created_at",
    "updated_at",
]


def now_iso() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).replace(microsecond=0).isoformat()


def read_startup_context() -> None:
    """Read required project context without scanning the repository."""
    for path in STARTUP_DOCS:
        if not path.exists():
            raise FileNotFoundError(f"启动文件不存在: {path}")
        path.read_text(encoding="utf-8")


def latest_input_image(input_dir: Path = INPUT_DIR) -> Path:
    if not input_dir.exists():
        raise FileNotFoundError(f"未指定 --image，且截图文件夹不存在: {input_dir}")
    candidates = [
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    if not candidates:
        raise FileNotFoundError(f"未指定 --image，且 {input_dir} 中没有 png/jpg/jpeg/webp 图片")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def extract_json_object(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"图片识别返回中找不到 JSON: {text[:300]}")


def _expected_keys() -> list[str]:
    keys = []
    for left_key, _placeholder, right_key in image_to_excel.LEFT_LAYOUT:
        if left_key:
            keys.append(left_key)
        if right_key:
            keys.append(right_key)
    for _category, fields in image_to_excel.RIGHT_LAYOUT:
        keys.extend(fields)
    return keys


def build_extraction_prompt(store: str, report_date: str) -> str:
    keys = "\n".join(f"- {key}" for key in _expected_keys())
    return (
        f"请从这张餐厅经营日报截图中读取 {store} 在 {report_date} 的所有可见数值，"
        "输出一个扁平 JSON 对象。只输出 JSON，不要 markdown。\n"
        "要求：\n"
        "1. key 必须尽量使用下面列表中的字段名。\n"
        "2. 数值用 number，不要带人民币符号、百分号或逗号。\n"
        "3. 百分比按截图数字输出，例如 70.28% 输出 70.28。\n"
        "4. 没看清的字段可以省略，不要编造。\n"
        "5. 重复的 日累计/月累计 字段必须保留前缀，例如 烤鸭_日累计、套餐_月累计。\n\n"
        f"字段列表：\n{keys}"
    )


def recognize_image(image_path: Path, store: str, report_date: str) -> dict:
    """Use an OpenAI-compatible vision model to read the report image."""
    if config.LLM_PROVIDER != "openai":
        raise RuntimeError("图片自动识别需要 OpenAI-compatible LLM_PROVIDER=openai")
    if not config.LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_KEY，无法自动识别图片")

    from openai import OpenAI

    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    model = getattr(config, "LLM_VISION_MODEL", "") or config.LLM_MODEL
    kwargs = {"api_key": config.LLM_API_KEY}
    if config.LLM_BASE_URL:
        kwargs["base_url"] = config.LLM_BASE_URL
    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_extraction_prompt(store, report_date)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            }
        ],
    )
    return extract_json_object(response.choices[0].message.content or "")


def _read_pipeline_rows(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists() or path.stat().st_size == 0:
        return PIPELINE_COLUMNS[:], []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def append_pipeline_log(path: Path, row: dict) -> None:
    """Append a pipeline row and upgrade older logs with new columns."""
    existing_columns, rows = _read_pipeline_rows(path)
    columns = existing_columns[:]
    for col in PIPELINE_COLUMNS:
        if col not in columns:
            columns.append(col)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for existing in rows:
            writer.writerow({col: existing.get(col, "") for col in columns})
        writer.writerow({col: row.get(col, "") for col in columns})


def is_already_pushed(path: Path, report_date: str, store: str) -> bool:
    _columns, rows = _read_pipeline_rows(path)
    for row in rows:
        if row.get("date") != report_date or row.get("store_name") != store:
            continue
        pushed = row.get("feishu_push_success") == "true" or row.get("feishu_pushed") == "true"
        if row.get("status") == "done" and pushed:
            return True
    return False


def store_history_has_row(path: Path, report_date: str, store: str) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("date") == report_date and row.get("store_name") == store:
                return True
    return False


def write_pipeline_state(path: Path, store: str, completed_date: str, timestamp: str) -> None:
    next_date = date.fromisoformat(completed_date) + timedelta(days=1)
    data = {
        "workflow_version": "1.0",
        "current_store_name": store,
        "current_target_date": str(next_date),
        "last_completed_date": completed_date,
        "last_completed_status": "done",
        "last_feishu_pushed": True,
        "next_action": "idle_all_done",
        "updated_at": timestamp,
        "updated_by": "codex",
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_git_commit_push(files: list[Path], message: str) -> None:
    rel_files = [str(path.relative_to(BASE_DIR)) for path in files]
    pre_staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=BASE_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    staged_files = {line.strip() for line in pre_staged.stdout.splitlines() if line.strip()}
    unexpected = staged_files - set(rel_files)
    if unexpected:
        raise RuntimeError(f"暂存区存在无关文件，停止自动提交: {sorted(unexpected)}")

    subprocess.run(["git", "add", *rel_files], cwd=BASE_DIR, check=True)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=BASE_DIR,
        check=False,
    )
    if diff.returncode == 0:
        print("[git] 没有需要提交的 pipeline 变更")
        return
    subprocess.run(["git", "commit", "-m", message], cwd=BASE_DIR, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, check=True)


def _pipeline_row(
    *,
    report_date: str,
    store: str,
    image_path: Path,
    excel_path: Path | None,
    report_path: Path | None,
    success: bool,
    timestamp: str,
    error: str = "",
) -> dict:
    return {
        "date": report_date,
        "store_name": store,
        "source_type": "screenshot",
        "source_file": str(image_path),
        "excel_file": str(excel_path) if excel_path else "",
        "normalized_json": "",
        "report_file": str(report_path) if report_path else "",
        "feishu_pushed": "true" if success else "false",
        "feishu_push_success": "true" if success else "false",
        "pushed_at": timestamp if success else "",
        "agent": "codex",
        "workflow_version": "1.0",
        "status": "done" if success else "failed",
        "notes": "" if success else "daily workflow failed",
        "error_message": error,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def run_daily_report(args: argparse.Namespace) -> int:
    read_startup_context()
    input_folder = Path(getattr(args, "input_folder", INPUT_DIR))
    image_path = Path(args.image) if args.image else latest_input_image(input_folder)
    if not image_path.exists():
        raise FileNotFoundError(f"图片不存在: {image_path}")
    if is_already_pushed(PIPELINE_LOG, args.date, args.store) and not args.force:
        print(f"[daily] {args.store} · {args.date} 已成功推送，跳过。需要重跑请加 --force")
        return 0
    history_file = config.DATA_DIR / "store_history.csv"
    if store_history_has_row(history_file, args.date, args.store) and not args.force:
        raise RuntimeError(f"{args.store} · {args.date} 已存在 store_history.csv 记录；重跑请加 --force")

    timestamp = now_iso()
    excel_path = None
    report_path = config.OUTPUT_DIR / f"report_{args.store_id}_{args.date}.json"
    try:
        print(f"[daily] 识别图片: {image_path}")
        daily_json = recognize_image(image_path, args.store, args.date)
        excel_path = image_to_excel.build_excel(daily_json, args.date, config.DATA_DIR)
        print(f"[daily] 已生成 Excel: {excel_path}")

        import main as daily_main

        daily_main.run(None, args.store_id, excel_path, args_ns=SimpleNamespace(force=args.force))
        write_pipeline_state(PIPELINE_STATE, args.store, args.date, timestamp)
        append_pipeline_log(
            PIPELINE_LOG,
            _pipeline_row(
                report_date=args.date,
                store=args.store,
                image_path=image_path,
                excel_path=excel_path,
                report_path=report_path,
                success=True,
                timestamp=timestamp,
            ),
        )
        run_git_commit_push(
            [PIPELINE_STATE, PIPELINE_LOG],
            f"日报推送完成：{args.date} {args.store}",
        )
        return 0
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        append_pipeline_log(
            PIPELINE_LOG,
            _pipeline_row(
                report_date=args.date,
                store=args.store,
                image_path=image_path,
                excel_path=excel_path,
                report_path=report_path if report_path.exists() else None,
                success=False,
                timestamp=timestamp,
                error=error,
            ),
        )
        print("[daily] 失败，已写入 pipeline_log.csv", file=sys.stderr)
        traceback.print_exc()
        try:
            run_git_commit_push(
                [PIPELINE_LOG],
                f"记录日报失败：{args.date} {args.store}",
            )
        except Exception as git_exc:
            print(f"[git] 失败日志提交/推送失败: {git_exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键处理经营日报截图并推送飞书")
    parser.add_argument("--image", help=f"日报截图路径；不传时自动使用 {INPUT_DIR} 中最新图片")
    parser.add_argument("--input-folder", default=str(INPUT_DIR), help="未传 --image 时读取最新截图的文件夹")
    parser.add_argument("--store", default="便宜坊马连道", help="门店名称")
    parser.add_argument("--store-id", default="MLD", help="内部门店编号，用于 report 文件名")
    parser.add_argument("--date", required=True, help="日报日期 YYYY-MM-DD")
    parser.add_argument("--force", action="store_true", help="允许重跑已推送日期，并覆盖历史重复记录")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_daily_report(parse_args()))
