import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import telegram_notify as notifier


def vacancy(url, status='NEW', details='Python & Go'):
    return f'''### Example — Backend Engineer — 9/10

- Status: `{status}`
- Published: 2026-10-12
- Location: Europe; remote
- Vacancy: {url}
- Fit: {details}
- Concerns: verify work eligibility
- CV: backend, cv/backend.pdf. Reason: platform focus.
'''


def report(active='', archive=''):
    return f'# Relevant vacancies\n\n## Active shortlist\n\n{active}\n## Archived\n\n{archive}'


class Notifications(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.result = self.directory / 'NEW.md'
        self.result.write_text(report(archive=vacancy('https://example.org/old')))
        notifier.prepare(self.directory)
        self.config = patch.object(notifier, 'settings', return_value={'TG_BOT_TOKEN': 'test'})
        self.chat = patch.object(notifier, 'recipient', return_value='123')
        self.config.start()
        self.chat.start()
        self.addCleanup(self.config.stop)
        self.addCleanup(self.chat.stop)

    def test_baseline_includes_separate_archive(self):
        (self.directory / '.telegram_state.json').unlink()
        (self.directory / 'APPLIED.md').write_text(
            vacancy('https://example.org/separate-archive', 'APPLIED'))
        notifier.prepare(self.directory)
        state = json.loads((self.directory / '.telegram_state.json').read_text())
        self.assertIn('https://example.org/separate-archive', state['seen'])

    def test_new_active_only_and_no_repeat(self):
        self.result.write_text(report(
            vacancy('https://example.org/new') + vacancy('https://example.org/applied', 'APPLIED'),
            vacancy('https://example.org/old') + vacancy('https://example.org/archived'),
        ))
        with patch.object(notifier, 'api') as send:
            notifier.deliver(self.directory)
            notifier.deliver(self.directory)
        self.assertEqual(send.call_count, 1)
        message = send.call_args.args[2]['text']
        for text in (notifier.VACANCY_HEADER, 'Backend Engineer', '9/10', 'Published:',
                     'Location:', 'Fit:', 'Concerns:', 'CV: backend'):
            self.assertIn(text, message)
        self.assertNotIn('https://example.org/old', message)

    def test_failed_delivery_retries_after_status_becomes_reviewed(self):
        self.result.write_text(report(vacancy('https://example.org/new')))
        with patch.object(notifier, 'api', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                notifier.deliver(self.directory)
        self.result.write_text(report(vacancy('https://example.org/new', 'REVIEWED')))
        with patch.object(notifier, 'api') as send:
            notifier.deliver(self.directory, enqueue=False)
        self.assertEqual(send.call_count, 1)
        state = json.loads((self.directory / '.telegram_state.json').read_text())
        self.assertEqual(state['pending'], {})

    def test_partial_delivery_resumes_without_repeating_first_chunk(self):
        self.result.write_text(report(vacancy('https://example.org/new', details='🚀' * 5000)))
        with patch.object(notifier, 'api', side_effect=[{}, RuntimeError('offline')]) as send:
            with self.assertRaises(RuntimeError):
                notifier.deliver(self.directory)
        first = send.call_args_list[0].args[2]['text']
        with patch.object(notifier, 'api') as retry:
            notifier.deliver(self.directory, enqueue=False)
        for call in retry.call_args_list:
            message = call.args[2]['text']
            self.assertNotEqual(message, first)
            self.assertLessEqual(len(message.encode('utf-16-le')) // 2, 4096)

    def test_archived_pending_vacancy_is_not_sent(self):
        self.result.write_text(report(vacancy('https://example.org/new')))
        with patch.object(notifier, 'api', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                notifier.deliver(self.directory)
        self.result.write_text(report(archive=vacancy('https://example.org/new', 'SKIP')))
        with patch.object(notifier, 'api') as send:
            notifier.deliver(self.directory, enqueue=False)
        send.assert_not_called()

    def run_files(self, summary='Scan complete.\nNew: 0 | Archived: 0', usage=True):
        summary_file = self.directory / 'run-summary.md'
        summary_file.write_text(summary)
        run_log = self.directory / 'run.log'
        run_log.write_text('model=requested-model\nreasoning_effort=low\n'
                           'model: actual-model\nreasoning effort: medium\n'
                           + ('tokens used\n132,863\n' if usage else ''))
        return summary_file, run_log

    def test_zero_jobs_summary_uses_actual_metadata_and_is_not_repeated(self):
        summary_file, run_log = self.run_files(
            'Scan complete.\n- New: **0** | Archived: 0\n'
            'Updated [`NEW.md`](/local/NEW.md).')
        with patch.object(notifier, 'api') as send:
            notifier.enqueue_run(self.directory, summary_file, run_log, 0)
            notifier.deliver(self.directory, enqueue=False)
            notifier.enqueue_run(self.directory, summary_file, run_log, 0)
            notifier.deliver(self.directory, enqueue=False)
        self.assertEqual(send.call_count, 1)
        message = send.call_args.args[2]['text']
        for text in (notifier.ZERO_HEADER, 'New: 0 | Archived: 0', 'Updated NEW.md.',
                     'actual-model / medium | CLI tokens: 132,863'):
            self.assertIn(text, message)
        self.assertNotIn('/local/', message)

    def test_summary_partial_delivery_retries_without_repeating_chunks(self):
        summary_file, run_log = self.run_files('Scan complete.\n' + '🚀' * 5000)
        notifier.enqueue_run(self.directory, summary_file, run_log, 0)
        with patch.object(notifier, 'api', side_effect=[{}, RuntimeError('offline')]) as send:
            with self.assertRaises(RuntimeError):
                notifier.deliver(self.directory, enqueue=False)
        first = send.call_args_list[0].args[2]['text']
        notifier.enqueue_run(self.directory, summary_file, run_log, 0)
        with patch.object(notifier, 'api') as retry:
            notifier.deliver(self.directory, enqueue=False)
        self.assertGreater(retry.call_count, 0)
        for call in retry.call_args_list:
            message = call.args[2]['text']
            self.assertNotEqual(message, first)
            self.assertLessEqual(len(message.encode('utf-16-le')) // 2, 4096)
        state = json.loads((self.directory / '.telegram_state.json').read_text())
        self.assertEqual(state['pending_runs'], {})

    def test_compact_summary_has_counts_and_one_metadata_line(self):
        summary_file, run_log = self.run_files(
            'Scan complete.\nNew: 1 | Archived: 0\n'
            'Scanned: nodesk.co\nNot scanned: trulyremote.co\nReasons: DNS failure')
        message = notifier.run_message(summary_file, run_log, 0)
        self.assertEqual(message,
            'Run: run\n\nScan complete.\nNew: 1 | Archived: 0\n'
            'Scanned: nodesk.co\nNot scanned: trulyremote.co\nReasons: DNS failure\n\n'
            'actual-model / medium | CLI tokens: 132,863')

    def test_failed_scan_does_not_report_success_or_invent_tokens(self):
        summary_file, run_log = self.run_files(usage=False)
        for code, expected in ((124, 'time limit exceeded'), (1, 'exit code 1')):
            with self.subTest(code=code):
                message = notifier.run_message(summary_file, run_log, code)
                self.assertTrue(message.startswith(notifier.FAILURE_HEADER))
                self.assertIn(expected, message)
                self.assertIn('CLI tokens: n/a', message)
                self.assertNotIn('Scan complete.', message)

    def test_company_summaries_are_labeled_including_failures(self):
        summary_file, run_log = self.run_files()
        with run_log.open('a') as stream:
            stream.write('source=companies\n')
        for code in (0, 124):
            with self.subTest(code=code):
                message = notifier.run_message(summary_file, run_log, code)
                self.assertIn('Scope: company watchlist\n', message)
                self.assertEqual(message.count('actual-model / medium'), 1)

    def test_json_usage_sums_turns_without_double_counting_cache_or_reasoning(self):
        summary_file, run_log = self.run_files()
        with run_log.open('a') as stream:
            stream.write('{invalid json\n')
            stream.write(json.dumps({'type': 'item.completed', 'item': {
                'usage': {'input_tokens': 999999}}}) + '\n')
            stream.write(json.dumps({'type': 'turn.completed', 'usage': None}) + '\n')
            for inputs, cached, outputs in ((1000, 800, 100), (2000, 1800, 200)):
                stream.write(json.dumps({'type': 'turn.completed', 'usage': {
                    'input_tokens': inputs, 'cached_input_tokens': cached,
                    'output_tokens': outputs, 'reasoning_output_tokens': 50,
                }}) + '\n')
        message = notifier.run_message(summary_file, run_log, 0)
        self.assertIn('Tokens: 3,300 | in: 3,000 (cached: 2,600) | out: 300', message)
        self.assertNotIn('132,863', message)

    def test_claude_usage_and_cost_are_reported(self):
        summary_file, run_log = self.run_files(usage=False)
        run_log.write_text('model=claude-default\nreasoning_effort=low\n')
        with run_log.open('a') as stream:
            stream.write(json.dumps({'type': 'system', 'subtype': 'init',
                                     'model': 'claude-haiku-test'}) + '\n')
            for cost in (0.25, 0.5):
                stream.write(json.dumps({'type': 'result', 'result': 'x', 'usage': {
                    'input_tokens': 10, 'cache_creation_input_tokens': 5,
                    'cache_read_input_tokens': 100, 'output_tokens': 7,
                }, 'total_cost_usd': cost}) + '\n')
        message = notifier.run_message(summary_file, run_log, 0)
        self.assertIn('claude-haiku-test / low | '
                      'Tokens: 244 | in: 230 (cached: 200) | out: 14 | $0.75', message)

    def test_vacancy_and_summary_are_separate_messages(self):
        self.result.write_text(report(vacancy('https://example.org/new')))
        summary_file, run_log = self.run_files()
        notifier.enqueue_run(self.directory, summary_file, run_log, 0)
        with patch.object(notifier, 'api') as send:
            notifier.deliver(self.directory)
        self.assertEqual(send.call_count, 2)
        self.assertTrue(send.call_args_list[0].args[2]['text'].startswith(notifier.VACANCY_HEADER))
        self.assertIn('Scan complete.', send.call_args_list[1].args[2]['text'])


if __name__ == '__main__':
    unittest.main()
