"""Regression checks for the two-domain static build (standard library only)."""
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())


class Inspect(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.text, self.links, self.ids = [], [], [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attributes):
        pass

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append((tag, self.stack[-4:]))

    def handle_data(self, text):
        self.text.append(text)


class SiteTests(unittest.TestCase):
    def test_translations_preserve_structure_and_references(self):
        for path in sorted((ROOT / 'src/ru').glob('*.html')):
            with self.subTest(page=path.name):
                ru = Inspect(path.read_text(encoding='utf-8'))
                en = Inspect((ROOT / 'src/en' / path.name).read_text(encoding='utf-8'))
                for page in [ru, en]:
                    self.assertEqual(page.errors, [])
                    self.assertEqual(page.stack, [])
                    self.assertEqual(len(page.ids), len(set(page.ids)))
                self.assertEqual(Counter(ru.links), Counter(en.links))
                self.assertEqual(set(ru.ids), set(en.ids))
                self.assertIsNone(re.search('[А-Яа-яЁё]', ''.join(en.text)))

    def test_both_sites_build_with_correct_domains(self):
        # --check performs complete HTML, URL, reciprocal hreflang and sitemap checks.
        result = subprocess.run([sys.executable, str(ROOT / 'build.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('dist/ru/', result.stdout)
        self.assertIn('dist/en/', result.stdout)

    def test_stale_translation_does_not_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary)
            shutil.copy2(ROOT / 'build.py', copy)
            shutil.copy2(ROOT / 'site.config.json', copy)
            shutil.copytree(ROOT / 'src', copy / 'src')
            (copy / 'dist').mkdir()
            marker = copy / 'dist/keep.txt'
            marker.write_text('last successful build', encoding='utf-8')
            source = copy / 'src/ru/index.html'
            source.write_text(source.read_text(encoding='utf-8') + '\n<!-- Editorial update -->\n', encoding='utf-8')
            result = subprocess.run([sys.executable, str(copy / 'build.py')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('translation needs review', result.stderr)
            self.assertEqual(marker.read_text(encoding='utf-8'), 'last successful build')

    def test_build_works_outside_repository_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, str(ROOT / 'build.py'), '--check'], cwd=temporary, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
