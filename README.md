<p align="center">
  <img src="assets/banner.svg" width="100%"
       alt="dude: That cron really tied the job search together.">
</p>

# dude

[![tests](https://github.com/drucewihlis/dude/actions/workflows/tests.yml/badge.svg)](https://github.com/drucewihlis/dude/actions/workflows/tests.yml)

> The Dude abides. The cron hunts.

A lazy, local AI job-search daemon that pings you on Telegram.

Every morning a systemd timer wakes up an AI agent: [Codex CLI](https://github.com/openai/codex)
or [Claude Code](https://github.com/anthropics/claude-code), whichever you have. It reads your profile and CVs, walks your list of job boards, throws out what you've already seen,
checks each promising vacancy on the employer's page, and writes a scored shortlist to `NEW.md`.
Then it pings you on Telegram. You read it over coffee. In a bathrobe, ideally.

```text
🎳 New shit has come to light, man.

Example Corp — Senior Backend Engineer — 8/10

• Status: NEW
• Published: 2026-11-10
• Location: EU; remote
• Vacancy: https://jobs.example.com/123
• Fit: Python + Kafka platform team, matches the last 4 years
• Concerns: on-call rotation not described
• CV: backend, cv/backend.pdf. Reason: platform focus
```

## What it does

- **Runs while you sleep.** A systemd user timer starts the scan at a set hour. If the laptop was
  asleep, the scan catches up when it wakes, until a cutoff hour. One successful run per day.
- **Scans your sources, not "the internet".** You approve a list of boards. The agent uses public
  feeds and APIs where it can and a headless browser where it must, within a page budget per source.
- **Remembers.** Applied, skipped and rejected jobs go into a local index. The agent checks it
  before opening a vacancy, so you never see the same job twice.
- **Verifies.** Each candidate is checked on the employer's page for date, allowed countries,
  remote policy and whether it is still open. A board's "worldwide" label doesn't count.
- **Picks the CV.** When you have several CVs, it notes which one fits each vacancy and why.
- **Learns access recipes.** Working endpoints and workarounds for each board go into
  `config/recipes.md`, so the next run is faster and cheaper.
- **Reports honestly.** Every run ends with a short summary: what was scanned, what was capped and
  what failed. A partial scan says so. It never claims full coverage it didn't get.
- **Shows the bill.** Each run summary in Telegram ends with the model, effort and tokens spent
  (plus the USD cost on Claude Code), so you always know what the Dude's habit costs.

It never applies, never messages employers and never edits your CVs. It finds jobs. The rest is
up to you, man.

## How it works

After each run the bot also sends a summary:

```text
🎳 Mark it zero.
Run: 2026-11-12_05-00-03

Scan complete.
New: 0 | Archived: 1
Scanned: weworkremotely.com, himalayas.app, trulyremote.co, web3.career
Coverage: bounded
Limits: himalayas.app — 3 pages, cap reached

gpt-6-luna / low | Tokens: 412,880 | in: 401,233 (cached: 362,112) | out: 11,647
```

```text
systemd timer ──▶ dude.sh ──▶ codex exec  or  claude -p
                     │            │
                     │            ├─ reads  config/profile.md, cv/*.pdf, config/sources.md
                     │            ├─ checks data/known_jobs.tsv before opening anything
                     │            └─ writes NEW.md, APPLIED.md, data/, config/recipes.md
                     │
                     └─▶ telegram_notify.py ──▶ one message per new job + a run summary
```

- `dude.sh` handles scheduling, locking, catch-up, the preflight check, resuming a partial scan
  and the time limit. The agent only does the scan.
- Your Telegram token is never passed to the agent's environment. Delivery is done by a plain
  Python script after the agent exits.
- **Codex** runs in its workspace sandbox with network access on. Unrelated MCP servers from your
  Codex config are disabled for the scan; only `playwright` and `node_repl` stay on.
- **Claude Code** runs headless (`-p`) in `dontAsk` mode with an explicit tool allowlist, reads of
  `.env`, `.telegram_*` and `logs/` denied, and git commands blocked. MCP servers come only from
  `config/mcp.json` (`--strict-mcp-config`), which ships with Playwright. Claude Code has no OS
  sandbox in this mode: run dude as a user that has nothing else worth reading, or enable
  [Claude Code sandboxing](https://docs.anthropic.com/en/docs/claude-code/sandboxing) in your
  settings.

## Pick your agent

| | Codex CLI | Claude Code |
| --- | --- | --- |
| Select | `DUDE_AGENT=codex` | `DUDE_AGENT=claude` |
| Login | `codex login` | `claude` once, then `/login` |
| Isolation | Workspace sandbox | Tool allowlist + deny rules |
| Browser | Playwright MCP from your Codex config | `config/mcp.json` |
| Spend cap | Time limit | Time limit + `DUDE_MAX_BUDGET_USD` |
| Telegram stats | Tokens | Tokens + USD cost |

`DUDE_AGENT=auto` (the default) uses Codex if it is installed, otherwise Claude Code.

## Keep it cheap

A scan is mostly reading: feeds, listings and job pages, many times over. That is a job for a small
model with little thinking, not a frontier model at full effort. Start here:

| Agent | `DUDE_MODEL` | `DUDE_EFFORT` |
| --- | --- | --- |
| Codex | `gpt-6-luna` | `low` |
| Claude Code | `claude-haiku-5-5` | `low` |

Tips:

- **Watch the run summary.** Every Telegram summary shows tokens in/out and the cached share (and
  dollars on Claude Code). If a run suddenly costs 3x, a board probably changed and the agent is
  flailing: check `logs/` and fix the recipe.
- **Keep the page budget small.** `Page budget` in `config/profile.md` caps discovery pages per
  source. Newest-first sorting plus a daily run means 1–3 pages are usually enough.
- **Let recipes do the work.** A saved JSON feed in `config/recipes.md` costs a fraction of
  rendering the page in a browser. Fewer browser-only sources means fewer tokens.
- **Prune sources** that never produce matches.
- **Cap it.** On Claude Code set `DUDE_MAX_BUDGET_USD`; on both, `DUDE_SCAN_MINUTES` bounds a run.
- Go up to `medium` effort only if the agent keeps misjudging eligibility on a cheap model.

## Requirements

- Linux with systemd user services (GNU `date`, `flock`).
- [Codex CLI](https://github.com/openai/codex) or
  [Claude Code](https://github.com/anthropics/claude-code), logged in.
- Recommended: the [Playwright MCP](https://github.com/microsoft/playwright-mcp) for JavaScript-heavy
  boards (`npx` must be available for the shipped `config/mcp.json`).
- Python 3.9+, `curl`, `pdftotext` (`poppler-utils`).
- A Telegram bot token from [@BotFather](https://t.me/BotFather).

## Setup (~5 min)

```bash
git clone https://github.com/drucewihlis/dude.git && cd dude
scripts/init.sh                 # creates your local config and state files; never overwrites
```

1. **Profile.** Edit `config/profile.md`: who you are, target roles, location rules, filters and
   which CV to use when. The shipped example is a fictional backend engineer; replace it.
2. **CVs.** Drop your PDFs into `cv/` and list them in the profile.
3. **Sources.** Edit `config/sources.md`. `config/recipes.md` already knows how to read the
   example boards.
4. **Telegram.** Put `TG_BOT_TOKEN` in `.env`, send `/start` to your bot, then:
   ```bash
   python3 scripts/telegram_notify.py --setup-test
   ```
5. **First run.**
   ```bash
   ./dude.sh --check-sandbox    # the agent CLI starts (and the Codex sandbox works)
   ./dude.sh --force            # full scan now, ignoring the schedule
   ```
6. **Schedule it.**
   ```bash
   scripts/install_timer.sh     # daily at DUDE_SCAN_HOUR; uninstall_timer.sh to remove
   ```

Your profile, sources, CVs, results and state are all git-ignored. `git pull` never touches them.

## Daily use

Open `NEW.md`, change `NEW` to `APPLIED` or `SKIP`, add notes. The next scan keeps your statuses
and moves closed jobs to `APPLIED.md`.

```bash
./dude.sh --dry-run                          # show what would run
./dude.sh --force                            # run now
./dude.sh --source=https://himalayas.app/jobs # one source only (must be in sources.md)
./dude.sh --companies --force                # company watchlist scan
```

## Configuration

All settings live in `.env` (see [`.env.example`](.env.example)). Environment variables override it.

| Setting | Default | Meaning |
| --- | --- | --- |
| `TG_BOT_TOKEN` | | Telegram bot token |
| `TG_CHAT_ID` | auto | Detected from the first `/start`; set it if several chats exist |
| `DUDE_TZ` | system | Timezone for the schedule, e.g. `Europe/Berlin` |
| `DUDE_SCAN_HOUR` | `5` | Hour the daily scan starts |
| `DUDE_CATCHUP_HOUR` | `18` | No catch-up runs after this hour |
| `DUDE_SCAN_MINUTES` | `50` | Time limit per scan, including resumes |
| `DUDE_COMPANY_DAYS` | `1,3,5` | ISO weekdays for the company scan; empty disables it |
| `DUDE_AGENT` | `auto` | `codex`, `claude` or `auto` |
| `DUDE_MODEL` | CLI default | Model for the scan; see [Keep it cheap](#keep-it-cheap) |
| `DUDE_EFFORT` | `low` | Reasoning effort; `none` omits the flag |
| `DUDE_MAX_BUDGET_USD` | | Claude Code only: hard cap per run |
| `CODEX_BIN` / `CLAUDE_BIN` | on `PATH` | Paths to the CLIs |

Change `DUDE_TZ` or `DUDE_SCAN_HOUR`? Run `scripts/install_timer.sh` again.

**Company watchlist.** Copy `config/companies.example.md` to `config/companies.md` and list the
companies you want watched. On `DUDE_COMPANY_DAYS`, a second scan runs right after a successful
regular one, with its own checkpoint.

## Files

| Path | What |
| --- | --- |
| `dude.sh` | The runner |
| `prompts/` | Scan rules and prompts for the agent |
| `config/*.example.*` | Templates for your profile, sources, companies, recipes, MCP servers |
| `scripts/` | Init, timer install, Telegram delivery, known-jobs index, agent helpers |
| `systemd/` | Unit templates and an optional AppArmor profile |
| `assets/` | Banner, square mark and social preview image |
| `NEW.md` / `APPLIED.md` | Your shortlist and archive (local) |
| `data/` | Checkpoints, rejections, known-jobs index (local) |
| `logs/` | Per-run traces and summaries (local) |

## Troubleshooting

- **`--check-sandbox` fails with a user-namespace error on Ubuntu 24.04+.** AppArmor blocks the
  Codex sandbox when it starts from systemd. See `systemd/codex-userns.apparmor`.
- **"Send /start to the bot".** Message the bot once, or set `TG_CHAT_ID`.
- **A board is always "Not scanned".** Run `./dude.sh --force --source=<url>` and read the newest
  file in `logs/`. The agent saves what worked to `config/recipes.md`.
- **Claude Code stops with permission denials.** Headless runs only get the tools listed in
  `dude.sh`. Add an MCP server to `config/mcp.json` and its tools to `--allowedTools`.
- **Nothing found for days.** Mark it zero. Widen the profile filters or add sources.

## Telegram vocabulary

| Message | Means |
| --- | --- |
| 🎳 New shit has come to light, man. | A new vacancy |
| 🎳 Mark it zero. | Scan finished, nothing new |
| 🎳 This aggression will not stand, man. | Scan failed or timed out |

## Tests

```bash
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE). Not affiliated with OpenAI, Anthropic, Telegram or the Coen brothers. Abide responsibly.
