#!/usr/bin/env python3
"""Portable replacements for GNU-only tools, so dude runs on Linux, macOS and WSL.

epoch-at DATE HOUR                         epoch seconds for DATE (YYYY-MM-DD) at HOUR:00 local time
lock LOCKFILE LOGFILE -- CMD...            run CMD holding an exclusive lock; skip if already held
timeout SECONDS [--kill-after S] -- CMD... run CMD, TERM it after SECONDS, KILL after grace; exit 124
render TEMPLATE OUT [--xml] KEY=VALUE...   replace @KEY@ placeholders (XML-escaped with --xml)
"""

from datetime import datetime
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from xml.sax.saxutils import escape


def split_command(args):
    if '--' not in args:
        sys.exit(__doc__)
    index = args.index('--')
    command = args[index + 1:]
    if not command:
        sys.exit(__doc__)
    return args[:index], command


def epoch_at(day, hour):
    moment = datetime.strptime(f'{day} {int(hour)}', '%Y-%m-%d %H')
    print(int(time.mktime(moment.timetuple())))


def lock(args):
    (lock_file, log_file), command = split_command(args)
    fd = os.open(lock_file, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        with open(log_file, 'a') as stream:
            stream.write(time.strftime('%Y-%m-%dT%H:%M:%S%z') + ' another run is already active\n')
        sys.exit(0)
    # The lock belongs to the open file, which stays open across exec.
    os.set_inheritable(fd, True)
    os.environ['DUDE_LOCK_HELD'] = '1'
    os.execvp(command[0], command)


def run_with_timeout(args):
    options, command = split_command(args)
    seconds = float(options[0])
    grace = float(options[options.index('--kill-after') + 1]) if '--kill-after' in options else 120
    process = subprocess.Popen(command, start_new_session=True)

    def forward(signum, _frame):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    try:
        code = process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        forward(signal.SIGTERM, None)
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            forward(signal.SIGKILL, None)
            process.wait()
        return 124
    return 128 - code if code < 0 else code


def render(args):
    template, out, *pairs = args
    xml = '--xml' in pairs
    text = Path(template).read_text()
    for pair in pairs:
        if pair == '--xml':
            continue
        key, _, value = pair.partition('=')
        text = text.replace(f'@{key}@', escape(value) if xml else value)
    Path(out).write_text(text)


def main(argv):
    if len(argv) == 3 and argv[0] == 'epoch-at':
        epoch_at(argv[1], argv[2])
    elif argv[:1] == ['lock']:
        lock(argv[1:])
    elif argv[:1] == ['timeout']:
        sys.exit(run_with_timeout(argv[1:]))
    elif argv[:1] == ['render'] and len(argv) >= 3:
        render(argv[1:])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
