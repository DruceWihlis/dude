import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from scan_context import build, canonical


class Index(unittest.TestCase):
    def test_canonical_strips_tracking_but_preserves_job_id(self):
        self.assertEqual(canonical('https://EXAMPLE.org/job/?id=42&utm_source=board#apply'),
                         'https://example.org/job?id=42')

    def test_archive_legacy_urls_status_and_rejections_survive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'APPLIED.md').write_text(
                '### Legacy https://example.org/old?utm_source=board\n- Status: `APPLIED`\n')
            (root / 'NEW.md').write_text(
                '## Active shortlist\n### New role\n- Status: `NEW`\n'
                '- Vacancy: https://example.org/new\n')
            (root / 'data/rejections.tsv').write_text(
                'url\tcompany_role\treason\nhttps://example.org/no\tNo role\tUS only\n'
                'https://example.org/old\tOld role\told rejection\n')
            self.assertEqual(build(root), 3)
            with (root / 'data/known_jobs.tsv').open() as stream:
                rows = {r['url']: r for r in csv.DictReader(stream, delimiter='\t')}
            self.assertEqual(rows['https://example.org/old']['status_or_reason'], 'APPLIED')
            self.assertEqual(rows['https://example.org/new']['status_or_reason'], 'NEW')
            self.assertEqual(rows['https://example.org/no']['status_or_reason'], 'US only')

    def test_fresh_install_builds_empty_index(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(build(Path(folder)), 0)
            self.assertTrue((Path(folder) / 'data/known_jobs.tsv').exists())


if __name__ == '__main__':
    unittest.main()
