#!/usr/bin/env python3
"""Build both standalone SilverEV sites using only the Python standard library."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
SHARED = SRC / 'shared'
TOKENS = re.compile(r'\{\{([a-z_]+)\}\}')
SITEMAP_NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def source_digest(filename, metadata):
    # Track both the article and its search/social metadata, ignoring key order.
    payload = (SRC / 'ru' / filename).read_bytes() + b'\0'
    payload += json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def render(template, values):
    def replace(match):
        key = match[1]
        if key not in values:
            raise ValueError(f'Unknown template field: {key}')
        return str(values[key])
    return TOKENS.sub(replace, template)


def page_url(origin, filename):
    return origin + ('/' if filename == 'index.html' else '/' + filename)


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []
        self.canonicals = []
        self.alternates = {}
        self.lang = None
        self.h1 = 0
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'html':
            self.lang = attrs.get('lang')
        if tag == 'h1':
            self.h1 += 1
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                raise ValueError(f'Duplicate HTML id: {attrs["id"]}')
            self.ids.add(attrs['id'])
        for field in ('href', 'src'):
            if field in attrs:
                self.links.append(attrs[field])
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs['href'])
        if tag == 'link' and attrs.get('rel') == 'alternate':
            language = attrs['hreflang']
            if language in self.alternates:
                raise ValueError(f'Duplicate hreflang: {language}')
            self.alternates[language] = attrs['href']


def validate_output(output, sites, pages, default_language):
    parsed = {}
    hosts = {urlsplit(site['origin']).netloc: lang for lang, site in sites.items()}
    for lang, metadata in pages.items():
        for filename, meta in metadata.items():
            content = (output / lang / filename).read_text(encoding='utf-8')
            if '{{' in content or '<!--#' in content:
                raise ValueError(f'{lang}/{filename}: unresolved template or SSI')
            page = Page(content)
            parsed[(lang, filename)] = page
            if page.lang != lang or page.h1 != 1:
                raise ValueError(f'{lang}/{filename}: incorrect language or h1 count')
            if meta.get('noindex'):
                if page.canonicals or page.alternates:
                    raise ValueError('Error pages must not advertise canonical/alternate URLs')
            else:
                if page.canonicals != [page_url(sites[lang]['origin'], filename)]:
                    raise ValueError(f'{lang}/{filename}: incorrect canonical')
                expected = {code: page_url(site['origin'], filename) for code, site in sites.items()}
                expected['x-default'] = expected[default_language]
                if page.alternates != expected:
                    raise ValueError(f'{lang}/{filename}: incorrect hreflang pair')
    for (lang, filename), page in parsed.items():
        for link in page.links:
            parts = urlsplit(link)
            target_lang = hosts.get(parts.netloc, lang)
            if parts.netloc and parts.netloc not in hosts:
                continue
            if parts.scheme and parts.scheme not in ('http', 'https'):
                continue
            raw_path = unquote(parts.path)
            if not raw_path:
                path = filename
            elif raw_path.startswith('/'):
                path = raw_path.lstrip('/') or 'index.html'
            else:
                path = str(Path(filename).parent / raw_path)
            target = output / target_lang / path
            if target.is_dir():
                path = str(Path(path) / 'index.html')
                target = output / target_lang / path
            if not target.is_file():
                raise ValueError(f'{lang}/{filename}: missing target {link}')
            if parts.fragment and (target_lang, path) in parsed:
                if unquote(parts.fragment) not in parsed[(target_lang, path)].ids:
                    raise ValueError(f'{lang}/{filename}: missing anchor {link}')
    for lang, metadata in pages.items():
        tree = ET.parse(output / lang / 'sitemap.xml')
        urls = [node.text for node in tree.findall(f'.//{{{SITEMAP_NS}}}loc')]
        expected = [page_url(sites[lang]['origin'], filename) for filename, meta in metadata.items() if not meta.get('noindex')]
        if sorted(urls) != sorted(expected):
            raise ValueError(f'{lang}: sitemap does not match published pages')


def build(check=False):
    config = read_json(ROOT / 'site.config.json')
    sites = config['sites']
    if set(sites) != {'ru', 'en'} or config['default_language'] not in sites:
        raise ValueError('Configure both ru and en and a valid default language')
    for site in sites.values():
        origin = urlsplit(site['origin'])
        if origin.scheme != 'https' or not origin.netloc or origin.path or origin.query or origin.fragment:
            raise ValueError('Site origins must be HTTPS hostnames without a trailing slash')
    if len({site['origin'] for site in sites.values()}) != len(sites):
        raise ValueError('Each language needs its own origin')
    pages = {lang: read_json(SRC / lang / 'pages.json') for lang in sites}
    if set(pages['ru']) != set(pages['en']):
        raise ValueError('Russian and English page lists must match')
    for lang, metadata in pages.items():
        if {path.name for path in (SRC / lang).glob('*.html')} != set(metadata):
            raise ValueError(f'{lang}: pages.json must list every HTML source exactly once')
        for filename, meta in metadata.items():
            if not re.fullmatch(r'[a-z0-9-]+\.html', filename):
                raise ValueError(f'Invalid source filename: {filename}')
            if lang == 'en' and meta.get('source_sha256') != source_digest(filename, pages['ru'][filename]):
                raise ValueError(f'en/{filename}: translation needs review; see README.md')
            for field in ('section', 'body_class', 'type', 'noindex', 'scripts'):
                if meta.get(field) != pages['ru'][filename].get(field):
                    raise ValueError(f'{lang}/{filename}: structural metadata differs: {field}')
    templates = {name: (SHARED / 'templates' / (name + '.html')).read_text(encoding='utf-8')
                 for name in ('page', 'header', 'footer', 'yandex-metrika-head', 'yandex-metrika-body')}
    with tempfile.TemporaryDirectory(prefix='.silverev-build-', dir=ROOT) as temporary:
        output = Path(temporary) / 'dist'
        for lang, site in sites.items():
            destination = output / lang
            destination.mkdir(parents=True)
            shutil.copytree(SHARED / 'assets', destination / 'assets')
            shutil.copytree(SHARED / 'static', destination, dirs_exist_ok=True)
            locale = read_json(SRC / lang / 'locale.json')
            base = {key: html.escape(str(value), quote=True) for key, value in locale.items()}
            other_lang = 'en' if lang == 'ru' else 'ru'
            base.update(lang=lang, current_language=lang.upper(), alternate_language=other_lang.upper(),
                        alternate_lang=other_lang, contact_email=html.escape(config['contact_email']),
                        hostname=html.escape(urlsplit(site['origin']).netloc))
            for filename, meta in pages[lang].items():
                values = {**base, **{key: html.escape(str(value), quote=True) for key, value in meta.items()}}
                values['alternate_url'] = page_url(sites[other_lang]['origin'], filename)
                nav = []
                for section, path in [('home', '/'), ('news', '/news.html'), ('reviews', '/reviews.html'), ('history', '/history.html'), ('about', '/about.html')]:
                    active = section == meta['section']
                    nav.append(f'<a class="nav-link{" active" if active else ""}" data-section="{section}" href="{path}"' + (' aria-current="page"' if active else '') + f'>{base[section]}</a>')
                values['nav_links'] = '\n            '.join(nav)
                if meta.get('noindex'):
                    values['indexing'] = '<meta name="robots" content="noindex, follow">'
                    values['og_url'] = ''
                else:
                    own_url = page_url(site['origin'], filename)
                    tags = [f'<link rel="canonical" href="{own_url}">']
                    tags += [f'<link rel="alternate" hreflang="{code}" href="{page_url(other["origin"], filename)}">' for code, other in sites.items()]
                    tags += [f'<link rel="alternate" hreflang="x-default" href="{page_url(sites[config["default_language"]]["origin"], filename)}">']
                    values['indexing'] = '\n    '.join(tags)
                    values['og_url'] = f'<meta property="og:url" content="{own_url}">'
                values['scripts'] = '\n    '.join(f'<script defer src="{html.escape(path, quote=True)}"></script>' for path in meta.get('scripts', []))
                values['analytics_head'] = templates['yandex-metrika-head'] if site.get('analytics') else ''
                values['analytics_body'] = templates['yandex-metrika-body'] if site.get('analytics') else ''
                values['header'] = render(templates['header'], values)
                values['footer'] = render(templates['footer'], values)
                values['content'] = render((SRC / lang / filename).read_text(encoding='utf-8'), values)
                (destination / filename).write_text(render(templates['page'], values), encoding='utf-8')
            ET.register_namespace('', SITEMAP_NS)
            sitemap = ET.Element(f'{{{SITEMAP_NS}}}urlset')
            for filename, meta in pages[lang].items():
                if meta.get('noindex'):
                    continue
                item = ET.SubElement(sitemap, 'url')
                ET.SubElement(item, 'loc').text = page_url(site['origin'], filename)
            ET.indent(sitemap, space='  ')
            ET.ElementTree(sitemap).write(destination / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
            (destination / 'robots.txt').write_text(f'User-agent: *\nAllow: /\n\nSitemap: {site["origin"]}/sitemap.xml\n', encoding='utf-8')
            manifest = {'name': locale['manifest_name'], 'short_name': 'SilverEV', 'lang': lang, 'start_url': '/', 'scope': '/',
                        'icons': [{'src': f'/web-app-manifest-{size}x{size}.png', 'sizes': f'{size}x{size}', 'type': 'image/png', 'purpose': 'any maskable'} for size in (192, 512)],
                        'theme_color': '#08131E', 'background_color': '#08131E', 'display': 'standalone'}
            (destination / 'site.webmanifest').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        validate_output(output, sites, pages, config['default_language'])
        if not check:
            target = ROOT / 'dist'
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise ValueError('dist must be a regular directory, not a file or symlink')
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(output), str(target))
    print(f'{"Validated" if check else "Built and validated"}: ' + ', '.join(f'dist/{lang}/ ({len(metadata)} pages)' for lang, metadata in pages.items()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Build and validate in a temporary directory without replacing dist')
    args = parser.parse_args()
    try:
        build(args.check)
    except (OSError, ValueError, KeyError) as error:
        print(f'Build failed: {error}', file=sys.stderr)
        sys.exit(1)
