#!/bin/bash
set -euo pipefail

LABEL="com.restaurant.daily-watcher"
PROJECT_DIR="/Users/ming/Restaurant/restaurant-ai-bot"
LOG_PATH="$PROJECT_DIR/logs/watch_daily_folder.log"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
SERVICE_TARGET="gui/$(id -u)/$LABEL"

echo "== launchd plist =="
if [ -f "$PLIST_PATH" ]; then
  echo "present: $PLIST_PATH"
else
  echo "missing: $PLIST_PATH"
fi

echo
echo "== launchd service =="
if launchctl print "$SERVICE_TARGET" >/dev/null 2>&1; then
  echo "loaded: $SERVICE_TARGET"
  launchctl print "$SERVICE_TARGET" 2>/dev/null | sed -n '1,80p'
else
  echo "not loaded: $SERVICE_TARGET"
  launchctl list 2>/dev/null | grep "$LABEL" || true
fi

echo
echo "== process =="
pgrep -fl "watch_daily_folder.py" || echo "watch_daily_folder.py process not found"

echo
echo "== recent log =="
if [ -f "$LOG_PATH" ]; then
  tail -50 "$LOG_PATH"
else
  echo "log not found: $LOG_PATH"
fi
