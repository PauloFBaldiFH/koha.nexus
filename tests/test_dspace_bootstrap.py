"""Build orchestration doubles; integrated CI uses actual images and installer."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import dspace_bootstrap as bootstrap
import dspace_smoke
sys.path.insert(0, str(ROOT / 'platforms/dspace'))
import runtime


class BootstrapTests(unittest.TestCase):
    def test_extracted_kit_runs_solr_contract_check_without_the_checkout(self):
        # Exercise the distributed tools, not imports resolving back into the
        # repository. Docker responses alone are doubled; the contract read
        # and release/patch validation are real and fail with the old ZIP.
        with tempfile.TemporaryDirectory() as temp:
            kit = Path(temp) / 'kit'
            with zipfile.ZipFile(ROOT / 'platforms/dspace/build-inputs.zip') as archive:
                archive.extractall(kit)
            code = r'''
import json, subprocess, sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import dspace_smoke
def docker(*args, **kwargs):
    text = ''
    if args[0] == 'exec':
        text = '8983' if 'id' in args else json.dumps({'status': {k: {} for k in
            ('authority','oai','search','statistics','qaevent','suggestion','audit')}})
    return subprocess.CompletedProcess(args, 0, text, '')
with patch.object(dspace_smoke, 'docker', side_effect=docker):
    dspace_smoke.smoke('solr', 'nexus-dspace')
'''
            result = subprocess.run([sys.executable, '-I', '-c', code, str(kit / 'tools')],
                                    cwd=temp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('solr: startup and image contract passed', result.stdout)

    def test_distributed_build_kit_is_bound_to_installer_and_reproducible(self):
        import dspace_build_bundle
        import io
        output = io.BytesIO()
        dspace_build_bundle.create(output)
        content = (ROOT / 'platforms/dspace/build-inputs.zip').read_bytes()
        self.assertEqual(output.getvalue(), content)
        self.assertIn('KEI_DSPACE_BUILD_SHA="' + hashlib.sha256(content).hexdigest() + '"', (ROOT / 'installer').read_text())

    def test_missing_catalog_offers_preparation_without_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'dspace'
            rt = runtime.Runtime(root, Path(temp) / 'catalog.json', lab=True)
            self.assertTrue(rt.availability()['prepare_required'])
            self.assertFalse(root.exists())

    def test_cached_images_still_get_smoked_and_catalog_is_published_last(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'catalog.json'
            result = {'schema': 1, 'images': {'backend': 'sha256:' + '1' * 64}}
            def smoke(*args):
                self.assertFalse(target.exists(), 'No partial catalog may become installable')
            with patch.object(bootstrap, 'trusted_directory', side_effect=lambda p: Path(p)), \
                 patch.object(bootstrap, 'matching_image', return_value=True), \
                 patch.object(bootstrap.images, 'prepare') as fetch, \
                 patch.object(bootstrap, 'catalog', return_value=result), \
                 patch.object(dspace_smoke, 'smoke', side_effect=smoke) as checks:
                bootstrap.prepare(target, Path(temp))
            fetch.assert_not_called()
            self.assertEqual(checks.call_count, 3)
            self.assertEqual(json.loads(target.read_text())['origin'], 'local-build')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_failed_smoke_never_leaves_a_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'catalog.json'
            with patch.object(bootstrap, 'trusted_directory', side_effect=lambda p: Path(p)), \
                 patch.object(bootstrap, 'matching_image', return_value=True), \
                 patch.object(dspace_smoke, 'smoke', side_effect=RuntimeError('broken entrypoint')):
                with self.assertRaises(RuntimeError):
                    bootstrap.prepare(target, Path(temp))
            self.assertFalse(target.exists())

    def test_existing_catalog_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'catalog.json'
            target.write_text('keep')
            with patch.object(bootstrap, 'trusted_directory', side_effect=lambda p: Path(p)), \
                 patch.object(bootstrap, 'matching_image') as inspect:
                with self.assertRaises(ValueError):
                    bootstrap.prepare(target, Path(temp))
            inspect.assert_not_called()
            self.assertEqual(target.read_text(), 'keep')

    def test_only_local_build_catalog_enables_non_lab_local_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'catalog.json'
            rt = runtime.Runtime(Path(temp) / 'dspace', path)
            data = {'schema': 1, 'release_sha256': rt.release_hash,
                    'images': {name: 'sha256:' + '1' * 64 for name in ('backend', 'ui', 'solr')}}
            path.write_text(json.dumps(data))
            with self.assertRaises(runtime.Refused): rt.images()
            data['origin'] = 'local-build'
            path.write_text(json.dumps(data))
            self.assertEqual(len(rt.images()), 4)
            data['images']['backend'] = 'nexus-dspace-backend:latest'
            path.write_text(json.dumps(data))
            with self.assertRaises(runtime.Refused): rt.images()

    def test_missing_components_only_are_built_and_existing_sources_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'catalog.json'
            (Path(temp) / 'sources').mkdir()
            with patch.object(bootstrap, 'trusted_directory', side_effect=lambda p: Path(p)), \
                 patch.object(bootstrap, 'matching_image', side_effect=lambda d, n: n != 'ui'), \
                 patch.object(bootstrap.images, 'prepare') as fetch, \
                 patch.object(bootstrap.images, 'validate_sources') as validate, \
                 patch.object(bootstrap.images, 'run') as build, \
                 patch.object(bootstrap, 'catalog', return_value={}), \
                 patch.object(dspace_smoke, 'smoke'):
                bootstrap.prepare(target, Path(temp))
            fetch.assert_not_called()
            validate.assert_called_once()
            self.assertEqual(build.call_count, 1)
            self.assertIn('nexus-dspace-ui:10.1-r5', build.call_args.args)


if __name__ == '__main__': unittest.main()
