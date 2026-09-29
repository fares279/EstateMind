import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
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


class RuntimeMutableArtifactTests(SimpleTestCase):
    """The legal Chroma store is rewritten by Chroma at runtime; that must not
    count as a mismatch (the container would re-fetch the bundle on every start)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / 'artifacts'
        (self.src / 'valuation').mkdir(parents=True)
        (self.src / 'chroma' / 'legal').mkdir(parents=True)
        (self.src / 'valuation' / 'model.joblib').write_bytes(b'model-bytes')
        (self.src / 'chroma' / 'legal' / 'chroma.sqlite3').write_bytes(b'as shipped')
        self.lock = self.tmp / 'artifacts.lock.json'
        patches = [mock.patch.object(artifacts, 'ARTIFACTS_DIR', self.src),
                   mock.patch.object(artifacts, 'LOCK_FILE', self.lock)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        artifacts.main(['lock'])
        self.chroma = self.src / 'chroma' / 'legal' / 'chroma.sqlite3'

    def test_chroma_changed_at_runtime_still_verifies(self):
        self.chroma.write_bytes(b'rewritten by chroma after a query')
        self.assertEqual(artifacts.main(['verify']), 0)

    def test_missing_chroma_file_is_still_a_mismatch(self):
        self.chroma.unlink()
        self.assertEqual(artifacts.main(['verify']), 1)

    def test_strict_verify_and_pack_still_see_the_change(self):
        self.chroma.write_bytes(b'rewritten by chroma after a query')
        self.assertEqual(artifacts.main(['verify', '--strict']), 1)
        self.assertEqual(artifacts.main(['pack', str(self.tmp / 'bundle.tar.gz')]), 1)

    def test_model_file_change_is_still_a_mismatch(self):
        (self.src / 'valuation' / 'model.joblib').write_bytes(b'tampered')
        self.assertEqual(artifacts.main(['verify']), 1)


@unittest.skipUnless(shutil.which('sh'), 'needs a POSIX shell')
class EntrypointRefetchTests(SimpleTestCase):
    """Runs the real docker-entrypoint.sh. ESTATEMIND_ARTIFACTS_URL points at an
    unreachable host, so an attempted re-fetch makes the script fail."""

    API = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / 'artifacts'
        (self.src / 'valuation').mkdir(parents=True)
        (self.src / 'chroma' / 'legal').mkdir(parents=True)
        (self.src / 'valuation' / 'model.joblib').write_bytes(b'model-bytes')
        (self.src / 'chroma' / 'legal' / 'chroma.sqlite3').write_bytes(b'as shipped')
        self.lock = self.tmp / 'artifacts.lock.json'
        with mock.patch.object(artifacts, 'ARTIFACTS_DIR', self.src), mock.patch.object(artifacts, 'LOCK_FILE', self.lock):
            artifacts.main(['lock'])

    def _run_entrypoint(self):
        env = {**os.environ, 'SECRET_KEY': 'x' * 60, 'ESTATEMIND_ARTIFACTS_DIR': str(self.src),
               'ESTATEMIND_ARTIFACTS_LOCK': str(self.lock),
               'ESTATEMIND_ARTIFACTS_URL': 'https://artifacts.example.invalid/bundle.tar.gz',
               'PATH': os.pathsep.join([str(Path(sys.executable).parent), os.environ.get('PATH', '')])}
        env.pop('RUN_MIGRATIONS', None)
        return subprocess.run(['sh', 'docker-entrypoint.sh', 'true'], cwd=self.API, env=env,
                              capture_output=True, text=True, timeout=120)

    def test_chroma_change_does_not_trigger_a_refetch(self):
        (self.src / 'chroma' / 'legal' / 'chroma.sqlite3').write_bytes(b'rewritten by chroma after a query')
        result = self._run_entrypoint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_model_file_does_trigger_a_refetch(self):
        (self.src / 'valuation' / 'model.joblib').unlink()
        result = self._run_entrypoint()
        self.assertNotEqual(result.returncode, 0)
