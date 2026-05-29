"""每日任务入口。

用法:
    # 跑昨天的日报(cron 默认场景)
    python main.py

    # 指定日期 + 门店
    python main.py --date 2026-05-26 --store S001

    # 指定数据文件
    python main.py --file data/20260526.xlsx --store S001 --date 2026-05-26

cron 推荐:
    0 8 * * *  cd /opt/restaurant-ai-bot && /usr/bin/python main.py >> output/cron.log 2>&1
"""
from __future__ import annotations
import argparse
import json
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

import config
import parser as P
import analyst
import visualizer
import feishu_bot
import history


def find_default_file(report_date: date) -> Path:
    """约定:data/YYYYMMDD.xlsx 或 data/YYYY-MM-DD.csv 都行,自动找。"""
    candidates = [
        config.DATA_DIR / f"{report_date.strftime('%Y%m%d')}.xlsx",
        config.DATA_DIR / f"{report_date.strftime('%Y-%m-%d')}.xlsx",
        config.DATA_DIR / f"{report_date.strftime('%Y%m%d')}.csv",
        config.DATA_DIR / f"{report_date.strftime('%Y-%m-%d')}.csv",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"找不到 {report_date} 的日报,候选:{[str(c) for c in candidates]}")


def run(report_date: date | None, store_id: str,
        file_path: Path | None = None, args_ns=None) -> None:
    print(f"[main] === 日报 {report_date or '(从文件名抓)'} / store={store_id} ===")

    # 1. 解析
    fp = file_path or find_default_file(report_date) if report_date else file_path
    if fp is None:
        raise ValueError("必须指定 --file 或 --date 之一")
    print(f"[1/4] 解析 {fp.name}")
    daily = P.load_daily(fp, report_date)
    P.append_history(daily)
    daily = P.enrich_with_history(daily)

    actual_date = daily["meta"]["date"]   # parser 抓到的真实日期

    # 2. AI 分析
    print(f"[2/4] AI 诊断 (model={config.LLM_MODEL})")
    report = analyst.diagnose(daily)
    print(f"      → {report.get('health_level')} | {report.get('headline')}")

    # 3. 出图
    print("[3/4] 生成图表")
    charts = visualizer.make_all_charts(daily)
    print(f"      → {len(charts)} 张图")

    # 4. 飞书推送
    print("[4/4] 推送飞书")
    feishu_bot.send_card(report, daily["meta"], charts, daily=daily)

    # 5. 保存历史记录
    history.save(daily, report, force=getattr(args_ns, "force", False))

    print("[main] ✅ 完成")

    # 落地一份 JSON 留档,方便复盘
    log_path = config.OUTPUT_DIR / f"report_{store_id}_{actual_date}.json"
    import datetime
    class _DateEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return str(obj)
            return super().default(obj)
    log_path.write_text(json.dumps({"daily": daily, "report": report},
                                   cls=_DateEncoder, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="报告日 YYYY-MM-DD(若不传则从文件名自动抓)")
    ap.add_argument("--store", default="MLD", help="门店编号,默认 MLD(便宜坊马连道)")
    ap.add_argument("--file", help="指定日报文件路径(可选,默认按日期找)")
    ap.add_argument("--force", action="store_true", help="历史记录重复时直接覆盖，不询问")
    args = ap.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else None
    file_path = Path(args.file) if args.file else None

    # 若两者都没传:跑昨天 + data 目录自动找
    if report_date is None and file_path is None:
        report_date = date.today() - timedelta(days=1)

    try:
        run(report_date, args.store, file_path, args_ns=args)
    except Exception as e:
        err = f"❌ 日报机器人异常\n门店: {args.store}\n日期: {report_date}\n错误: {e}\n\n{traceback.format_exc()[:1000]}"
        print(err, file=sys.stderr)
        feishu_bot.send_text_fallback(err)
        sys.exit(1)


if __name__ == "__main__":
    main()
