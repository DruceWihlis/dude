#!/usr/bin/env bash
# Installs the daily scan: systemd (Linux), launchd (macOS) or Task Scheduler (WSL).

set -euo pipefail

readonly DUDE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PORTABLE="$DUDE_DIR/scripts/portable.py"
# shellcheck source=settings.sh
source "$DUDE_DIR/scripts/settings.sh"
# shellcheck source=platform.sh
source "$DUDE_DIR/scripts/platform.sh"

hour="$(setting DUDE_SCAN_HOUR 5)"
tz="$(setting DUDE_TZ)"
if ! [[ "$hour" =~ ^([01]?[0-9]|2[0-3])$ ]]; then
  printf 'DUDE_SCAN_HOUR must be 0-23, got %s\n' "$hour" >&2
  exit 2
fi
hour="$(printf '%02d' "$((10#$hour))")"
mkdir -p -- "$DUDE_DIR/logs"

case "$(detect_platform)" in
  linux)
    unit_dir="${HOME}/.config/systemd/user"
    mkdir -p -- "$unit_dir"
    python3 "$PORTABLE" render "$DUDE_DIR/scheduler/dude.service.in" "$unit_dir/dude.service" \
      "DUDE_DIR=$DUDE_DIR" "PATH=$PATH"
    python3 "$PORTABLE" render "$DUDE_DIR/scheduler/dude.timer.in" "$unit_dir/dude.timer" \
      "ON_CALENDAR=*-*-* $hour:00:00${tz:+ $tz}"
    systemctl --user daemon-reload
    systemctl --user enable --now dude.timer
    systemctl --user list-timers dude.timer --all
    ;;
  macos)
    plist="${HOME}/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
    mkdir -p -- "$(dirname -- "$plist")"
    python3 "$PORTABLE" render "$DUDE_DIR/scheduler/dude.plist.in" "$plist" --xml \
      "LABEL=$LAUNCHD_LABEL" "DUDE_DIR=$DUDE_DIR" "PATH=$PATH"
    launchctl bootout "gui/$(id -u)/$LAUNCHD_LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$plist"
    printf 'Installed %s: runs hourly and at login; scans once a day after %s:00.\n' \
      "$plist" "$hour"
    ;;
  wsl)
    if [[ -n "$tz" ]]; then
      printf 'Note: Windows starts the task at %s:00 Windows time; DUDE_TZ only affects dude.sh.\n' \
        "$hour"
    fi
    xml="$DUDE_DIR/logs/.dude-task.xml"
    trap 'rm -f -- "$xml" "$xml.utf8"' EXIT
    python3 "$PORTABLE" render "$DUDE_DIR/scheduler/dude-task.xml.in" "$xml.utf8" --xml \
      "DISTRO=${WSL_DISTRO_NAME:?WSL_DISTRO_NAME is not set}" "DUDE_DIR=$DUDE_DIR" "HOUR=$hour"
    # Task Scheduler expects UTF-16 XML.
    iconv -f UTF-8 -t UTF-16 "$xml.utf8" > "$xml"
    schtasks.exe /Create /TN "$WINDOWS_TASK" /XML "$(wslpath -w "$xml")" /F
    printf 'Installed Windows task "%s": daily at %s:00 and at logon.\n' "$WINDOWS_TASK" "$hour"
    ;;
  *)
    printf 'Unsupported platform: %s\n' "$(detect_platform)" >&2
    exit 2
    ;;
esac
