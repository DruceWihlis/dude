# Daily vacancy scan

Paths are relative to the repository root. The candidate, target roles, filters, CVs and page
budget are defined in `config/profile.md`.

## Run scope

Regular runs use `config/sources.md` and `data/checkpoint.md`. Company runs use
`config/companies.md` and `data/company_checkpoint.md`; `prompts/companies.md` overrides only the
source scope and checkpoint paths. Candidate filters and CV policy are shared.

## Read once

Read this file, `config/profile.md`, the current run's sources and checkpoint,
`config/recipes.md`, `NEW.md` and every CV listed in the profile
(`python3 scripts/cv_text.py <path>...` reads any format in one call).
Disclose unreadable CVs and continue with the available facts.

Never read `logs/` (including the current live log), scripts, `.env`, `.telegram_*` files or other
credentials. Do not list directories or read the whole archive. The runner builds
`data/known_jobs.tsv` locally; look up candidate URLs and company/title there with `rg -F` or
`grep -F` rather than reading `APPLIED.md`.

## Output budget

Every command's output enters your context, so keep it small. During discovery print only compact
records (title, company, date, location, URL) and counts; never print job descriptions, raw feeds
or HTML. Read a description only for a candidate you are verifying. End every command that may
print a lot with `| head -c 20000`.

## Candidate and filters

Apply the target roles, seniority, stack, location, work-model, language, legal-entity, freshness
and exclusion rules from `config/profile.md`. Judge actual requirements, not the title alone. Never
overstate the candidate's experience: do not count adjacent experience as years in a different
dedicated role.

## Search and verify

Each source gets the page budget from the profile, shared across keywords, categories, APIs,
browser fallbacks and resumed turns. A listing/feed response or Load More batch counts as one page,
including the first page; failed requests also consume a page attempt. Candidate detail pages do
not count. In company runs, each named company has its own budget. Stop earlier when results end or
the freshness window is covered. Never reset the budget by changing access methods, queries or
session turns. Put an explicit remaining-page bound in every pagination loop.

Prefer publication date descending using supported sorting; verify the order from returned dates.
Do not invent sort parameters. If ordering is unavailable, screen the first pages and report that
newest-first coverage is unconfirmed; do not fetch more pages to compensate. When the profile has
several role tracks, share the budget across them: choose one broad feed or query that covers all
tracks where available. Sort retrieved candidates newest first before verification. The page budget
overrides all instructions to exhaust pages or terms, run additional queries, or retry through
another access method after the cap is reached.

Record pages attempted, ordering and whether the cap was reached per source in the checkpoint
before moving on. A continuation is only the runner resuming this same session with a "Continue the
same run" message: then read those counters, spend only the remaining budget and do not revisit
capped sources. Every new run gets a full budget and starts from the newest listings, even when
the checkpoint is from earlier today; old counters are history, not spent budget. Reaching the
page cap is expected bounded coverage, not an access gap requiring retries.

1. Cover every source in the current run using saved recipes. Batch independent searches with short
   output; screen titles, dates, geography and known URLs before opening pages. Use one batched
   discovery pass per source, followed only by targeted queries for a specific coverage gap. No
   generic cross-board searches or repeated equivalent queries. Follow the general access procedure
   at the top of `config/recipes.md`; print compact records and counts, not raw feed/HTML bodies.
   Indexed web search alone cannot establish complete coverage. Apply the saved HTTP/browser
   fallback before declaring an access gap. Complete discovery across sources before candidate
   research. An empty or sparse result allows one targeted fallback for that gap, not repeated
   broad searches.
2. Deduplicate by canonical URL (strip tracking parameters), then by normalized company + title +
   location. Consult `data/known_jobs.tsv` by URL and company/title BEFORE opening or researching a
   candidate. Batch lookups; do not repeat unchanged lookups. Reopen a rejected or archived job only
   with evidence of changed requirements or eligibility; discovery alone is not evidence of a
   change. Add new rejections to `data/rejections.tsv` as URL, company_role, reason
   (tab-separated); do not duplicate unchanged rows. Do not research APPLIED/SKIP entries; closure
   checks cover `NEW.md` only.
3. Open each promising new vacancy. Verify publication date, actually allowed countries, remote
   policy and application status. Prefer linked employer pages where aggregator eligibility is
   ambiguous; a board's "worldwide" label never overrides an employer's country restriction. Stop
   researching once date, eligibility, requirements and application status are established; run
   further queries only for a named missing fact. Extract job fields locally rather than printing
   full HTML/JSON. Compact output must not silently truncate coverage.
4. On a DNS or connection failure, stop the other terms for that source. If the shell is sandboxed
   and your tools support escalation (Codex: `sandbox_permissions=require_escalated`), retry the
   public request once with it; the approval reviewer decides whether to allow it. Do not treat
   sandbox DNS failure as site downtime. If still unavailable, try an available JS browser once.
   Never repeat a failed access method with the same permissions. Empty text extraction proves
   nothing.
5. Recheck active entries for closure or passed deadlines. Move inactive entries to `APPLIED.md`,
   preserving their complete text and user statuses; use EXPIRED only for confirmed closure or a
   passed deadline, and never overwrite a user status.

## Save

`NEW.md` contains only the active shortlist, sorted by score then freshness. Score /10:
role/seniority 0–3, technical stack 0–2, relevant experience evidence 0–2, location/remote 0–2,
freshness/availability 0–1. Keep the `## Active shortlist` heading and use
`### Company — Role — score/10` headings. Each entry includes:

```markdown
### Company — Role — 8/10

- Status: `NEW`
- Published: YYYY-MM-DD
- Location: <allowed countries / regions>; <remote / hybrid / on-site>
- Vacancy: https://...
- Source: <board or company>
- Fit: <one or two lines>
- Concerns: <one or two lines>
- CV: <label from profile>, <path>. Reason: <short reason>
```

Use NEW for newly added entries; preserve REVIEWED/APPLIED/SKIP and all user notes. Select a CV per
the profile's CV rules, but never adapt it: no rewrites, forms or cover letters during scans. Never
invent experience.

Replace the current run's checkpoint with compact state: date, counts, CV access, per-source pages
attempted, ordering, coverage gaps and next action. Preserve other-source and global checkpoints in
single-source runs. The runner saves each run's final summary and trace in `logs/`; do not
duplicate narratives in working files. Keep `config/recipes.md` reusable: save working access
methods there, never daily results.

Write only `NEW.md`, `APPLIED.md`, `data/` and `config/recipes.md`. Never modify CVs or the
profile, submit applications, message employers or handle Telegram delivery. Do not run git
commands. Verify changed blocks only; avoid full-file readbacks and full diffs.

## Final message

Use exactly this short format, with no text before or after it (counts are real; zero means
no new match):

```text
Scan complete.
New: N | Archived: N
Scanned: <each source scanned to its end, freshness boundary or page cap>
Coverage: full
```

If any source hit the cap or lacks confirmed newest-first ordering, replace `Coverage: full` with
`Coverage: bounded` and add `Limits: <source — pages attempted, cap/order limit>`. This alone does
not make the run incomplete and must not trigger continuation. Never describe a capped source as
full freshness coverage.

If coverage is incomplete, start with `Scan partially complete.` instead of `Scan complete.` and
replace `Coverage: full` with these two lines:

```text
Not scanned: <each unscanned or incompletely scanned source by domain or company name>
Reasons: <brief reasons>
```

List every access gap or unfinished source under `Not scanned`; capped sources with verified
candidates belong under `Scanned` and `Limits`. Unfinished candidate verification still makes a
source incomplete, even at the page cap. If no source finished within its budget, write
`Scanned: none`. State CV access failures separately. List only sources in the current run's scope.
Do not repeat job titles, CV choices, updated files or routine checks; details belong in the
checkpoint. Do not invent a rejected-job count. The runner adds timestamp, model, effort and token
usage.
