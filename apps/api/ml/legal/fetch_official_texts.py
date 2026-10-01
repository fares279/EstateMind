"""One-off download of official Tunisian legal texts for the legal assistant's corpus.

    python -m ml.legal.fetch_official_texts

Only the Ministry of Justice's own pages are fetched (justice.gov.tn, "Codes juridiques"):
a fixed list, no crawling. Official legislative texts are not protected by copyright
(Law No. 94-36 of 24 February 1994, article 1). Each file is saved with its source URL and
download date in manifest.json, next to the files in
estatemind/assistants/legal/data/official/.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'estatemind' / 'assistants' / 'legal' / 'data' / 'official'

# page id on justice.gov.tn -> (file stem, title)
SOURCES = {
    294: ('code_droits_reels', 'Code des droits réels'),
    287: ('code_obligations_contrats', 'Code des obligations et des contrats'),
    288: ('code_statut_personnel', 'Code du statut personnel'),
    318: ('immatriculation_fonciere', 'Immatriculation foncière'),
    326: ('juge_registre_foncier', 'Juge du registre foncier'),
    297: ('code_droit_international_prive', 'Code du droit international privé'),
    289: ('code_commerce', 'Code de commerce'),
}


def _ipv4_only():
    """The site's IPv6 address is unreachable from here; resolve IPv4 only."""
    import socket
    original = socket.getaddrinfo

    def getaddrinfo(host, port, family=0, *args, **kwargs):
        try:
            return original(host, port, socket.AF_INET, *args, **kwargs)
        except socket.gaierror:
            # Python's resolver fails intermittently here while the system resolver works:
            # ask it (nslookup) for the IPv4 address; TLS still uses the host name (SNI)
            import re
            import subprocess
            out = subprocess.run(['nslookup', host], capture_output=True, text=True, timeout=30).stdout
            ips = [ip for ip in re.findall(r'(\d+\.\d+\.\d+\.\d+)', out.split('Name:', 1)[-1])]
            if not ips:
                raise
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ips[0], port))]
    socket.getaddrinfo = getaddrinfo


def fetch(url: str, attempts: int = 6) -> tuple[bytes, str]:
    # the site's certificate chain does not validate from here; the content is public
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (EstateMind legal corpus, one-off)'})
            with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
                return r.read(), r.headers.get('Content-Type', '')
        except Exception as exc:  # flaky DNS / TLS: retry with backoff
            last = exc
            time.sleep(3 * (i + 1))
    raise RuntimeError(f'{url}: {last}')


def main() -> int:
    _ipv4_only()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    for page_id, (stem, title) in SOURCES.items():
        url = f'https://www.justice.gov.tn/index.php?id={page_id}&L=3'
        target = OUT / f'{stem}.pdf'
        if target.exists() and stem in manifest:
            print('have', stem)
            continue
        try:
            body, ctype = fetch(url)
        except RuntimeError as exc:
            print('FAILED', exc)
            continue
        if not body.startswith(b'%PDF'):
            print('not a PDF, skipped:', stem, ctype, len(body))
            continue
        target.write_bytes(body)
        manifest[stem] = {'title': title, 'source_url': url, 'publisher': 'Ministère de la Justice (Tunisie)',
                          'downloaded': dt.date.today().isoformat(), 'bytes': len(body),
                          'sha256': hashlib.sha256(body).hexdigest()}
        print('saved', stem, len(body))
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
