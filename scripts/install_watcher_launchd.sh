#!/bin/bash
set -euo pipefail

LABEL="com.restaurant.daily-watcher"
PROJECT_DIR="/Users/ming/Restaurant/restaurant-ai-bot"
SCRIPT_PATH="/Users/ming/Restaurant/restaurant-ai-bot/watch_daily_folder.py"
PYTHON_PATH="/Users/ming/Restaurant/restaurant-ai-bot/.venv/bin/python"
INPUT_DIR="/Users/ming/Restaurant/daily-input/马连道"
LOG_DIR="$PROJECT_DIR/logs"
LOG_PATH="/Users/ming/Restaurant/restaurant-ai-bot/logs/watch_daily_folder.log"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
SERVICE_TARGET="gui/$(id -u)/$LABEL"

mkdir -p "$LOG_DIR"
mkdir -p "$INPUT_DIR"
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_PATH</string>
    <string>$SCRIPT_PATH</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>

  <key>StandardOutPath</key>
  <string>$LOG_PATH</string>

  <key>StandardErrorPath</key>
  <string>$LOG_PATH</string>

  <key>KeepAlive</key>
  <true/>

  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
PLIST

chmod 644 "$PLIST_PATH"

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || \
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true

if launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1; then
  :
else
  launchctl load "$PLIST_PATH"
fi

launchctl enable "$SERVICE_TARGET" >/dev/null 2>&1 || true
launchctl kickstart -k "$SERVICE_TARGET" >/dev/null 2>&1 || \
  launchctl start "$LABEL" >/dev/null 2>&1 || true

echo "Installed launchd watcher: $LABEL"
echo "Plist: $PLIST_PATH"
echo "Log: $LOG_PATH"
