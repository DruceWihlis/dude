#!/usr/bin/env bash
# dude: the cron hunts, you abide.

set -euo pipefail

# Parse the complete run before executing so edits during a scan cannot shift shell reads.
{

readonly DUDE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/settings.sh
source "$DUDE_DIR/scripts/settings.sh"
cd -- "$DUDE_DIR"

dude_tz="$(setting DUDE_TZ)"
if [[ -n "$dude_tz" ]]; then
  export TZ="$dude_tz"
fi

PROMPT_FILE="$DUDE_DIR/prompts/scan.md"
readonly RESULT_FILE="$DUDE_DIR/NEW.md"
readonly LOG_DIR="$DUDE_DIR/logs"
STATE_FILE="$DUDE_DIR/.last_successful_date"
readonly LOCK_FILE="$DUDE_DIR/.runner.lock"
readonly SCHEDULE_HOUR="$(setting DUDE_SCAN_HOUR 5)"
readonly CATCH_UP_HOUR="$(setting DUDE_CATCHUP_HOUR 18)"
readonly SCAN_MINUTES="$(setting DUDE_SCAN_MINUTES 50)"
readonly AGENT_SETTING="$(setting DUDE_AGENT auto)"
readonly MODEL="$(setting DUDE_MODEL)"
readonly EFFORT="$(setting DUDE_EFFORT low)"
readonly MAX_BUDGET_USD="$(setting DUDE_MAX_BUDGET_USD)"

force=false
dry_run=false
check_sandbox=false
source_url=''
companies=false
log_suffix=''

usage() {
  cat <<'USAGE'
Usage: dude.sh [--force] [--dry-run] [--check-sandbox] [--companies] [--source=URL]

  --force          ignore the schedule window and the once-per-day guard
  --dry-run        print what would run and exit
  --check-sandbox  verify that the agent CLI can start, then exit
  --companies      scan the company watchlist (config/companies.md)
  --source=URL     scan a single source from config/sources.md
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --force) force=true ;;
    --dry-run) dry_run=true ;;
    --check-sandbox) check_sandbox=true; force=true ;;
    --companies) companies=true ;;
    --source=*) source_url="${arg#--source=}" ;;
    -h|--help) usage; exit 0 ;;
    *)
      printf 'Unknown argument: %s\n' "$arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for required in config/profile.md config/sources.md NEW.md APPLIED.md data/rejections.tsv; do
  if [[ ! -e "$DUDE_DIR/$required" ]]; then
    printf 'Missing %s. Run scripts/init.sh first.\n' "$required" >&2
    exit 2
  fi
done

if [[ "$companies" == true ]]; then
  if [[ -n "$source_url" ]]; then
    printf '%s\n' '--companies cannot be combined with --source' >&2
    exit 2
  fi
  if [[ ! -r "$DUDE_DIR/config/companies.md" ]]; then
    printf '%s\n' 'Missing config/companies.md; copy config/companies.example.md first.' >&2
    exit 2
  fi
  PROMPT_FILE="$DUDE_DIR/prompts/companies.md"
  STATE_FILE="$DUDE_DIR/.last_company_successful_date"
  log_suffix='-companies'
fi
scan_source="${source_url:-all}"
if [[ "$companies" == true ]]; then
  scan_source='companies'
fi

if [[ -n "$source_url" ]]; then
  python3 - "$DUDE_DIR/config/sources.md" "$source_url" <<'PY'
import re
import sys
from pathlib import Path
approved = re.findall(r'^- (https?://[^\s`]+)', Path(sys.argv[1]).read_text(), re.M)
if sys.argv[2].rstrip('/') not in {url.rstrip('/') for url in approved}:
    sys.exit('Requested source is not in config/sources.md')
PY
fi

mkdir -p -- "$LOG_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  printf '%s another run is already active\n' "$(date --iso-8601=seconds)" \
    >> "$LOG_DIR/timer.log"
  exit 0
fi

log_timer() {
  printf '%s %s\n' "$(date --iso-8601=seconds)" "$*" \
    >> "$LOG_DIR/timer.log"
}

notify_user() {
  local title="$1"
  local message="$2"

  if ! command -v notify-send >/dev/null 2>&1; then
    log_timer "notification skipped: notify-send is unavailable"
    return 0
  fi

  if notify-send \
    --app-name="dude" \
    --urgency=normal \
    --expire-time=15000 \
    "$title" "$message"; then
    log_timer "notification sent: $title"
  else
    log_timer "notification failed: $title"
  fi
}

collect_vacancy_urls() {
  if [[ -r "$RESULT_FILE" ]]; then
    sed -n 's/^- Vacancy: \(https:\/\/.*\)$/\1/p' "$RESULT_FILE" \
      | sort -u
  fi
}

executable() {
  [[ -n "$1" && -x "$1" ]] && printf '%s\n' "$1"
}

find_codex() {
  executable "$(setting CODEX_BIN)" && return 0
  executable "$(command -v codex 2>/dev/null || true)" && return 0
  # Codex bundled with JetBrains IDEs (AI Assistant / ACP agents).
  executable "$(
    find "${HOME}/.cache/JetBrains" \
      -path '*/node_modules/@openai/codex-linux-x64/vendor/*/bin/codex' \
      -type f -executable -print 2>/dev/null \
      | sort -V \
      | tail -n 1
  )" && return 0
  return 1
}

find_claude() {
  executable "$(setting CLAUDE_BIN)" && return 0
  executable "$(command -v claude 2>/dev/null || true)" && return 0
  executable "${HOME}/.claude/local/claude" && return 0
  return 1
}

now_epoch="$(date +%s)"
today="$(date +%F)"
scheduled_epoch="$(date -d "$today $SCHEDULE_HOUR:00:00" +%s)"
delay_seconds=$((now_epoch - scheduled_epoch))
catch_up_epoch="$(date -d "$today $CATCH_UP_HOUR:00:00" +%s)"

if [[ "$force" != true ]]; then
  if (( delay_seconds < 0 )); then
    log_timer "skip: scheduled time has not arrived"
    exit 0
  fi

  if (( now_epoch > catch_up_epoch )); then
    log_timer "skip: missed ${CATCH_UP_HOUR}:00 catch-up deadline"
    exit 0
  fi

  if [[ -z "$source_url" && -f "$STATE_FILE" ]] && [[ "$(<"$STATE_FILE")" == "$today" ]]; then
    log_timer "skip: successful run already completed today"
    exit 0
  fi
fi

agent=''
agent_bin=''
case "$AGENT_SETTING" in
  codex) agent=codex; agent_bin="$(find_codex || true)" ;;
  claude) agent=claude; agent_bin="$(find_claude || true)" ;;
  auto)
    if agent_bin="$(find_codex)"; then
      agent=codex
    elif agent_bin="$(find_claude)"; then
      agent=claude
    else
      agent=auto
    fi
    ;;
  *)
    printf 'DUDE_AGENT must be codex, claude or auto, got %s\n' "$AGENT_SETTING" >&2
    exit 2
    ;;
esac
if [[ -z "$agent_bin" ]]; then
  log_timer "failure: agent CLI ($AGENT_SETTING) was not found"
  printf 'Agent CLI (%s) was not found. Install Codex or Claude Code, or set CODEX_BIN / CLAUDE_BIN.\n' \
    "$AGENT_SETTING" >&2
  exit 1
fi

if [[ ! -r "$PROMPT_FILE" ]]; then
  log_timer "failure: runner prompt is missing"
  exit 1
fi

run_stamp="$(date +%F_%H-%M-%S)$log_suffix"
run_log="$LOG_DIR/$run_stamp.log"
summary_file="$LOG_DIR/$run_stamp-summary.md"
before_urls="$(mktemp "$LOG_DIR/.before-urls.XXXXXX")"
after_urls="$(mktemp "$LOG_DIR/.after-urls.XXXXXX")"
single_source_prompt=''
trap 'rm -f -- "$before_urls" "$after_urls"; if [[ -n "$single_source_prompt" ]]; then rm -f -- "$single_source_prompt"; fi' EXIT
collect_vacancy_urls > "$before_urls"

if [[ -n "$source_url" ]]; then
  single_source_prompt="$(mktemp "$LOG_DIR/.single-source-prompt.XXXXXX")"
  cp -- "$PROMPT_FILE" "$single_source_prompt"
  {
    printf '\nSingle-source override for this independent run:\n'
    printf 'Scan ONLY %s. Do not scan other job boards.\n' "$source_url"
    printf '%s\n' \
      'You may open employer application pages linked from this source to verify its vacancies.' \
      'Skip source-specific procedures for other sources. Report other sources as outside this run, not unavailable.' \
      'Do not backfill, recheck or archive existing entries from other sources.' \
      'Preserve all other source checkpoints and the global daily-run checkpoint; record this source coverage separately in data/checkpoint.md.' \
      'Discover and save useful access methods for this new source. Keep all normal candidate filters and CV requirements.' \
      'Identify this as an independent single-source scan in the final summary.'
  } >> "$single_source_prompt"
  PROMPT_FILE="$single_source_prompt"
fi

model_label="${MODEL:-$agent-default}"
effort_label="${EFFORT}"

if [[ "$dry_run" == true ]]; then
  printf 'decision=run\n'
  printf 'project=%s\n' "$DUDE_DIR"
  printf 'agent=%s\n' "$agent"
  printf 'agent_bin=%s\n' "$agent_bin"
  printf 'model=%s\n' "$model_label"
  printf 'effort=%s\n' "$effort_label"
  printf 'source=%s\n' "$scan_source"
  printf 'prompt=%s\n' "$PROMPT_FILE"
  printf 'log=%s\n' "$run_log"
  printf 'summary=%s\n' "$summary_file"
  exit 0
fi

# Build the agent command. Only the browser MCP is exposed to the scan.
agent_args=()
if [[ "$agent" == codex ]]; then
  if ! mcp_overrides="$(python3 "$DUDE_DIR/scripts/scan_mcp_config.py" "$agent_bin")"; then
    log_timer "failure: could not isolate scan MCP tools"
    exit 1
  fi
  # Quoted per-plugin overrides still load plugin MCPs in Codex 0.165.0.
  agent_args=(exec --disable plugins)
  if [[ -n "$mcp_overrides" ]]; then
    while IFS= read -r override; do
      agent_args+=(--config "$override")
    done <<< "$mcp_overrides"
  fi
  [[ -n "$MODEL" ]] && agent_args+=(--model "$MODEL")
  [[ "$EFFORT" != none ]] && agent_args+=(--config "model_reasoning_effort=\"$EFFORT\"")
  agent_args+=(
    --config 'sandbox_workspace_write.network_access=true'
    --json --skip-git-repo-check --approve-for-me --cd "$DUDE_DIR"
    --output-last-message "$summary_file"
  )
else
  agent_args=(
    -p --output-format stream-json --verbose
    --permission-mode dontAsk
    --allowedTools Bash Read Write Edit Glob Grep WebFetch WebSearch mcp__playwright
    --disallowedTools 'Read(./.env)' 'Read(./.env.*)' 'Read(./.telegram_*)' 'Read(./logs/**)'
    'Bash(git:*)'
    --strict-mcp-config
  )
  if [[ -r "$DUDE_DIR/config/mcp.json" ]]; then
    agent_args+=(--mcp-config "$DUDE_DIR/config/mcp.json")
  fi
  [[ -n "$MODEL" ]] && agent_args+=(--model "$MODEL")
  [[ "$EFFORT" != none ]] && agent_args+=(--effort "$EFFORT")
  [[ -n "$MAX_BUDGET_USD" ]] && agent_args+=(--max-budget-usd "$MAX_BUDGET_USD")
fi

# run_agent SECONDS [RESUME_ID] < prompt
run_agent() {
  local seconds="$1"
  local resume="${2:-}"
  local args=("${agent_args[@]}")
  if [[ -n "$resume" && "$agent" == codex ]]; then
    args+=(resume "$resume" -)
  elif [[ -n "$resume" ]]; then
    args+=(--resume "$resume")
  elif [[ "$agent" == codex ]]; then
    args+=(-)
  fi
  local code=0
  timeout --signal=TERM --kill-after=2m "${seconds}s" "$agent_bin" "${args[@]}" \
    >> "$run_log" 2>&1 || code=$?
  if [[ "$agent" == claude ]]; then
    python3 "$DUDE_DIR/scripts/agent_events.py" summary "$run_log" "$summary_file" || true
  fi
  return "$code"
}

agent_version="$("$agent_bin" --version 2>/dev/null | head -n 1 || printf 'unknown')"
log_timer "start: vacancy scan; source=$scan_source; agent=$agent; bin=$agent_bin; version=$agent_version; model=$model_label; effort=$effort_label"

{
  printf 'agent=%s\n' "$agent"
  printf 'agent_bin=%s\n' "$agent_bin"
  printf 'version=%s\n' "$agent_version"
  printf 'model=%s\n' "$model_label"
  printf 'reasoning_effort=%s\n\n' "$effort_label"
  printf 'source=%s\n\n' "$scan_source"
} > "$run_log"

set +e
if [[ "$agent" == codex ]]; then
  timeout 20s "$agent_bin" sandbox \
    --config 'permissions.scan.extends=":workspace"' \
    --permission-profile scan \
    --cd "$DUDE_DIR" \
    -- /bin/bash -c 'test -r prompts/task.md && test -r config/profile.md' \
    >> "$run_log" 2>&1
else
  # Claude Code has no standalone sandbox probe; check that the CLI starts.
  timeout 20s "$agent_bin" --version >> "$run_log" 2>&1
fi
exit_code=$?
set -e

if [[ "$check_sandbox" == true ]]; then
  cat -- "$run_log"
  printf 'sandbox_check_exit_code=%s\n' "$exit_code"
  exit "$exit_code"
fi

if (( exit_code != 0 )); then
  printf 'Scan not run: preflight check exited with code %s. See %s.\n' \
    "$exit_code" "$run_log" > "$summary_file"
else
  if ! python3 "$DUDE_DIR/scripts/telegram_notify.py" --prepare >> "$LOG_DIR/timer.log" 2>&1; then
    log_timer "Telegram baseline failed; see timer.log"
    exit 1
  fi
  if ! python3 "$DUDE_DIR/scripts/telegram_notify.py" --retry >> "$LOG_DIR/timer.log" 2>&1; then
    log_timer "Telegram retry failed; messages remain queued"
  fi

  python3 "$DUDE_DIR/scripts/scan_context.py" >> "$run_log" 2>&1

  scan_started=$SECONDS
  exit_code=0
  run_agent "$((SCAN_MINUTES * 60))" < "$PROMPT_FILE" || exit_code=$?

  # A partial answer can mean the model stopped before trying the saved recipes.
  # Resume the exact session, with a shared deadline and a bounded number of retries.
  if [[ "$companies" != true && -z "$source_url" ]] && (( exit_code == 0 )); then
    session_id="$(python3 "$DUDE_DIR/scripts/agent_events.py" session "$run_log")"
    for attempt in 1 2; do
      if ! grep -Eq '^Not scanned:|^Scan partially complete' "$summary_file" 2>/dev/null; then
        break
      fi
      if [[ -z "$session_id" ]]; then
        log_timer "failure: cannot resume partial scan without a session ID"
        exit_code=1
        break
      fi
      remaining=$((SCAN_MINUTES * 60 - (SECONDS - scan_started)))
      if (( remaining <= 0 )); then
        exit_code=124
        break
      fi
      log_timer "continuing partial regular scan: attempt=$attempt; session=$session_id"
      run_agent "$remaining" "$session_id" <<'PROMPT' || exit_code=$?
The regular scan is not finished. Continue the same run: for each incomplete source, perform
the saved direct recipe, remaining terms and pagination within the page budget from
config/profile.md, and the required browser fallback if not yet attempted. Read page counters from
the checkpoint; never reset them across queries, methods or turns. Skip capped sources and report
their bounded coverage as a limitation, not a retryable gap. Prefer newest-first ordering where
supported. Screen records and verify eligible candidates. Do not repeat methods already proven
blocked with the same permissions. A source may remain incomplete only after its applicable access
methods were attempted or a concrete blocker prevents completion. Work through all remaining sources
before stopping; do not stop merely because the first discovery pass is incomplete. Update the
checkpoint and final summary for the entire run, including vacancies added or archived in earlier
turns. Preserve all existing statuses and report concrete blockers honestly.
PROMPT
      (( exit_code == 0 )) || break
    done
  fi
fi

# CLI exit 0 only means the conversation ended, not that the scan ran.
if (( exit_code == 0 )) && ! python3 - "$summary_file" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
markers = ('Scan complete.', 'Scan partially complete.')
sys.exit(0 if path.is_file() and path.read_text().lstrip().startswith(markers) else 1)
PY
then
  exit_code=1
  log_timer "failure: missing scan-completion summary; see $summary_file"
fi

notify_run_summary() {
  if ! python3 "$DUDE_DIR/scripts/telegram_notify.py" --run-summary \
    --summary-file "$summary_file" --run-log "$run_log" --exit-code "$exit_code" \
    >> "$LOG_DIR/timer.log" 2>&1; then
    log_timer "Telegram run summary failed; queued messages will retry on the next run"
  fi
}

if (( exit_code == 0 )); then
  collect_vacancy_urls > "$after_urls"
  new_count="$(comm -13 "$before_urls" "$after_urls" | sed '/^$/d' | wc -l)"
  new_count="${new_count//[[:space:]]/}"
  if [[ -z "$source_url" ]]; then
    printf '%s\n' "$today" > "$STATE_FILE"
  fi
  log_timer "success: output saved to $summary_file"
  if ! python3 "$DUDE_DIR/scripts/telegram_notify.py" --send >> "$LOG_DIR/timer.log" 2>&1; then
    log_timer "Telegram delivery failed; queued messages will retry on the next run"
  fi
  notify_run_summary
  if (( new_count > 0 )); then
    notify_user \
      "New jobs: $new_count" \
      "New shit has come to light, man. See NEW.md."
  fi
  exit 0
fi

if (( exit_code == 124 )); then
  log_timer "failure: agent run exceeded ${SCAN_MINUTES} minutes; see $run_log"
else
  log_timer "failure: agent exited with code $exit_code; see $run_log"
fi
notify_run_summary
notify_user \
  "Job scan failed" \
  "This aggression will not stand, man. See logs/."
exit "$exit_code"

}
