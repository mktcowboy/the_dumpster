#!/usr/bin/env python3
"""Check repository content without printing matched private values."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys

BLOCKED = {'8802b69f05738c4ed94b86a0fa4cee921db823e62d47a70d9034a1abcaa3bb9b', '9fbb8412cdc93b8c5919da05fe115ab04af1b15acc0e14c91d025b249a88f268', '614e8e1f4c3876db53f8d40288168711fa77930b5ccbf0b9626c9b01aa42d5f2', 'e016ef65bf37def457ab09faa9d48effdf0186a7dab671318b6d39de1a4f551c'}  # Fingerprints populated below; never store private values here.


def git(*args):
    return subprocess.check_output(['git', *args])


def private(data):
    for encoding in ('utf-8', 'utf-16-le', 'utf-16-be'):
        text = data.decode(encoding, errors='ignore').lower()
        if any(hashlib.sha256(t.encode()).hexdigest() in BLOCKED
               for t in re.findall(r'[a-z0-9]+', text)):
            return True
        if re.search(r'(?:^|[\s\"\x27=])/(?:users|home)/[^/\s]+/', text):
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--staged', action='store_true')
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--message')
    args = parser.parse_args()
    failed = []
    if args.message:
        if private(Path(args.message).read_bytes()):
            failed.append('commit message')
    else:
        names = git('ls-files', '-z') if args.staged else git('ls-files', '-z', '--cached', '--others', '--exclude-standard')
        for name in set(names.split(b'\0')) - {b''}:
            path = name.decode()
            if args.staged:
                data = git('show', ':' + path)
            else:
                p = Path(path)
                if not p.is_file():
                    continue
                data = p.read_bytes()
            if private(name) or private(data):
                failed.append('repository file (path withheld)')
    if args.staged or args.message:
        for field in ('GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT'):
            if private(git('var', field)):
                failed.append('commit identity')
    if args.history:
        if private(git('log', '--all', '--format=%an <%ae>%n%cn <%ce>%n%B')):
            failed.append('commit history metadata')
        objects = git('rev-list', '--objects', '--all').splitlines()
        for entry in objects:
            oid, _, name = entry.partition(b' ')
            if private(name):
                failed.append('historical filename')
            if git('cat-file', '-t', oid.decode()).strip() == b'blob':
                if private(git('cat-file', 'blob', oid.decode())):
                    failed.append('historical file content')
    if failed:
        print('Privacy check failed: ' + ', '.join(sorted(set(failed))), file=sys.stderr)
        return 1
    print('Privacy check passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
