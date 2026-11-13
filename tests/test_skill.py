from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / '.agents' / 'skills' / 'abide'


class AbideSkill(unittest.TestCase):
    def test_codex_and_claude_share_one_skill(self):
        link = ROOT / '.claude' / 'skills' / 'abide'
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), SKILL.resolve())

    def test_frontmatter_names_the_skill(self):
        text = (SKILL / 'SKILL.md').read_text()
        front = re.match(r'---\n(.*?)\n---\n', text, re.S)
        self.assertIsNotNone(front)
        self.assertIn('name: abide\n', front[1] + '\n')
        self.assertRegex(front[1], r'description: \S')
        self.assertIn('writing.md', text)
        self.assertTrue((SKILL / 'writing.md').exists())

    def test_drafts_stay_private(self):
        ignored = (ROOT / '.gitignore').read_text().splitlines()
        self.assertIn('/applications/', ignored)

    def test_profile_example_has_application_facts(self):
        profile = (ROOT / 'config' / 'profile.example.md').read_text()
        self.assertIn('\n## Applications\n', profile)


if __name__ == '__main__':
    unittest.main()
