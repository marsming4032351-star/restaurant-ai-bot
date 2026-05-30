#!/bin/bash
set -euo pipefail

LABEL="com.restaurant.daily-watcher"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || \
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true

pkill -f "/Users/ming/Restaurant/restaurant-ai-bot/watch_daily_folder.py" >/dev/null 2>&1 || true

rm -f "$PLIST_PATH"

echo "Uninstalled launchd watcher: $LABEL"
echo "Removed plist: $PLIST_PATH"
echo "Business data, logs, screenshots, Excel files, and reports were not deleted."
