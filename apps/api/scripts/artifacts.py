"""Model artifacts: lock file, verification, packing and fetching.

Artifacts (trained models, the legal vector store) are too large for git and
live in ARTIFACTS_DIR, which is gitignored. What *should* be there is recorded
in artifacts.lock.json (tracked), so any machine can check it has the right
files and fetch them from wherever the team keeps the bundle.

    python scripts/artifacts.py lock                # record current files
    python scripts/artifacts.py verify [--strict]   # compare disk with the lock
    python scripts/artifacts.py pack out.tar.gz     # bundle for upload
    python scripts/artifacts.py fetch <https-url>   # download, unpack, verify

`fetch` takes any HTTPS URL of a bundle made by `pack` (a release asset, a
pre-signed object-storage URL, ...), or $ESTATEMIND_ARTIFACTS_URL.

Runtime-mutable files: Chroma rewrites the legal vector store (chroma/) when it
is used. They are locked and shipped like every other file, but `verify` only
requires them to be present; a changed hash there is expected, not tampering.
Otherwise the container entrypoint would re-fetch the whole bundle on every
start once the legal assistant had answered a question. `verify --strict`,
`pack` and `fetch` (checking a downloaded bundle) still compare every file.
Standard library only, so it runs in a slim build stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))
from config.paths import ARTIFACTS_DIR  # noqa: E402

LOCK_FILE = Path(os.environ.get('ESTATEMIND_ARTIFACTS_LOCK', API_ROOT / 'artifacts.lock.json'))
RUNTIME_MUTABLE = ('chroma/',)


def _runtime_mutable(rel: str) -> bool:
    return rel.startswith(RUNTIME_MUTABLE)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _scan(root: Path) -> dict[str, dict]:
    return {
        p.relative_to(root).as_posix(): {'size': p.stat().st_size, 'sha256': _sha256(p)}
        for p in sorted(root.rglob('*')) if p.is_file()
    }


def _load_lock() -> dict[str, dict]:
    return json.loads(LOCK_FILE.read_text(encoding='utf-8'))['files']


def lock(_args) -> int:
    files = _scan(ARTIFACTS_DIR)
    LOCK_FILE.write_text(json.dumps({'files': files}, indent=1) + '\n', encoding='utf-8')
    total = sum(f['size'] for f in files.values())
    print(f'locked {len(files)} files, {total / 1e6:.1f} MB -> {LOCK_FILE.name}')
    return 0


def verify(args, root: Path | None = None, strict: bool | None = None) -> int:
    root = root or ARTIFACTS_DIR
    strict = getattr(args, 'strict', False) if strict is None else strict
    expected, missing, changed, runtime_changed = _load_lock(), [], [], []
    for rel, meta in expected.items():
        path = root / rel
        if not path.is_file():
            missing.append(rel)
        elif path.stat().st_size != meta['size'] or _sha256(path) != meta['sha256']:
            (changed if strict or not _runtime_mutable(rel) else runtime_changed).append(rel)
    extra = sorted(set(_scan(root)) - set(expected)) if root.exists() else []
    for label, items in (('missing', missing), ('changed', changed),
                         ('changed at runtime (allowed)', runtime_changed), ('not in lock', extra)):
        for rel in items:
            print(f'{label}: {rel}')
    ok = not missing and not changed
    print(f"{'OK' if ok else 'MISMATCH'}: {len(expected) - len(missing) - len(changed)}/{len(expected)} files match"
          + (f' ({len(runtime_changed)} runtime-mutable changed)' if runtime_changed else '')
          + (f', {len(extra)} extra' if extra else ''))
    return 0 if ok else 1


def pack(args) -> int:
    if verify(args, strict=True) != 0:
        print('refusing to pack: disk does not match the lock (run `lock` first if the change is intended)')
        return 1
    with tarfile.open(args.output, 'w:gz') as tar:
        for rel in _load_lock():
            tar.add(ARTIFACTS_DIR / rel, arcname=rel)
    print(f'wrote {args.output}')
    return 0


def fetch(args) -> int:
    url = args.url or os.environ.get('ESTATEMIND_ARTIFACTS_URL', '')
    if not url.startswith('https://'):
        print('fetch needs an https:// URL (argument or ESTATEMIND_ARTIFACTS_URL)')
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        bundle, staging = Path(tmp) / 'bundle.tar.gz', Path(tmp) / 'artifacts'
        with urllib.request.urlopen(url) as response, bundle.open('wb') as out:  # noqa: S310 (https only)
            shutil.copyfileobj(response, out)
        with tarfile.open(bundle, 'r:gz') as tar:
            tar.extractall(staging, filter='data')  # rejects absolute paths and '..'
        if verify(args, root=staging, strict=True) != 0:
            print('downloaded bundle does not match the lock; nothing installed')
            return 1
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        for rel in _load_lock():
            target = ARTIFACTS_DIR / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging / rel, target)
    print(f'installed into {ARTIFACTS_DIR}')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('lock').set_defaults(func=lock)
    v = sub.add_parser('verify')
    v.add_argument('--strict', action='store_true', help='also compare runtime-mutable files (chroma/)')
    v.set_defaults(func=verify)
    p = sub.add_parser('pack')
    p.add_argument('output')
    p.set_defaults(func=pack)
    f = sub.add_parser('fetch')
    f.add_argument('url', nargs='?')
    f.set_defaults(func=fetch)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
