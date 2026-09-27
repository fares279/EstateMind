import importlib.util
import io
import tarfile
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

_spec = importlib.util.spec_from_file_location('artifacts_cli', Path(__file__).resolve().parents[2] / 'scripts' / 'artifacts.py')
artifacts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(artifacts)


class ArtifactLockTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / 'artifacts'
        (self.src / 'valuation').mkdir(parents=True)
        (self.src / 'valuation' / 'model.joblib').write_bytes(b'model-bytes')
        (self.src / 'priors.json').write_text('{}')
        self.lock = self.tmp / 'artifacts.lock.json'
        patches = [mock.patch.object(artifacts, 'ARTIFACTS_DIR', self.src),
                   mock.patch.object(artifacts, 'LOCK_FILE', self.lock)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        artifacts.main(['lock'])

    def _bundle(self, tamper=False) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tar:
            for rel in ('valuation/model.joblib', 'priors.json'):
                data = b'evil' if tamper and rel.endswith('joblib') else (self.src / rel).read_bytes()
                info = tarfile.TarInfo(rel)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    def _fetch_into(self, target, bundle):
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(bundle)
        with mock.patch.object(artifacts, 'ARTIFACTS_DIR', target), \
                mock.patch.object(artifacts.urllib.request, 'urlopen', return_value=response):
            return artifacts.main(['fetch', 'https://example.invalid/bundle.tar.gz'])

    def test_verify_detects_changes(self):
        self.assertEqual(artifacts.main(['verify']), 0)
        (self.src / 'priors.json').write_text('{"changed": 1}')
        self.assertEqual(artifacts.main(['verify']), 1)

    def test_fetch_installs_a_matching_bundle(self):
        target = self.tmp / 'restored'
        self.assertEqual(self._fetch_into(target, self._bundle()), 0)
        self.assertEqual((target / 'valuation' / 'model.joblib').read_bytes(), b'model-bytes')

    def test_fetch_rejects_a_tampered_bundle(self):
        target = self.tmp / 'restored'
        self.assertEqual(self._fetch_into(target, self._bundle(tamper=True)), 1)
        self.assertFalse((target / 'valuation' / 'model.joblib').exists())

    def test_fetch_requires_https(self):
        self.assertEqual(artifacts.main(['fetch', 'http://example.invalid/x']), 1)
