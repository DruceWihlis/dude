Perform the daily vacancy scan under `prompts/task.md` for the candidate in `config/profile.md`.
Follow its read-once list, source coverage, verification, CV selection (no adaptation) and final
message rules. Complete without questions. Write only scan results and state.
Do not read `.env`, credentials, `.telegram_*` files or scripts; the runner handles delivery.
Do not submit applications or modify CV files. Never read run logs, including the current live log.
Respect the per-source page budget from the profile across all queries, newest first where
supported; never exhaust a feed beyond the cap. This is a new run with a full budget.

First tool call: read all startup material in ONE shell call, without directory discovery:

```bash
cat prompts/task.md config/profile.md config/sources.md config/recipes.md data/checkpoint.md NEW.md
```

Second tool call: extract every CV listed in `config/profile.md` in ONE shell call
(`pdftotext <path> -` for each PDF, `cat` for text files). Report each failure and continue with
the available facts. Then follow `prompts/task.md`.
