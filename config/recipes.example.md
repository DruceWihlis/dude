# Source access recipes

Technical instructions for the scanning agent: endpoints, access methods, pagination, fields and
filters. The agent appends working methods for new sources here. Keep scan rules, results and
vacancy assessments elsewhere. Replace the example search terms with terms for your target roles.

## General access

- Apply the profile's page budget per source across all queries, methods and resumed turns.
  Prefer supported newest-first sorting; stop at the cap even if more pages or terms remain.
- Prefer public HTTP feeds or HTML; parse responses locally with Python. If sandbox DNS fails,
  retry once with escalated network access where supported (Codex:
  `sandbox_permissions=require_escalated`), then try the Playwright browser.
- Use `curl --fail --silent --show-error --max-time 30`; quote URLs containing `?` or `&`.
- For JavaScript pages, use a hydrated browser and inspect network requests for pagination.

## Public ATS feeds

Most company boards sit on one of these. Prefer the JSON feed over the rendered page.

- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<board>/jobs?content=true`. Fields:
  `jobs[].title`, `location.name`, `updated_at`, `absolute_url`.
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/<board>`. Fields: `jobs[].title`,
  `location`, `isRemote`, `publishedAt`, `jobUrl`, description.
- Lever: `https://api.lever.co/v0/postings/<company>?mode=json`. Fields: `text`,
  `categories.location`, `workplaceType`, `createdAt` (ms), `hostedUrl`.
- Workable and others may require a JS browser; inspect network requests.

## We Work Remotely

- GET https://weworkremotely.com/remote-jobs.rss; parse XML with `xml.etree.ElementTree`.
- Read `channel/item`: `title`, `link`, `guid`, `pubDate`, `region`, `country`, `category`,
  `description`, `expires_at`. Include all categories.
- Use category/archive links if the RSS feed does not reach the freshness window.

## Himalayas

- Browse feed: `https://himalayas.app/jobs/api?limit=20`; follow `nextCursor` using `cursor`.
  Prefer it when returned publication dates confirm newest-first order.
- Search: `https://himalayas.app/jobs/api/search?q=<term>&page=1`. Returns `jobs`, `totalCount`,
  `limit`, `offset`; pages start at 1 and are not date ordered. Deduplicate by `guid`.
- Fields: `title`, `companyName`, `guid`, `applicationLink`, `pubDate`, `expiryDate`,
  `locationRestrictions`, `timezoneRestrictions`, `seniority`, `categories`.
- Search and browse share one page budget.

## Truly Remote

- POST https://trulyremote.co/api/getListing with `Content-Type: application/json` and body
  `{"term":"<term>","locations":[]}`. Empty `locations` includes worldwide roles.
- Read `records[].fields`: `role`, `companyName`, `publishDate`, `lastModifiedOn`,
  `listingSummary`, `useListingRegions`, `roleApplyURL`.
- If `offset` is returned, send it unchanged in the next request with the same term; it may be a
  string. The rendered page may omit job cards from text snapshots; use the API.

## Google Careers

- Start at https://www.google.com/about/careers/applications/jobs/results/?location=Europe and
  follow `page=N` with the same filters.
- Extract the `ds:1` callback from the HTML without evaluating JavaScript:

```python
match = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel:", html, re.S)
if not match:
    raise ValueError('Google ds:1 schema changed')
data = json.loads(match[1])
jobs, total, page_size = data[0], data[2], data[3]
```

- Job fields: ID at 0, title at 1, responsibilities at 3, qualifications at 4, locations at 9,
  description at 10. Use a JS browser if direct extraction fails.

## JetBrains

- GET https://resources.jetbrains.com/storage/greenhouse/greenhouse-data.json and screen `jobs`;
  read `metadata` (`Job Category`), `location`, `offices`, `departments` and job ID.
- Details: `https://job-boards.eu.greenhouse.io/jetbrains/jobs/<id>`.

## Getro boards (Dragonfly, Solana and other investor portfolios)

- Parse `__NEXT_DATA__` JSON at `props.pageProps.initialState.jobs`: `found` holds records with
  `id`, `title`, `organization.name`, `createdAt`, `workMode`, `searchableLocations`, `url`.
- Guessed `?page=2` parameters do not work. Use browser network inspection to find the actual
  load-more request and cursor.

## Other boards

- Remocate: https://www.remocate.app/job-categories/<category> with `?page=N`; search with
  `https://www.remocate.app/?q=<term>` (matches descriptions too).
- NoDesk: parse HTML cards from category pages such as https://nodesk.co/remote-jobs/backend/.
  Its Algolia search returns 403 for public requests.
- Cryptocurrency Jobs: parse HTML cards from https://cryptocurrencyjobs.co/engineering/. Its
  Algolia search returns 403 for public requests.
- Web3.career: extract `tr[data-jobid]` and `time[datetime]`, then follow `rel=next`. The
  `?search=` parameter does not filter.
- CryptoJobsList: category pages such as https://cryptojobslist.com/engineering; use a browser if
  HTTP is blocked.
- Wellfound: parse `__NEXT_DATA__` at `props.pageProps.apolloState.data`; job keys begin with
  `JobListing:`. Inspect actual pagination before using page parameters.

## Web search fallback

Use only for a named coverage gap. Replace `DOMAIN`, the role terms and `AFTER_DATE`:

```text
site:DOMAIN ("Backend Engineer" OR "Platform Engineer") (Europe OR EMEA OR remote OR worldwide) after:AFTER_DATE
```
