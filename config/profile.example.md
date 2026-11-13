# Candidate profile

Everything the agent needs to know about you. Plain English; be specific. The agent treats this
file as the source of truth for filters, scoring and CV choice. This example describes a fictional
backend engineer: replace it with your own.

## Who

- Backend engineer, 6 years: Python (FastAPI, Django), Go, PostgreSQL, Redis, Kafka, AWS, Docker,
  Kubernetes basics, CI/CD with GitHub Actions.
- Based in Lisbon, Portugal. Authorized to work in the EU without sponsorship.
- Timezone: `Europe/Lisbon`. English: fluent. Portuguese: basic.

## Target roles

Priority order:

1. Senior Backend Engineer (Python or Go).
2. Platform / Developer Experience Engineer.
3. Track: junior or associate Data Engineer (career transition). Accept only roles whose actual
   requirements fit junior scope; do not count backend years as data-engineering years.

Exclude: staff / principal roles, pure frontend, management-only roles, on-call-heavy SRE.

## Location and work model

- Remote preferred; hybrid acceptable in Lisbon.
- Accept: Portugal, EU, Europe, EMEA, CET±2 or worldwide. Reject country-only roles outside Portugal
  unless international contracting is explicitly allowed.
- Employment or B2B contract are both fine.

## Other filters

- Reject roles that require fluent Portuguese or any language other than English.
- Freshness: 30 days; up to 60 for unusually strong senior matches.
- Do not use LinkedIn.

## Scan settings

- Page budget: 3 discovery pages per source per run.

## CVs

Files live in `cv/` (git-ignored). The agent reads all of them once per run.

| Label | Path | Use for |
| --- | --- | --- |
| backend | `cv/backend.pdf` | Default for backend and platform roles |
| data | `cv/data.pdf` | Data engineering track |

Choose by the vacancy's actual responsibilities, not by your previous job titles.

## Applications

Used by the `abide` skill when you send it a vacancy link. Scans ignore this section.

- Greeting: `Hi,`. Sign-off: `Best,` then `Alex` on a new line.
- Cover letters: mention that references from former managers are available.
- Right to work: authorized in the EU; no sponsorship needed.
- Notice period: 1 month.
- Salary: EUR 75,000+ gross per year, or the equivalent B2B day rate.
- Links: https://github.com/example, https://example.dev
