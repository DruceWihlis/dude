#!/usr/bin/env bash
# Installs the systemd user service and timer for the daily scan.

set -euo pipefail

readonly DUDE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly USER_UNIT_DIR="${HOME}/.config/systemd/user"
# shellcheck source=settings.sh
source "$DUDE_DIR/scripts/settings.sh"

hour="$(setting DUDE_SCAN_HOUR 5)"
tz="$(setting DUDE_TZ)"
if ! [[ "$hour" =~ ^([01]?[0-9]|2[0-3])$ ]]; then
  printf 'DUDE_SCAN_HOUR must be 0-23, got %s\n' "$hour" >&2
  exit 2
fi
calendar="$(printf '*-*-* %02d:00:00' "$((10#$hour))")${tz:+ $tz}"

mkdir -p -- "$USER_UNIT_DIR"
sed -e "s|@DUDE_DIR@|$DUDE_DIR|g" \
  "$DUDE_DIR/systemd/dude.service.in" > "$USER_UNIT_DIR/dude.service"
sed -e "s|@ON_CALENDAR@|$calendar|g" \
  "$DUDE_DIR/systemd/dude.timer.in" > "$USER_UNIT_DIR/dude.timer"

systemctl --user daemon-reload
systemctl --user enable --now dude.timer
systemctl --user list-timers dude.timer --all
