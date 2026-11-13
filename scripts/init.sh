#!/usr/bin/env bash
# Creates local config and state files from the templates. Never overwrites existing files.

set -euo pipefail

readonly DUDE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$DUDE_DIR"

create() {
  local path="$1"
  if [[ -e "$path" ]]; then
    printf 'keep    %s\n' "$path"
    return 0
  fi
  mkdir -p -- "$(dirname -- "$path")"
  cat > "$path"
  printf 'create  %s\n' "$path"
}

copy_example() {
  local example="$1"
  local target="$2"
  create "$target" < "$example"
}

copy_example .env.example .env
chmod 600 .env
new_profile=''
[[ -e config/profile.md ]] || new_profile=1
copy_example config/profile.example.md config/profile.md
# Example CVs only come with the example profile that lists them.
if [[ -n "$new_profile" ]]; then
  copy_example cv/backend.example.md cv/backend.md
  copy_example cv/data.example.md cv/data.md
fi
copy_example config/sources.example.md config/sources.md
copy_example config/recipes.example.md config/recipes.md
copy_example config/mcp.example.json config/mcp.json

create NEW.md <<'MD'
# Relevant vacancies

The active list is sorted by fit score, then freshness. Change `NEW` to `APPLIED` or `SKIP`
after reviewing an entry; scans preserve your statuses and notes.

## Active shortlist
MD

create APPLIED.md <<'MD'
# Archived vacancies

Applied, skipped, expired and closed entries moved here from `NEW.md`.
MD

printf 'url\tcompany_role\treason\n' | create data/rejections.tsv
printf '# Scan checkpoint\n\nNo runs yet.\n' | create data/checkpoint.md
printf '# Company scan checkpoint\n\nNo runs yet.\n' | create data/company_checkpoint.md

cat <<'NEXT'

Next:
  1. Edit config/profile.md: who you are, what you want, which CVs to use. Put your CVs in cv/
     (PDF, DOCX, ODT, Markdown or text) and delete the examples.
  2. Edit config/sources.md: the job boards to scan.
  3. Put TG_BOT_TOKEN in .env, send /start to your bot, run:
       python3 scripts/telegram_notify.py --setup-test
  4. Optional: cp config/companies.example.md config/companies.md for a company watchlist.
  5. ./dude.sh --check-sandbox, then ./dude.sh --force for a first run.
  6. scripts/install_timer.sh to run it every morning.
NEXT
