#!/usr/bin/env python3
"""Deliver new Active shortlist entries and run summaries to Telegram without exposing the token."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

DIRECTORY = Path(__file__).resolve().parent.parent

VACANCY_HEADER = '🎳 New shit has come to light, man.'
ZERO_HEADER = '🎳 Mark it zero.'
FAILURE_HEADER = '🎳 This aggression will not stand, man.'
SETUP_MESSAGE = ('🎳 The Dude abides. Telegram is connected: new jobs from the daily scan '
                 'will show up here.')


def settings(directory):
    values = {}
    path = directory / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.removeprefix('export ').partition('=')
            if separator:
                values[key.strip()] = value.strip().strip('\"\'')
    for key in ('TG_BOT_TOKEN', 'TG_CHAT_ID'):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def api(token, method, payload=None):
    request = urllib.request.Request(
        'https://api.telegram.org/bot' + token + '/' + method,
        data=json.dumps(payload or {}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # Never include the request URL (it contains the token) in logs.
        raise RuntimeError(f'Telegram {method}: HTTP {error.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError(f'Telegram {method}: connection failed') from None
    if not result.get('ok'):
        raise RuntimeError(f'Telegram {method}: API request rejected')
    return result['result']


def recipient(directory, config):
    if config.get('TG_CHAT_ID'):
        return config['TG_CHAT_ID']
    path = directory / '.telegram_chat_id'
    if path.exists():
        return path.read_text().strip()
    updates = api(config['TG_BOT_TOKEN'], 'getUpdates', {'timeout': 0})
    chats = set()
    for update in updates:
        message = update.get('message', {})
        chat = message.get('chat', {})
        command = message.get('text', '').split(maxsplit=1)
        if chat.get('type') == 'private' and command and command[0].split('@')[0] == '/start':
            chats.add(chat['id'])
    if len(chats) != 1:
        raise RuntimeError('Send /start to the bot; with several chats, set TG_CHAT_ID in .env.')
    chat_id = str(chats.pop())
    path.write_text(chat_id + '\n')
    path.chmod(0o600)
    return chat_id


def entries(text):
    """Parse only level-three vacancy entries inside the active section."""
    active = re.search(r'^## Active shortlist\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not active:
        raise RuntimeError('NEW.md has no Active shortlist section')
    result = []
    for block in re.split(r'(?=^### )', active[1], flags=re.M):
        if not block.startswith('### '):
            continue
        url = re.search(r'^- Vacancy:\s*(https?://\S+)\s*$', block, re.M)
        status = re.search(r'^- Status:\s*`?([A-Z]+)', block, re.M)
        if not url or not status:
            raise RuntimeError('Active vacancy is missing its URL or status')
        if status[1] in {'APPLIED', 'SKIP', 'EXPIRED', 'CLOSED', 'REJECTED'}:
            continue
        result.append((url[1], block.strip()))
    return result


def split_message(text):
    # At most 3600 UTF-16 units even when every character is an emoji.
    result = []
    while len(text) > 1800:
        end = text.rfind('\n', 0, 1800)
        if end <= 0:
            end = 1800
        result.append(text[:end])
        text = text[end:].lstrip('\n')
    if text:
        result.append(text)
    return result


def chunks(block):
    text = VACANCY_HEADER + '\n\n' + block.removeprefix('### ').replace('`', '')
    return split_message(re.sub(r'^- ', '• ', text, flags=re.M))


def run_message(summary_file, run_log, exit_code):
    log = run_log.read_text()
    # Prefer the CLI's actual settings over the runner's requested settings.
    model = re.search(r'^model: (.+)$', log, re.M)
    effort = (re.search(r'^reasoning effort: (.+)$', log, re.M)
              or re.search(r'^reasoning_effort=(.+)$', log, re.M))
    usage = re.findall(r'^tokens used\s*\n([\d,]+)\s*$', log, re.M)
    tokens = f'{int(usage[-1].replace(",", "")):,}' if usage else 'n/a'
    token_line = f'CLI tokens: {tokens}'
    codex_turns, claude_results, claude_model = [], [], None
    for line in log.splitlines():
        if not line.startswith('{'):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        counts = event.get('usage')
        if event.get('type') == 'turn.completed':
            if isinstance(counts, dict) and all(
                isinstance(counts.get(key), int) and counts[key] >= 0
                for key in ('input_tokens', 'cached_input_tokens', 'output_tokens')
            ):
                codex_turns.append(counts)
        elif event.get('type') == 'system' and isinstance(event.get('model'), str):
            claude_model = claude_model or event['model']
        elif event.get('type') == 'result' and isinstance(counts, dict):
            claude_results.append(event)
    if codex_turns:
        inputs, cached, outputs = (
            sum(turn[key] for turn in codex_turns)
            for key in ('input_tokens', 'cached_input_tokens', 'output_tokens')
        )
        # Cached input is part of input; reasoning is part of output.
        token_line = (f'Tokens: {inputs + outputs:,} | in: {inputs:,} '
                      f'(cached: {cached:,}) | out: {outputs:,}')
    elif claude_results:
        # Claude reports cache reads and writes separately from uncached input.
        def total(key):
            return sum(int(result['usage'].get(key) or 0) for result in claude_results)
        cached = total('cache_read_input_tokens')
        inputs = total('input_tokens') + total('cache_creation_input_tokens') + cached
        outputs = total('output_tokens')
        token_line = (f'Tokens: {inputs + outputs:,} | in: {inputs:,} '
                      f'(cached: {cached:,}) | out: {outputs:,}')
        costs = [result.get('total_cost_usd') for result in claude_results]
        if all(isinstance(cost, (int, float)) for cost in costs):
            token_line += f' | ${sum(costs):.2f}'
    if not model and claude_model:
        model = (None, claude_model)
    model = model or re.search(r'^model=(.+)$', log, re.M)
    header = ''
    if exit_code == 0:
        summary = summary_file.read_text().strip() if summary_file.exists() else ''
        if not summary:
            summary = 'Scan complete. The final summary is missing; check the logs.'
        summary = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', summary)
        summary = summary.replace('**', '').replace('`', '')
        summary = re.sub(r'^- ', '', summary, flags=re.M)
        if re.search(r'^New: 0\b', summary, re.M):
            header = ZERO_HEADER + '\n'
    elif exit_code == 124:
        header = FAILURE_HEADER + '\n'
        summary = 'Scan not finished: time limit exceeded.\nResults may be incomplete.'
    else:
        header = FAILURE_HEADER + '\n'
        summary = f'Scan not finished: exit code {exit_code}.\nResults may be incomplete.'
    scope = 'Scope: company watchlist\n' if re.search(r'^source=companies$', log, re.M) else ''
    return (f'{header}Run: {run_log.stem}\n{scope}\n{summary}\n\n'
            f'{model[1] if model else "model n/a"} / '
            f'{effort[1] if effort else "effort n/a"} | {token_line}')


def enqueue_run(directory, summary_file, run_log, exit_code):
    path, state = load_state(directory)
    runs = state.setdefault('pending_runs', {})
    run_id = run_log.name
    if run_id not in state.get('delivered_runs', []) and run_id not in runs:
        runs[run_id] = split_message(run_message(summary_file, run_log, exit_code))
        save(path, state)


def save(path, state):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def load_state(directory):
    path = directory / '.telegram_state.json'
    if not path.exists():
        raise RuntimeError('Telegram baseline missing; run --prepare before the scan')
    return path, json.loads(path.read_text())


def prepare(directory):
    path = directory / '.telegram_state.json'
    if not path.exists():
        text = (directory / 'NEW.md').read_text()
        archive = directory / 'APPLIED.md'
        if archive.exists():
            text += '\n' + archive.read_text()
        seen = re.findall(r'^- Vacancy:\s*(https?://\S+)\s*$', text, re.M)
        save(path, {'seen': list(dict.fromkeys(seen)), 'pending': {}})
        print(f'Telegram baseline initialized: {len(seen)} existing vacancies excluded')


def send(token, chat_id, text):
    api(token, 'sendMessage', {
        'chat_id': chat_id,
        'text': text,
        'link_preview_options': {'is_disabled': True},
    })


def deliver(directory, enqueue=True):
    path, state = load_state(directory)
    if enqueue:
        for url, block in entries((directory / 'NEW.md').read_text()):
            if url not in state['seen']:
                state['pending'][url] = chunks(block)
                state['seen'].append(url)
        save(path, state)
    if not state['pending'] and not state.get('pending_runs'):
        print('Telegram: no pending messages')
        return
    config = settings(directory)
    if not config.get('TG_BOT_TOKEN'):
        raise RuntimeError('TG_BOT_TOKEN missing; messages remain queued')
    chat_id = recipient(directory, config)
    # Drop pending entries the user has since applied to, skipped or archived.
    active_urls = {url for url, _ in entries((directory / 'NEW.md').read_text())}
    for url in list(state['pending']):
        if url not in active_urls:
            del state['pending'][url]
            save(path, state)
            continue
        while state['pending'][url]:
            send(config['TG_BOT_TOKEN'], chat_id, state['pending'][url][0])
            state['pending'][url].pop(0)
            save(path, state)
        del state['pending'][url]
        save(path, state)
        print('Telegram: vacancy delivered')
    for run_id in list(state.get('pending_runs', {})):
        messages = state['pending_runs'][run_id]
        while messages:
            send(config['TG_BOT_TOKEN'], chat_id, messages[0])
            messages.pop(0)
            save(path, state)
        del state['pending_runs'][run_id]
        state.setdefault('delivered_runs', []).append(run_id)
        save(path, state)
        print('Telegram: run summary delivered')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for flag in ('prepare', 'send', 'retry', 'setup-test', 'run-summary'):
        group.add_argument('--' + flag, action='store_true')
    parser.add_argument('--summary-file', type=Path)
    parser.add_argument('--run-log', type=Path)
    parser.add_argument('--exit-code', type=int, default=0)
    args = parser.parse_args()
    if args.prepare:
        prepare(DIRECTORY)
    elif args.run_summary:
        if args.summary_file is None or args.run_log is None:
            parser.error('--run-summary requires --summary-file and --run-log')
        enqueue_run(DIRECTORY, args.summary_file, args.run_log, args.exit_code)
        deliver(DIRECTORY, enqueue=False)
    elif args.setup_test:
        config = settings(DIRECTORY)
        if not config.get('TG_BOT_TOKEN'):
            raise RuntimeError('TG_BOT_TOKEN missing')
        send(config['TG_BOT_TOKEN'], recipient(DIRECTORY, config), SETUP_MESSAGE)
        print('Telegram setup test delivered')
    else:
        deliver(DIRECTORY, enqueue=args.send)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f'Telegram notification failed: {error}', file=sys.stderr)
        sys.exit(1)
