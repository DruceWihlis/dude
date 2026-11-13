---
name: abide
description: Prepare a job application from a vacancy link. Reads the profile and every CV, checks fit, picks a CV, suggests material CV edits, answers each application-form field and drafts a cover letter; saves the drafts to applications/. Never submits. Use when the user sends a vacancy URL, alone or with "apply", "cover letter" or "fill the form".
---

# Abide

Turn one vacancy link into ready-to-paste application drafts. The user reviews and submits; you
never do.

## Rules

- Facts come only from the CVs and `config/profile.md`. Never invent skills, years, numbers,
  employers or opinions. Keep the real scope of each experience: "helped with" stays "helped with".
- If facts conflict, the profile wins over CVs; flag conflicts that affect this application.
- A missing fact becomes a placeholder `[ask: <question>]`, never a guess.
- Never submit forms, create accounts, message anyone or edit CVs, the profile or scan state.
- Do not read `.env`, `.telegram_*` or `logs/`.

## Steps

1. **Read once.** In one shell call: `cat config/profile.md`, then `pdftotext <path> -` for every
   CV listed in it (`cat` for text CVs). Report an unreadable CV and continue with the rest.
2. **Read the vacancy** with `curl` or a web fetch; use the Playwright MCP if the page needs
   JavaScript. Extract responsibilities, requirements, location and eligibility, compensation, and
   the application form: every field with its label, type, options and required flag. If the form
   is on a separate apply page, open it. If it is behind a login, say so and continue without it.
3. **Check fit** against the profile's target roles and filters. Lead with blockers (country,
   work authorization, language, seniority) in one line each. If a hard filter fails, say so and
   ask whether to continue before drafting.
4. **Pick the CV** by the vacancy's actual responsibilities, not past job titles, following the
   profile's CV table:
   `Selected CV: <label>, <path>. Reason: <one sentence>`
5. **CV edits.** Suggest only changes that materially improve the match, as `Before:` (verbatim
   from the selected CV), `After:` and `Reason:`. You may move a true fact from another CV; name
   that CV. Otherwise write `No changes needed.`
6. **Form answers.** One entry per field, in form order: `**<label>**` then the answer. Fill
   choices exactly as offered. Use `## Applications` in the profile for standard facts (right to
   work, notice period, salary, links). Keep free-text answers short and specific to this role.
7. **Cover letter** only if the form has a cover-letter field or the user asks. Three or four
   short paragraphs: why this role, the two or three most relevant facts with concrete results,
   anything the profile says to mention. Do not retell the CV. Use the greeting and sign-off
   from `## Applications`.
8. **Edit.** Run every free-text answer and the cover letter through [writing.md](writing.md),
   then check the result against it once more.
9. **Save** to `applications/<YYYY-MM-DD>-<company>-<role>.md` (lowercase, hyphens), in this
   order: vacancy URL, fit, selected CV, CV edits, form answers, cover letter, open `[ask: ...]`
   questions. Show the same content in chat without a "what changed" section.

When the user says they submitted it, set the vacancy's status to `APPLIED` in `NEW.md` if it is
listed there, and change nothing else.
