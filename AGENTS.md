# dude

A local job-search runner. `dude.sh` schedules the scans; `prompts/` holds the scan rules; user data
lives in git-ignored `config/*.md`, `cv/`, `NEW.md`, `APPLIED.md`, `data/` and `applications/`.

## Scheduled scans

Runs started by `dude.sh` follow `prompts/scan.md` and `prompts/task.md` only. Ignore the rest of
this file there; never prepare applications during a scan.

## Interactive sessions

- A vacancy link on its own is a request to prepare an application: use the `abide` skill
  (`.agents/skills/abide/SKILL.md`). It drafts; the user submits.
- Never read `.env`, `.telegram_*` or `logs/` unless the user asks for a specific log.

## Developing dude

- Python 3.9+ standard library and bash 3.2 only: the runner must work on Linux, macOS and WSL.
- Run `python3 -m unittest discover -s tests` before committing.
- Keep docs and prompts short; wrap prose at 100 columns.
