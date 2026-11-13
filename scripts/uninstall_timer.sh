#!/usr/bin/env bash
# Removes the daily scan installed by install_timer.sh.

set -euo pipefail

readonly DUDE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=platform.sh
source "$DUDE_DIR/scripts/platform.sh"

case "$(detect_platform)" in
  linux)
    unit_dir="${HOME}/.config/systemd/user"
    systemctl --user disable --now dude.timer || true
    rm -f -- "$unit_dir/dude.timer" "$unit_dir/dude.service"
    systemctl --user daemon-reload
    ;;
  macos)
    launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" 2>/dev/null || true
    rm -f -- "${HOME}/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
    ;;
  wsl)
    schtasks.exe /Delete /TN "$WINDOWS_TASK" /F || true
    ;;
esac
