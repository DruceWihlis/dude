#!/usr/bin/env python3
"""Read Codex (`--json`) and Claude Code (`stream-json`) event logs.

session LOG          print the session ID to resume (Codex thread or Claude session)
summary LOG OUT      write the last Claude result text to OUT (Codex writes its own)
"""

import json
from pathlib import Path
import sys


def events(path):
    for line in Path(path).read_text(errors='replace').splitlines():
        if not line.startswith('{'):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            yield event


def session(path):
    for event in events(path):
        if event.get('type') == 'thread.started' and event.get('thread_id'):
            return event['thread_id']
        if event.get('type') == 'system' and event.get('session_id'):
            return event['session_id']
    return ''


def summary(path, out):
    results = [event for event in events(path)
               if event.get('type') == 'result' and isinstance(event.get('result'), str)]
    if results:
        Path(out).write_text(results[-1]['result'])
        return True
    return False


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'session':
        print(session(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == 'summary':
        summary(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
