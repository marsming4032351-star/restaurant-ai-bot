#!/bin/bash
# ─────────────────────────────────────────────────────────
# 便宜坊日报助手 — 手动/兼容入口：生成上周经营周报
# 当前主链路不依赖 crontab，由周一处理上周日日报成功后自动触发。
# ─────────────────────────────────────────────────────────

PROJECT_DIR="/Users/ming/Restaurant/restaurant-ai-bot"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/weekly_report.log"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 时间戳
NOW=$(date '+%Y-%m-%d %H:%M:%S')

echo "" >> "$LOG_FILE"
echo "====== $NOW 开始生成上周周报 ======" >> "$LOG_FILE"

# 进入项目目录
cd "$PROJECT_DIR" || {
    echo "[$NOW] ❌ 无法进入项目目录: $PROJECT_DIR" >> "$LOG_FILE"
    exit 1
}

# 运行周报（使用系统 python3，加载 .env 由脚本内部完成）
python3 "$PROJECT_DIR/weekly_report.py" --last-week >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

NOW=$(date '+%Y-%m-%d %H:%M:%S')
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$NOW] ✅ 周报推送成功" >> "$LOG_FILE"
else
    echo "[$NOW] ❌ 周报推送失败，exit code: $EXIT_CODE" >> "$LOG_FILE"
fi

echo "====== $NOW 结束 ======" >> "$LOG_FILE"

exit $EXIT_CODE
