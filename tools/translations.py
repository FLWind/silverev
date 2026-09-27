#!/usr/bin/env python3
"""Report stale English translations or record an explicit editorial review."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build import SRC, read_json, source_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'mark-reviewed'])
    parser.add_argument('pages', nargs='*', help='Exact HTML filenames for mark-reviewed')
    args = parser.parse_args()
    russian = read_json(SRC / 'ru/pages.json')
    english = read_json(SRC / 'en/pages.json')
    if args.command == 'mark-reviewed':
        if not args.pages:
            parser.error('Specify the translated HTML pages you have reviewed')
        for name in args.pages:
            if name not in russian or name not in english or not (SRC / 'en' / name).is_file():
                parser.error(f'Unknown translation: {name}')
        for name in args.pages:
            english[name]['source_sha256'] = source_digest(name, russian[name])
        (SRC / 'en/pages.json').write_text(json.dumps(english, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Recorded review:', ', '.join(args.pages))
        return 0
    stale = [name for name in russian if name not in english or english[name].get('source_sha256') != source_digest(name, russian[name])]
    if stale:
        print('Translations requiring review:\n' + '\n'.join(stale))
        return 1
    print('All English translations match the recorded Russian source revisions.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
