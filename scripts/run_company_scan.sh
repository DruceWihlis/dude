#!/usr/bin/env bash
# Runs the company watchlist scan after a successful regular scan on configured weekdays.

set -euo pipefail

readonly DUDE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=settings.sh
source "$DUDE_DIR/scripts/settings.sh"

dude_tz="$(setting DUDE_TZ)"
if [[ -n "$dude_tz" ]]; then
  export TZ="$dude_tz"
fi

readonly DAILY_STATE="$DUDE_DIR/.last_successful_date"
readonly COMPANY_DAYS="$(setting DUDE_COMPANY_DAYS 1,3,5)"

if [[ ! -r "$DUDE_DIR/config/companies.md" || -z "$COMPANY_DAYS" ]]; then
  exit 0
fi
if [[ ! -r "$DAILY_STATE" ]] || [[ "$(<"$DAILY_STATE")" != "$(date +%F)" ]]; then
  exit 0
fi

weekday="$(date +%u)"
if [[ ",${COMPANY_DAYS// /}," == *",$weekday,"* ]]; then
  exec "$DUDE_DIR/dude.sh" --companies
fi
