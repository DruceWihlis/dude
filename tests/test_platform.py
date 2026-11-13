import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from test_dude import BASH, ROOT, copy_template

PORTABLE = [sys.executable, str(ROOT / 'scripts/portable.py')]


class Portable(unittest.TestCase):
    def test_epoch_at_matches_local_time(self):
        out = subprocess.run([*PORTABLE, 'epoch-at', '2026-10-21', '5'], capture_output=True,
                             text=True, check=True).stdout
        expected = time.mktime(time.strptime('2026-10-21 05:00', '%Y-%m-%d %H:%M'))
        self.assertEqual(int(out), int(expected))

    def test_timeout_passes_exit_code_and_stdin(self):
        result = subprocess.run([*PORTABLE, 'timeout', '5', '--', 'sh', '-c', 'cat; exit 3'],
                                input='hello', capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (3, 'hello'))

    def test_timeout_kills_and_returns_124(self):
        started = time.monotonic()
        result = subprocess.run([*PORTABLE, 'timeout', '0.5', '--kill-after', '1', '--',
                                 'sh', '-c', 'trap "" TERM; sleep 30'], capture_output=True)
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.monotonic() - started, 10)

    def test_lock_skips_second_run_and_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            lock, log = Path(folder) / 'lock', Path(folder) / 'timer.log'
            holder = subprocess.Popen([*PORTABLE, 'lock', str(lock), str(log), '--',
                                       'sh', '-c', 'echo held; sleep 5'], stdout=subprocess.PIPE,
                                      text=True)
            self.addCleanup(holder.stdout.close)
            self.addCleanup(holder.wait)
            self.addCleanup(holder.kill)
            self.assertEqual(holder.stdout.readline().strip(), 'held')
            second = subprocess.run([*PORTABLE, 'lock', str(lock), str(log), '--',
                                     'sh', '-c', 'echo second'], capture_output=True, text=True)
            self.assertEqual((second.returncode, second.stdout), (0, ''))
            self.assertIn('another run is already active', log.read_text())

    def test_render_escapes_xml_only_when_asked(self):
        with tempfile.TemporaryDirectory() as folder:
            template, out = Path(folder) / 't', Path(folder) / 'o'
            template.write_text('<a>@DIR@</a>')
            subprocess.run([*PORTABLE, 'render', str(template), str(out), '--xml', 'DIR=/a&b'],
                           check=True)
            self.assertEqual(out.read_text(), '<a>/a&amp;b</a>')
            subprocess.run([*PORTABLE, 'render', str(template), str(out), 'DIR=/a&b'], check=True)
            self.assertEqual(out.read_text(), '<a>/a&b</a>')


class InstallTimer(unittest.TestCase):
    """Runs the installers against recording stubs of systemctl, launchctl and schtasks.exe."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.directory, self.home, self.bin = root / 'dude', root / 'home', root / 'bin'
        for path in (self.directory, self.home, self.bin):
            path.mkdir()
        copy_template(self.directory)
        self.calls = root / 'calls'
        for name in ('systemctl', 'launchctl', 'schtasks.exe'):
            stub = self.bin / name
            stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{self.calls}"\n'
                            'case "$*" in *"/XML "*) cp "$(echo "$*" | sed "s/.*\\/XML //;'
                            's/ \\/F.*//")" "' + str(root / 'task.xml') + '" ;; esac\n')
            stub.chmod(0o755)
        wslpath = self.bin / 'wslpath'
        wslpath.write_text('#!/bin/sh\necho "$2"\n')
        wslpath.chmod(0o755)

    def run_script(self, name, platform, **env):
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(('DUDE_', 'WSL_'))}
        environment.update(HOME=str(self.home), PATH=f'{self.bin}:{os.environ["PATH"]}',
                           DUDE_PLATFORM=platform, **env)
        result = subprocess.run([BASH, str(self.directory / 'scripts' / name)], env=environment,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.calls.read_text() if self.calls.exists() else ''

    def test_linux_renders_systemd_units(self):
        (self.directory / '.env').write_text('DUDE_SCAN_HOUR=7\nDUDE_TZ=Europe/Berlin\n')
        calls = self.run_script('install_timer.sh', 'linux')
        units = self.home / '.config/systemd/user'
        self.assertIn('OnCalendar=*-*-* 07:00:00 Europe/Berlin',
                      (units / 'dude.timer').read_text())
        service = (units / 'dude.service').read_text()
        self.assertIn(f'ExecStart={self.directory}/dude.sh', service)
        self.assertIn(f'Environment="PATH={self.bin}:', service)
        self.assertIn('systemctl --user enable --now dude.timer', calls)
        self.run_script('uninstall_timer.sh', 'linux')
        self.assertFalse((units / 'dude.timer').exists())

    def test_macos_renders_launch_agent(self):
        calls = self.run_script('install_timer.sh', 'macos')
        plist = (self.home / 'Library/LaunchAgents/dude.scan.plist').read_text()
        self.assertIn(f'<string>{self.directory}/scripts/scheduled_run.sh</string>', plist)
        self.assertIn('<integer>3600</integer>', plist)
        self.assertIn('launchctl bootstrap gui/', calls)
        self.assertTrue((self.directory / 'logs').is_dir())
        self.run_script('uninstall_timer.sh', 'macos')
        self.assertFalse((self.home / 'Library/LaunchAgents/dude.scan.plist').exists())

    def test_wsl_registers_utf16_task(self):
        (self.directory / '.env').write_text('DUDE_SCAN_HOUR=6\n')
        calls = self.run_script('install_timer.sh', 'wsl', WSL_DISTRO_NAME='Ubuntu')
        self.assertIn('schtasks.exe /Create /TN dude /XML ', calls)
        task = (Path(self.temp.name) / 'task.xml').read_bytes().decode('utf-16')
        self.assertIn('<StartBoundary>2026-01-01T06:00:00</StartBoundary>', task)
        self.assertIn(f'-d Ubuntu -- /bin/bash "{self.directory}/scripts/scheduled_run.sh"', task)
        self.assertFalse((self.directory / 'logs/.dude-task.xml').exists())
        self.assertIn('schtasks.exe /Delete /TN dude /F',
                      self.run_script('uninstall_timer.sh', 'wsl'))


class ScheduledRun(unittest.TestCase):
    def test_company_hook_runs_only_after_successful_scan(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / 'scripts').mkdir()
            (directory / 'scripts/scheduled_run.sh').write_text(
                (ROOT / 'scripts/scheduled_run.sh').read_text())
            for code in (0, 1):
                (directory / 'dude.sh').write_text(f'echo scan >> "{folder}/order"; exit {code}\n')
                (directory / 'scripts/run_company_scan.sh').write_text(
                    f'echo companies >> "{folder}/order"\n')
                (directory / 'order').unlink(missing_ok=True)
                subprocess.run([BASH, str(directory / 'scripts/scheduled_run.sh')])
                expected = ['scan', 'companies'] if code == 0 else ['scan']
                self.assertEqual((directory / 'order').read_text().split(), expected)


if __name__ == '__main__':
    unittest.main()
