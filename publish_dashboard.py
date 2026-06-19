#!/usr/bin/env python3
"""渲染经营驾驶舱并发布到飞书妙搭应用（同一 app_id，URL 不变，内容刷新）。

发布走 lark-cli 的妙搭能力：`apps +html-publish --app-id <id> --path <html>`。
注意：标准 npm 版 lark-cli 不含 `apps` 子命令，需使用支持 apps 域的构建
（见 README/PROJECT_MEMORY 妙搭章节）。本脚本不读取/打印任何 token 或 secret。

配置（均可被命令行覆盖）：
- LARK_APPS_CLI    支持 apps 域的 lark-cli 可执行文件路径
- DASHBOARD_APP_ID 目标妙搭应用 ID（非机密，即 /app/ 链接里那段）

设计原则（与日报主流程一致）：发布失败只告警、抛异常由调用方决定是否吞掉，
绝不伪造数据、绝不因发布失败把日报业务判为 failed。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import render_dashboard

BASE_DIR = Path(__file__).resolve().parent
# 妙搭要求入口文件名为 index.html，发布产物固定输出到 dist/index.html
DEFAULT_OUTPUT = BASE_DIR / "outputs" / "interactive_dashboard" / "dist" / "index.html"
# 应用 ID 不是机密（就是 /app/ 链接里那段），给个默认值，可用 env / 参数覆盖
DEFAULT_APP_ID = os.environ.get("DASHBOARD_APP_ID", "app_4kdvcqjv319yh")
DEFAULT_CLI = os.environ.get("LARK_APPS_CLI", str(BASE_DIR / "bin" / "lark-cli-apps"))


def publish_html(html_path: Path, app_id: str, cli_bin: str, *, dry_run: bool = False) -> dict:
    """单次 multipart POST 发布 HTML，返回 lark-cli 的 JSON 结果（含 access url）。"""
    cli = Path(cli_bin)
    if not cli.exists():
        raise FileNotFoundError(
            f"未找到支持妙搭(apps)的 lark-cli: {cli_bin}；"
            "请用 LARK_APPS_CLI 指向 apps 域构建，或 --cli 显式传入"
        )
    html_path = html_path.resolve()
    # 妙搭要求 --path 为「当前目录内的相对路径」，故在 HTML 所在目录执行、只传文件名
    cmd = [
        str(cli), "apps", "+html-publish",
        "--app-id", app_id,
        "--path", html_path.name,
        "--as", "user",
        "--format", "json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    # 干净环境：剥离代理，避免妙搭鉴权走错代理（沿用项目 miaoda 命令做法）
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in {"http_proxy", "https_proxy", "all_proxy"}}
    env.update({"HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "",
                "http_proxy": "", "https_proxy": "", "all_proxy": ""})
    proc = subprocess.run(cmd, cwd=html_path.parent, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"妙搭发布失败 (exit {proc.returncode}): {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw": proc.stdout.strip()}


def render_and_publish(
    store: str,
    *,
    template: Path = render_dashboard.DEFAULT_TEMPLATE,
    output: Path = DEFAULT_OUTPUT,
    app_id: str = DEFAULT_APP_ID,
    cli_bin: str = DEFAULT_CLI,
    dry_run: bool = False,
) -> dict:
    rows = render_dashboard.build_rows(store)
    if not rows:
        raise RuntimeError(f"没有 {store} 的数据，无法渲染驾驶舱")
    html = render_dashboard.render(rows, template)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"[dashboard] 已渲染 {len(rows)} 天（{rows[0]['date']} ~ {rows[-1]['date']}）-> {output}")
    result = publish_html(output, app_id, cli_bin, dry_run=dry_run)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染并发布经营驾驶舱到飞书妙搭")
    parser.add_argument("--store", default="便宜坊马连道")
    parser.add_argument("--template", default=str(render_dashboard.DEFAULT_TEMPLATE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--app-id", default=DEFAULT_APP_ID, help="妙搭应用 ID")
    parser.add_argument("--cli", default=DEFAULT_CLI, help="支持 apps 域的 lark-cli 路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印请求，不真正发布")
    args = parser.parse_args()

    result = render_and_publish(
        args.store,
        template=Path(args.template),
        output=Path(args.output),
        app_id=args.app_id,
        cli_bin=args.cli,
        dry_run=args.dry_run,
    )
    url = result.get("url") or result.get("access_url") or result.get("data", {}).get("url") if isinstance(result, dict) else None
    print(f"[dashboard] 发布完成{'(dry-run)' if args.dry_run else ''}：{url or json.dumps(result, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
