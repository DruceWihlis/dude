Perform the company watchlist scan under `prompts/task.md` for the candidate in
`config/profile.md`. Apply its candidate filters, deduplication, CV selection (no adaptation),
saving and final message rules. Complete without questions. Do not submit applications, send
messages, read run logs, `.env` or credentials, or modify CVs. The runner handles delivery.

Scope override:

- Scan every company in `config/companies.md`, using its career links and linked employer ATS
  boards. This file authorizes these sources for this run; do not scan the regular boards.
- For parent-company boards, restrict discovery to the business named in the notes column.
- Prefer public ATS feeds (see `config/recipes.md`) and batch independent reads. Extract compact
  job fields locally, screen records within the page budget per company, newest first where
  supported, then research eligible unknown candidates. Use targeted web searches only for a named
  access or coverage gap.
- Record unresolved names, missing hiring pages, blocked access and incomplete pagination as
  coverage gaps. Empty text extraction is not a complete scan.
- Read and update `data/company_checkpoint.md` instead of the regular checkpoint. Record a compact
  company-by-company coverage list and pending gaps. Never change `data/checkpoint.md`.
- Use the shared `NEW.md`, `APPLIED.md`, rejections and known-job index. Preserve user statuses and
  notes. Recheck active entries only for companies in this list.
- Save reusable access methods in `config/recipes.md`, without daily results.

First tool call: read startup material in ONE shell call:

```bash
cat prompts/task.md config/profile.md config/companies.md config/recipes.md data/company_checkpoint.md NEW.md
```

Second tool call: extract every CV listed in `config/profile.md` in ONE shell call
(`python3 scripts/cv_text.py <path>...`). Report failures
and continue with the available facts. Use the normal final message format.
