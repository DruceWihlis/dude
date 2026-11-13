#!/usr/bin/env python3
"""Read Codex (`--json`) and Claude Code (`stream-json`) event logs.

session LOG          print the session ID to resume (Codex thread or Claude session)
summary LOG OUT      write the last Claude result text to OUT (Codex writes its own)
compact              copy stdin to stdout, cutting long strings so run logs stay small
"""

import json
from pathlib import Path
import sys

# Command output and page bodies longer than this are cut in the saved trace. The agent itself
# still sees its full output; this only keeps logs/ readable and small.
LIMIT = 4000


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


def cut(value):
    if isinstance(value, str) and len(value) > LIMIT:
        return value[:LIMIT] + f'…[truncated {len(value) - LIMIT} chars]'
    if isinstance(value, list):
        return [cut(item) for item in value]
    if isinstance(value, dict):
        return {key: cut(item) for key, item in value.items()}
    return value


def compact(source, sink):
    for line in source:
        text = line.rstrip('\n')
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            event = None
        if isinstance(event, dict):
            # The final Claude result is the run summary; keep it whole.
            result = event.get('result') if event.get('type') == 'result' else None
            event = cut(event)
            if result is not None:
                event['result'] = result
            text = json.dumps(event, ensure_ascii=False)
        else:
            text = cut(text)
        sink.write(text + '\n')
        sink.flush()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'session':
        print(session(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == 'summary':
        summary(sys.argv[2], sys.argv[3])
    elif sys.argv[1:] == ['compact']:
        sys.stdin.reconfigure(errors='replace')
        compact(sys.stdin, sys.stdout)
    else:
        sys.exit(__doc__)
