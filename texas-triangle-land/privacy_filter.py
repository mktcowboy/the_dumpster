"""Drop listings whose text trips the repository's privacy blocklist (scripts/check_privacy.py).

Public listing addresses occasionally contain a blocked word by coincidence; the repo rule is
that such words never land in committed files, so those rows are skipped. Values are never printed.
"""
import hashlib, os, re, sys

_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
try:
    sys.path.insert(0, _SCRIPTS)
    from check_privacy import BLOCKED
except ImportError:  # running outside the repo
    BLOCKED = set()
finally:
    sys.path.remove(_SCRIPTS)


def blocked(row):
    for v in row.values():
        if isinstance(v, str):
            for t in re.findall(r"[a-z0-9]+", v.lower()):
                if hashlib.sha256(t.encode()).hexdigest() in BLOCKED:
                    return True
    return False
