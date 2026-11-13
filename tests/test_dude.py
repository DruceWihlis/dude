import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
# CI on macOS sets TEST_BASH=/bin/bash to check compatibility with the stock bash 3.2.
BASH = os.environ.get('TEST_BASH', 'bash')
SOURCE_URL = 'https://weworkremotely.com'


def copy_template(directory):
    """Copy tracked files only, never the developer's local config or data."""
    for folder in ('prompts', 'scripts', 'scheduler'):
        shutil.copytree(ROOT / folder, directory / folder,
                        ignore=shutil.ignore_patterns('__pycache__'))
    (directory / 'config').mkdir()
    for example in (ROOT / 'config').glob('*.example.*'):
        shutil.copy(example, directory / 'config' / example.name)
    for name in ('dude.sh', '.env.example'):
        shutil.copy(ROOT / name, directory / name)


class Runner(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'dude'
        self.directory.mkdir()
        copy_template(self.directory)
        subprocess.run([BASH, str(self.directory / 'scripts/init.sh')], check=True,
                       capture_output=True, text=True)
        shutil.copy(self.directory / 'config/companies.example.md',
                    self.directory / 'config/companies.md')
        self.state = self.directory / '.last_successful_date'
        self.state.write_text('2026-10-12\n')
        (self.directory / 'scripts/telegram_notify.py').write_text(
            'import sys\nfrom pathlib import Path\n'
            'with (Path(__file__).parent.parent / "notifications").open("a") as f:\n'
            ' f.write(" ".join(sys.argv[1:]) + "\\n")\n'
        )
        self.bin = Path(self.temp.name) / 'bin'
        self.bin.mkdir()
        self.codex = self.bin / 'codex'
        self.codex.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
args = sys.argv[1:]
if args[0] == '--version':
    print('codex-test')
elif args[0] == 'sandbox':
    sys.exit(int(os.environ.get('TEST_SANDBOX_EXIT', '0')))
elif args[:2] == ['mcp', 'list']:
    assert args[args.index('--disable') + 1] == 'plugins'
    if os.environ.get('TEST_MCP_LIST_EXIT'):
        sys.exit(int(os.environ['TEST_MCP_LIST_EXIT']))
    print(os.environ.get('TEST_MCP_SERVERS', '[{"name":"node_repl"},{"name":"playwright"},'
          '{"name":"webstorm"},{"name":"pycharm"},{"name":"future-login-server"}]'))
else:
    assert '--json' in args
    print('{"type":"thread.started","thread_id":"test-thread"}')
    if os.environ.get('TEST_BIG_OUTPUT'):
        print('{"type":"item.completed","item":{"type":"command_execution",'
              '"aggregated_output":"' + 'x' * 100000 + '"}}')
    Path('model-args').write_text('\\n'.join(args))
    Path('model-called').touch()
    if os.environ.get('TEST_REWRITE_RUNNER'):
        runner = Path('dude.sh')
        runner.write_text('# added during scan\\n' * 8 + runner.read_text())
    path = Path(args[args.index('--output-last-message') + 1])
    Path('model-prompt').write_text(sys.stdin.read())
    with Path('model-calls').open('a') as stream:
        stream.write(path.name + '\\n')
    if not os.environ.get('TEST_MISSING_SUMMARY'):
        summaries = os.environ.get('TEST_SUMMARIES', '').split('|')
        calls = len(Path('model-calls').read_text().splitlines())
        summary = summaries[min(calls - 1, len(summaries) - 1)] if summaries[0] else \\
            os.environ.get('TEST_SUMMARY', 'Scan complete.\\nNew: 0')
        path.write_text(summary)
    sys.exit(int(os.environ.get('TEST_CODEX_EXIT', '0')))
''')
        self.codex.chmod(0o755)
        (self.bin / 'notify-send').write_text('#!/bin/sh\nexit 0\n')
        (self.bin / 'notify-send').chmod(0o755)
        (self.bin / 'date').write_text('''#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
day = os.environ.get('TEST_RUN_DATE', '2026-10-21')
if args == ['+%F']:
    print(day)
elif args == ['+%F_%H-%M-%S']:
    print(day + '_07-00-00')
elif args == ['+%s']:
    import time
    run_time = os.environ.get('TEST_RUN_TIME', '05:00:00')
    print(int(time.mktime(time.strptime(day + ' ' + run_time, '%Y-%m-%d %H:%M:%S'))))
elif args == ['+%u']:
    import datetime
    print(datetime.date.fromisoformat(day).isoweekday())
else:
    os.execv('/bin/date', ['date', *args])
''')
        (self.bin / 'date').chmod(0o755)

    def env(self, **overrides):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('DUDE_', 'CODEX_', 'CLAUDE_', 'TG_'))}
        env.update(CODEX_BIN=str(self.codex), PATH=f'{self.bin}:{os.environ["PATH"]}',
                   **overrides)
        return env

    def model_calls(self):
        return (self.directory / 'model-calls').read_text().splitlines()

    def run_runner(self, *args, force=True, **overrides):
        return subprocess.run([BASH, str(self.directory / 'dude.sh'),
                               *(['--force'] if force else []), *args],
                              cwd=self.directory, env=self.env(**overrides),
                              capture_output=True, text=True, timeout=10)

    def run_hook(self, **overrides):
        return subprocess.run([BASH, str(self.directory / 'scripts/run_company_scan.sh')],
                              cwd=self.directory, env=self.env(**overrides),
                              capture_output=True, text=True, timeout=10)

    def test_missing_setup_fails_before_scan(self):
        (self.directory / 'config/profile.md').unlink()
        result = self.run_runner()
        self.assertEqual(result.returncode, 2)
        self.assertIn('scripts/init.sh', result.stderr)
        self.assertFalse((self.directory / 'model-called').exists())

    def test_reported_failure_is_not_success_even_with_cli_exit_zero(self):
        result = self.run_runner(TEST_SUMMARY='Scan not run: bwrap failed')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.state.read_text(), '2026-10-12\n')
        notifications = (self.directory / 'notifications').read_text()
        self.assertIn('--exit-code 1', notifications)
        self.assertNotIn('--send\n', notifications)

    def test_late_catch_up_runs_once(self):
        for _ in range(2):
            result = self.run_runner(force=False, TEST_RUN_TIME='18:00:00')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.model_calls()), 1)

    def test_after_catch_up_deadline_skips(self):
        result = self.run_runner(force=False, TEST_RUN_TIME='18:00:01')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.directory / 'model-called').exists())
        self.assertEqual(self.state.read_text(), '2026-10-12\n')

    def test_schedule_comes_from_env_file(self):
        (self.directory / '.env').write_text('DUDE_SCAN_HOUR="7"\nDUDE_CATCHUP_HOUR=9\n')
        self.run_runner(force=False, TEST_RUN_TIME='06:59:00')
        self.assertFalse((self.directory / 'model-called').exists())
        self.run_runner(force=False, TEST_RUN_TIME='07:30:00')
        self.assertTrue((self.directory / 'model-called').exists())

    def test_force_bypasses_catch_up_deadline(self):
        result = self.run_runner(TEST_RUN_TIME='19:00:00')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.directory / 'model-called').exists())

    def test_before_schedule_waits(self):
        self.assertEqual(self.run_runner(force=False, TEST_RUN_TIME='04:59:00').returncode, 0)
        self.assertFalse((self.directory / 'model-called').exists())

    def test_partial_completion_advances_state(self):
        result = self.run_runner(TEST_SUMMARY='Scan partially complete.\nNew: 0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state.read_text(), '2026-10-21\n')
        self.assertEqual(len(self.model_calls()), 3)
        self.assertIn('resume\ntest-thread', (self.directory / 'model-args').read_text())

    def test_resume_stops_when_coverage_is_complete(self):
        result = self.run_runner(TEST_SUMMARIES='Scan complete.\nNot scanned: board|'
                                 'Scan complete.\nCoverage: full')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.model_calls()), 2)

    def test_page_cap_is_success_without_continuation(self):
        result = self.run_runner(TEST_SUMMARY=(
            'Scan complete.\nNew: 0 | Archived: 0\n'
            'Scanned: Himalayas\nCoverage: bounded\n'
            'Limits: Himalayas — 3 pages, cap reached'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state.read_text(), '2026-10-21\n')
        self.assertEqual(len(self.model_calls()), 1)

    def test_access_gap_resumes_but_final_page_cap_does_not(self):
        result = self.run_runner(TEST_SUMMARIES=(
            'Scan partially complete.\nNot scanned: Solana\n'
            'Limits: Himalayas — 3 pages, cap reached|'
            'Scan complete.\nScanned: Himalayas, Solana\nCoverage: bounded\n'
            'Limits: Himalayas — 3 pages, cap reached'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.model_calls()), 2)

    def test_edit_during_scan_preserves_delivery_and_completion(self):
        result = self.run_runner(TEST_REWRITE_RUNNER='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state.read_text(), '2026-10-21\n')
        notifications = (self.directory / 'notifications').read_text()
        self.assertIn('--send\n', notifications)
        self.assertIn('--run-summary', notifications)
        self.assertIn('--exit-code 0', notifications)

    def test_run_log_cuts_huge_command_output_but_keeps_exit_code(self):
        result = self.run_runner(TEST_BIG_OUTPUT='1', TEST_CODEX_EXIT='7')
        self.assertEqual(result.returncode, 7)
        log = next(path for path in (self.directory / 'logs').glob('*.log')
                   if path.name != 'timer.log')
        self.assertLess(log.stat().st_size, 20000)
        self.assertIn('truncated 96000 chars', log.read_text())
        self.assertIn('"thread_id": "test-thread"', log.read_text())

    def test_old_traces_are_removed_but_summaries_and_timer_log_stay(self):
        logs = self.directory / 'logs'
        logs.mkdir(exist_ok=True)
        old = time.time() - 40 * 86400
        for name in ('2026-09-01_05-00-00.log', '2026-09-01_05-00-00-summary.md', 'timer.log'):
            (logs / name).write_text('old\n')
            os.utime(logs / name, (old, old))
        (logs / '2026-10-20_05-00-00.log').write_text('recent\n')
        self.assertEqual(self.run_runner().returncode, 0)
        self.assertFalse((logs / '2026-09-01_05-00-00.log').exists())
        for name in ('2026-09-01_05-00-00-summary.md', 'timer.log', '2026-10-20_05-00-00.log'):
            self.assertTrue((logs / name).exists(), name)

    def test_missing_summary_is_failure(self):
        self.assertEqual(self.run_runner(TEST_MISSING_SUMMARY='1').returncode, 1)
        self.assertEqual(self.state.read_text(), '2026-10-12\n')

    def test_completed_scan_advances_state(self):
        self.assertEqual(self.run_runner().returncode, 0)
        self.assertNotEqual(self.state.read_text(), '2026-10-12\n')

    def test_model_flag_only_when_configured(self):
        self.assertEqual(self.run_runner().returncode, 0)
        self.assertNotIn('--model', (self.directory / 'model-args').read_text())
        self.state.write_text('2026-10-12\n')
        self.assertEqual(self.run_runner(DUDE_MODEL='some-model').returncode, 0)
        self.assertIn('--model\nsome-model\n', (self.directory / 'model-args').read_text())

    def test_telegram_token_never_reaches_agent_environment(self):
        (self.directory / '.env').write_text('TG_BOT_TOKEN=secret\n')
        self.codex.write_text(self.codex.read_text().replace(
            "assert '--json' in args",
            "assert '--json' in args\n    assert 'TG_BOT_TOKEN' not in os.environ"))
        result = self.run_runner()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scan_disables_unrelated_tools_without_removing_browser(self):
        self.assertEqual(self.run_runner().returncode, 0)
        args = (self.directory / 'model-args').read_text()
        self.assertIn('--disable\nplugins\n', args)
        self.assertIn('mcp_servers.webstorm.enabled=false', args)
        self.assertIn('mcp_servers.pycharm.enabled=false', args)
        self.assertIn('mcp_servers.future-login-server.enabled=false', args)
        self.assertNotIn('mcp_servers.node_repl.enabled=false', args)
        self.assertNotIn('mcp_servers.playwright.enabled=false', args)

    def test_unsupported_mcp_name_fails_before_scan(self):
        result = self.run_runner(TEST_MCP_SERVERS='[{"name":"unexpected.name"}]')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.directory / 'model-called').exists())

    def test_mcp_discovery_failure_never_starts_scan(self):
        result = self.run_runner(TEST_MCP_LIST_EXIT='1')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.directory / 'model-called').exists())
        self.assertEqual(self.state.read_text(), '2026-10-12\n')

    def test_no_unrelated_mcps_still_runs(self):
        result = self.run_runner(TEST_MCP_SERVERS='[{"name":"playwright"}]')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_single_source_preserves_daily_state(self):
        self.assertEqual(self.run_runner(f'--source={SOURCE_URL}').returncode, 0)
        self.assertEqual(self.state.read_text(), '2026-10-12\n')
        self.assertTrue((self.directory / 'data/known_jobs.tsv').exists())
        self.assertIn(f'Scan ONLY {SOURCE_URL}', (self.directory / 'model-prompt').read_text())

    def test_unknown_single_source_is_rejected(self):
        result = self.run_runner('--source=https://example.org/')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.directory / 'model-called').exists())

    def test_preflight_failure_never_calls_model(self):
        self.assertEqual(self.run_runner(TEST_SANDBOX_EXIT='78').returncode, 78)
        self.assertFalse((self.directory / 'model-called').exists())
        self.assertEqual(self.state.read_text(), '2026-10-12\n')

    def test_check_mode_does_not_call_model_notify_or_advance_state(self):
        self.assertEqual(self.run_runner('--check-sandbox').returncode, 0)
        self.assertIn('start: sandbox check', (self.directory / 'logs/timer.log').read_text())
        self.assertFalse((self.directory / 'model-called').exists())
        self.assertFalse((self.directory / 'notifications').exists())
        self.assertEqual(self.state.read_text(), '2026-10-12\n')

    def test_nonzero_cli_exit_is_preserved(self):
        self.assertEqual(self.run_runner(TEST_CODEX_EXIT='124').returncode, 124)
        self.assertEqual(self.state.read_text(), '2026-10-12\n')

    def test_company_run_has_own_state_prompt_and_logs(self):
        self.assertEqual(self.run_runner('--companies').returncode, 0)
        self.assertEqual(self.state.read_text(), '2026-10-12\n')
        self.assertEqual((self.directory / '.last_company_successful_date').read_text(),
                         '2026-10-21\n')
        prompt = (self.directory / 'model-prompt').read_text()
        self.assertIn('config/companies.md', prompt)
        self.assertIn('data/company_checkpoint.md', prompt)
        log = self.directory / 'logs/2026-10-21_07-00-00-companies.log'
        self.assertIn('source=companies\n', log.read_text())
        self.assertTrue(log.with_name(log.stem + '-summary.md').exists())

    def test_company_run_requires_watchlist(self):
        (self.directory / 'config/companies.md').unlink()
        self.assertEqual(self.run_runner('--companies').returncode, 2)
        self.assertFalse((self.directory / 'model-called').exists())

    def test_company_guard_is_independent_and_skips_repeat(self):
        self.state.write_text('2026-10-21\n')
        for _ in range(2):
            self.assertEqual(self.run_runner('--companies', force=False).returncode, 0)
        self.assertEqual(len(self.model_calls()), 1)
        self.assertEqual(self.state.read_text(), '2026-10-21\n')

    def test_company_run_does_not_suppress_regular_run(self):
        self.assertEqual(self.run_runner('--companies', force=False).returncode, 0)
        self.assertEqual(self.run_runner(force=False).returncode, 0)
        calls = self.model_calls()
        self.assertEqual(len(calls), 2)
        self.assertIn('-companies-summary.md', calls[0])
        self.assertNotIn('-companies', calls[1])

    def test_failed_company_run_does_not_advance_either_guard(self):
        self.assertEqual(self.run_runner('--companies', TEST_CODEX_EXIT='124').returncode, 124)
        self.assertEqual(self.state.read_text(), '2026-10-12\n')
        self.assertFalse((self.directory / '.last_company_successful_date').exists())

    def test_company_and_single_source_modes_cannot_be_combined(self):
        result = self.run_runner('--companies', f'--source={SOURCE_URL}')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.directory / 'model-called').exists())

    def test_company_dry_run_does_not_execute_or_notify(self):
        result = self.run_runner('--companies', '--dry-run')
        self.assertEqual(result.returncode, 0)
        self.assertIn('source=companies\n', result.stdout)
        self.assertFalse((self.directory / 'model-called').exists())
        self.assertFalse((self.directory / 'notifications').exists())
        self.assertFalse((self.directory / '.last_company_successful_date').exists())

    def test_weekday_hook_runs_only_on_configured_days(self):
        for days, expected in (('', (19, 21, 23)), ('2,4', (20, 22))):
            for day in range(19, 26):
                with self.subTest(days=days, day=day):
                    (self.directory / '.env').write_text(
                        f'DUDE_COMPANY_DAYS={days}\n' if days else '')
                    self.state.write_text(f'2026-10-{day}\n')
                    marker = self.directory / 'model-called'
                    marker.unlink(missing_ok=True)
                    result = self.run_hook(TEST_RUN_DATE=f'2026-10-{day}')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(marker.exists(), day in expected)
                    self.assertEqual(self.state.read_text(), f'2026-10-{day}\n')

    def test_weekday_hook_waits_for_regular_completion(self):
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.directory / 'model-called').exists())
        self.assertEqual(self.state.read_text(), '2026-10-12\n')

    def test_weekday_hook_skips_without_watchlist(self):
        (self.directory / 'config/companies.md').unlink()
        self.state.write_text('2026-10-19\n')
        result = self.run_hook(TEST_RUN_DATE='2026-10-19')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.directory / 'model-called').exists())


CLAUDE_FAKE = """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[0] == '--version':
    print('2.0.0 (Claude Code)')
    sys.exit(0)
assert 'TG_BOT_TOKEN' not in os.environ
Path('claude-args').write_text('\\n'.join(args))
Path('model-called').touch()
Path('model-prompt').write_text(sys.stdin.read())
with Path('model-calls').open('a') as stream:
    stream.write('call\\n')
calls = len(Path('model-calls').read_text().splitlines())
summaries = os.environ.get('TEST_SUMMARIES') or os.environ.get('TEST_SUMMARY', 'Scan complete.\\nNew: 0')
summaries = summaries.split('|')
print(json.dumps({'type': 'system', 'subtype': 'init', 'session_id': 'claude-session',
                  'model': 'claude-test-model'}))
print(json.dumps({'type': 'result', 'subtype': 'success', 'session_id': 'claude-session',
                  'result': summaries[min(calls - 1, len(summaries) - 1)],
                  'usage': {'input_tokens': 10, 'cache_read_input_tokens': 100,
                            'cache_creation_input_tokens': 5, 'output_tokens': 7},
                  'total_cost_usd': 0.25}))
sys.exit(int(os.environ.get('TEST_CODEX_EXIT', '0')))
"""


class ClaudeRunner(Runner):
    """Same runner contract with Claude Code as the agent."""

    def setUp(self):
        super().setUp()
        self.claude = self.bin / 'claude'
        self.claude.write_text(CLAUDE_FAKE)
        self.claude.chmod(0o755)

    def env(self, **overrides):
        env = super().env(**overrides)
        del env['CODEX_BIN']
        env.update(DUDE_AGENT='claude', CLAUDE_BIN=str(self.claude))
        return env

    def claude_args(self):
        return (self.directory / 'claude-args').read_text().splitlines()

    def test_claude_writes_summary_and_uses_safe_flags(self):
        result = self.run_runner(DUDE_MODEL='claude-haiku-test', DUDE_MAX_BUDGET_USD='2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state.read_text(), '2026-10-21\n')
        args = self.claude_args()
        for flag in ('-p', '--strict-mcp-config', 'stream-json', 'dontAsk', 'Read(./.env)'):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index('--model') + 1], 'claude-haiku-test')
        self.assertEqual(args[args.index('--effort') + 1], 'low')
        self.assertEqual(args[args.index('--max-budget-usd') + 1], '2')
        self.assertEqual(args[args.index('--mcp-config') + 1],
                         str(self.directory / 'config/mcp.json'))
        summary = next((self.directory / 'logs').glob('*-summary.md'))
        self.assertEqual(summary.read_text(), 'Scan complete.\nNew: 0')

    def test_claude_effort_none_omits_flag(self):
        self.assertEqual(self.run_runner(DUDE_EFFORT='none').returncode, 0)
        self.assertNotIn('--effort', self.claude_args())

    def test_partial_completion_advances_state(self):
        result = self.run_runner(TEST_SUMMARIES='Scan partially complete.\nNew: 0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.model_calls()), 3)
        args = self.claude_args()
        self.assertEqual(args[args.index('--resume') + 1], 'claude-session')

    def test_company_run_does_not_suppress_regular_run(self):
        self.assertEqual(self.run_runner('--companies', force=False).returncode, 0)
        self.assertEqual(self.run_runner(force=False).returncode, 0)
        self.assertEqual(len(self.model_calls()), 2)
        summaries = sorted(path.name for path in (self.directory / 'logs').glob('*-summary.md'))
        self.assertEqual(len(summaries), 2)

    # Codex-specific behaviour does not apply to Claude Code.
    test_scan_disables_unrelated_tools_without_removing_browser = None
    test_unsupported_mcp_name_fails_before_scan = None
    test_mcp_discovery_failure_never_starts_scan = None
    test_preflight_failure_never_calls_model = None
    test_model_flag_only_when_configured = None
    test_edit_during_scan_preserves_delivery_and_completion = None
    test_reported_failure_is_not_success_even_with_cli_exit_zero = None
    test_missing_summary_is_failure = None
    test_run_log_cuts_huge_command_output_but_keeps_exit_code = None
    test_telegram_token_never_reaches_agent_environment = None


class Init(unittest.TestCase):
    def test_init_never_overwrites_user_files(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            copy_template(directory)
            (directory / 'config/profile.md').write_text('mine\n')
            subprocess.run([BASH, str(directory / 'scripts/init.sh')], check=True,
                           capture_output=True)
            self.assertEqual((directory / 'config/profile.md').read_text(), 'mine\n')
            self.assertIn('## Active shortlist', (directory / 'NEW.md').read_text())
            self.assertEqual(oct((directory / '.env').stat().st_mode & 0o777), '0o600')


if __name__ == '__main__':
    unittest.main()
