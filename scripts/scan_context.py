#!/usr/bin/env python3
"""Build a compact lookup index locally, without loading history into the model."""

import csv
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DIRECTORY = Path(__file__).resolve().parent.parent


def canonical(url):
    parts = urlsplit(url.rstrip('.,)'))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'ref', 'source'}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path.rstrip('/'), urlencode(sorted(query)), ''))


def build(directory):
    rows = {}
    for path in (directory / 'APPLIED.md', directory / 'NEW.md'):
        if not path.exists():
            continue
        for block in re.split(r'(?=^### )', path.read_text(), flags=re.M):
            if not block.startswith('### '):
                continue
            title = block.splitlines()[0].removeprefix('### ')
            status = re.search(r'^- Status:\s*`?([A-Z]+)', block, re.M)
            # Include employer links and legacy entries with a URL in the heading.
            for url in re.findall(r'https?://[^\s`<>]+', block):
                rows[canonical(url)] = (title, status[1] if status else 'KNOWN')
    rejections = directory / 'data/rejections.tsv'
    if rejections.exists():
        with rejections.open(newline='') as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                rows.setdefault(canonical(row['url']), (row['company_role'], row['reason']))
    path = directory / 'data/known_jobs.tsv'
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(('url', 'company_role', 'status_or_reason'))
        writer.writerows((url, *row) for url, row in sorted(rows.items()))
    temporary.replace(path)
    return len(rows)


if __name__ == '__main__':
    print(f'Known vacancy index: {build(DIRECTORY)} URLs')
