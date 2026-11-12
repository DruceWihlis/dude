#!/usr/bin/env bash

set -euo pipefail

readonly USER_UNIT_DIR="${HOME}/.config/systemd/user"

systemctl --user disable --now dude.timer || true
rm -f -- "$USER_UNIT_DIR/dude.timer"
rm -f -- "$USER_UNIT_DIR/dude.service"
systemctl --user daemon-reload
