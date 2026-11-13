import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import cv_text

DOCX = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>Alex Example</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Go</w:t><w:tab/><w:t>Python</w:t></w:r></w:p></w:body></w:document>')
ODT = ('<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
       'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text>'
       '<text:h>Alex Example</text:h><text:p>Kafka <text:span>pipelines</text:span></text:p>'
       '</office:text></office:body></office:document-content>')


class CvText(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def archive(self, name, member, xml):
        path = self.directory / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(member, xml)
        return path

    def run_main(self, *paths):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cv_text.main([str(path) for path in paths])
        return code, output.getvalue()

    def test_reads_every_supported_format_in_one_call(self):
        markdown = self.directory / 'cv.md'
        markdown.write_text('# Alex\n\n\n\nBackend')
        docx = self.archive('cv.docx', 'word/document.xml', DOCX)
        odt = self.archive('cv.odt', 'content.xml', ODT)
        code, output = self.run_main(markdown, docx, odt)
        self.assertEqual(code, 0)
        self.assertIn(f'===== {markdown}\n# Alex\n\nBackend\n', output)
        self.assertIn('Alex Example\nGo\tPython', output)
        self.assertIn('Alex Example\nKafka pipelines', output)

    def test_pdf_uses_pdftotext(self):
        path = self.directory / 'cv.pdf'
        path.write_bytes(b'%PDF-1.4')
        done = type('Done', (), {'returncode': 0, 'stdout': 'Alex from PDF', 'stderr': ''})
        with patch.object(cv_text.shutil, 'which', return_value='/usr/bin/pdftotext'), \
                patch.object(cv_text.subprocess, 'run', return_value=done) as run:
            code, output = self.run_main(path)
        self.assertEqual(code, 0)
        self.assertIn('Alex from PDF', output)
        self.assertEqual(run.call_args.args[0][0], 'pdftotext')

    def test_failures_are_reported_and_others_still_read(self):
        legacy = self.directory / 'old.doc'
        legacy.write_bytes(b'\xd0\xcf\x11\xe0')
        broken = self.directory / 'broken.docx'
        broken.write_text('not a zip')
        good = self.directory / 'cv.txt'
        good.write_text('Alex')
        code, output = self.run_main(legacy, broken, self.directory / 'missing.pdf', good)
        self.assertEqual(code, 1)
        self.assertEqual(output.count('UNREADABLE'), 3)
        self.assertIn('save it as PDF, DOCX or Markdown', output)
        self.assertTrue(output.rstrip().endswith('Alex'))


if __name__ == '__main__':
    unittest.main()
