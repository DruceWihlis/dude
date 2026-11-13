#!/usr/bin/env python3
"""Print the text of each CV: PDF, DOCX, ODT, Markdown or plain text.

cv_text.py PATH...   one "===== PATH" header per file; failures are reported and skipped, exit 1
"""

from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from xml.etree import ElementTree

TEXT = {'.md', '.markdown', '.txt', '.text'}
WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
ODF = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'


def pdf(path):
    if not shutil.which('pdftotext'):
        raise RuntimeError('pdftotext is not installed (poppler-utils on Linux, poppler on macOS)')
    result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError('pdftotext failed: ' + result.stderr.strip()[:200])
    return result.stdout


def docx(path):
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read('word/document.xml'))
    lines = []
    for paragraph in root.iter(WORD + 'p'):
        parts = []
        for node in paragraph.iter():
            if node.tag == WORD + 't':
                parts.append(node.text or '')
            elif node.tag == WORD + 'tab':
                parts.append('\t')
            elif node.tag in (WORD + 'br', WORD + 'cr'):
                parts.append('\n')
        lines.append(''.join(parts))
    return '\n'.join(lines)


def odt(path):
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read('content.xml'))
    lines = []
    for node in root.iter():
        if node.tag in (ODF + 'p', ODF + 'h'):
            lines.append(''.join(node.itertext()))
    return '\n'.join(lines)


def extract(path):
    suffix = path.suffix.lower()
    if suffix in TEXT:
        return path.read_text()
    if suffix == '.pdf':
        return pdf(path)
    if suffix == '.docx':
        return docx(path)
    if suffix == '.odt':
        return odt(path)
    raise RuntimeError(f'unsupported format {suffix or "(none)"}: save it as PDF, DOCX or Markdown')


def main(paths):
    if not paths:
        sys.exit(__doc__)
    failed = False
    for name in paths:
        print(f'===== {name}')
        try:
            text = extract(Path(name))
        except (OSError, RuntimeError, KeyError, zipfile.BadZipFile,
                ElementTree.ParseError, UnicodeDecodeError) as error:
            print(f'UNREADABLE: {error}')
            failed = True
            continue
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        print(text if text else 'UNREADABLE: no text found (scanned image?)')
        failed = failed or not text
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
