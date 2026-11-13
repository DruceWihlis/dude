import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import agent_events


class Compact(unittest.TestCase):
    def run_compact(self, *lines):
        out = io.StringIO()
        agent_events.compact(io.StringIO(''.join(line + '\n' for line in lines)), out)
        return out.getvalue().splitlines()

    def test_cuts_nested_strings_and_keeps_usage(self):
        event = {'type': 'item.completed', 'item': {'aggregated_output': 'x' * 10000,
                                                     'command': 'curl feed'}}
        usage = {'type': 'turn.completed', 'usage': {'input_tokens': 5}}
        first, second = self.run_compact(json.dumps(event), json.dumps(usage))
        item = json.loads(first)['item']
        self.assertTrue(item['aggregated_output'].endswith('…[truncated 6000 chars]'))
        self.assertEqual(item['command'], 'curl feed')
        self.assertEqual(json.loads(second), usage)

    def test_claude_result_summary_is_never_cut(self):
        summary = 'Scan complete.\n' + 'y' * 9000
        line, = self.run_compact(json.dumps({'type': 'result', 'result': summary,
                                             'usage': {'output_tokens': 1}}))
        self.assertEqual(json.loads(line)['result'], summary)

    def test_plain_text_lines_are_cut_too(self):
        line, = self.run_compact('z' * 5000)
        self.assertTrue(line.endswith('…[truncated 1000 chars]'))


if __name__ == '__main__':
    unittest.main()
