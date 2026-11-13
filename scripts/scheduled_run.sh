#!/usr/bin/env bash
# Scheduler entry point for launchd (macOS) and Task Scheduler (WSL): the regular scan, then the
# company watchlist hook. Both are no-ops when nothing is due, so frequent triggers are cheap.

set -uo pipefail

readonly DUDE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p -- "$DUDE_DIR/logs"
"$BASH" "$DUDE_DIR/dude.sh" && "$BASH" "$DUDE_DIR/scripts/run_company_scan.sh"
