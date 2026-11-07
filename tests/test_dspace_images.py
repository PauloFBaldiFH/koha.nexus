"""Release preparation fails closed before any image build or service change."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dspace_images", ROOT / "tools/dspace_images.py")
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)


class DSpaceInputs(unittest.TestCase):
    def setUp(self):
        self.data = images.load_release()

    def assert_bad_lock(self, edit):
        data = copy.deepcopy(self.data)
        edit(data)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "release.json"
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                images.load_release(path)

    def test_rejects_movable_bases(self):
        self.assert_bad_lock(lambda d: d["bases"].update(node="node:22"))

    def test_rejects_arbitrary_sources(self):
        self.assert_bad_lock(lambda d: d["sources"]["ui"].update(repository="https://example.org/fork.git"))

    def test_rejects_dev_release(self):
        self.assert_bad_lock(lambda d: d["sources"]["backend"].update(tag="dspace-10_x-test"))

    def test_rejects_mismatched_frontend(self):
        self.assert_bad_lock(lambda d: d["sources"]["ui"].update(tag="dspace-9.4", version="9.4.0"))

    def test_does_not_claim_arm_support_or_installation(self):
        self.assertEqual(self.data["architectures"], ["linux/amd64"])
        contract = json.loads((images.BASE / "contract.json").read_text())
        self.assertFalse(contract["installable"])
        self.assertEqual(contract["lifecycle"]["migration"], "explicit-cli-operation")
        self.assertIsNone(contract["services"]["solr"]["public_path"])
        self.assertIsNone(contract["services"]["postgres"]["public_path"])

    def test_build_has_no_push_or_shell_and_uses_exact_pins(self):
        with patch.dict(os.environ, {}, clear=True):
            cmd = images.build_command(self.data, Path("/tmp/sources"), "backend", "nexus-dspace", Path("/tmp/out.json"))
        self.assertNotIn("--push", cmd)
        self.assertIn("--load", cmd)
        self.assertIn("backend-source=/tmp/sources/backend-source", cmd)
        self.assertIn("SOURCE_REVISION=" + self.data["sources"]["backend"]["commit"], cmd)
        self.assertIn("JAVA_IMAGE=" + self.data["bases"]["java"], cmd)

    def test_rejects_tag_or_shell_in_prefix(self):
        for prefix in ("image:latest", "image;touch /tmp/unwanted", "$(id)"):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                images.build_command(self.data, Path("/tmp"), "ui", prefix, Path("/tmp/out"))

    def test_prepare_preserves_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            marker = path / "keep"
            marker.write_text("user files")
            with patch.object(images, "run") as command, self.assertRaises(ValueError):
                images.prepare(self.data, path)
            command.assert_not_called()
            self.assertEqual(marker.read_text(), "user files")

    def test_moved_upstream_tag_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export"
            with patch.object(images, "run", return_value=subprocess.CompletedProcess([], 0, stdout="0" * 40)), self.assertRaises(ValueError):
                images.prepare(self.data, out)
            self.assertFalse(out.exists())

    def prepared_fixture(self, path):
        (path / "backend-source").mkdir()
        (path / "ui-source").mkdir()
        (path / "backend-source/pom.xml").write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0"><version>10.1</version></project>')
        (path / "ui-source/package.json").write_text('{"version":"10.1.0"}')
        (path / "sources.json").write_text(json.dumps(images.source_stamp(self.data)))
        (path / "checksums.json").write_text(json.dumps(images.source_checksums(path)))

    def test_refuses_modified_sources_before_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.prepared_fixture(path)
            images.validate_sources(self.data, path)
            (path / "ui-source/package.json").write_text('{"version":"10.1.0", "scripts":{"postinstall":"untrusted"}}')
            with self.assertRaisesRegex(ValueError, "changed"):
                images.validate_sources(self.data, path)

    def test_refuses_symlinked_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.prepared_fixture(path)
            (path / "ui-source/leak").symlink_to(path / "sources.json")
            with self.assertRaisesRegex(ValueError, "Symlinks"):
                images.validate_sources(self.data, path)

    def test_ui_fails_without_canonical_config(self):
        entry = images.BASE / "images/ui-entrypoint.sh"
        with patch.dict(os.environ, {"PATH": os.defpath}, clear=True):
            result = subprocess.run(["sh", str(entry)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("canonical", result.stderr)

    def test_proxy_settings_are_private_and_xml_escaped(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "HTTPS_PROXY": "http://user:p%26ss@proxy.example:8080", "NO_PROXY": "localhost,127.0.0.1"
        }, clear=True):
            target = Path(tmp) / "settings.xml"
            self.assertTrue(images.maven_proxy_settings(target))
            root = images.ET.fromstring(target.read_bytes())
            self.assertEqual(root.findtext("proxies/proxy/password"), "p&ss")
            self.assertEqual(root.findtext("proxies/proxy/nonProxyHosts"), "localhost|127.0.0.1")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_ui_rejects_upstream_self_signed_fallback(self):
        entry = images.BASE / "images/ui-entrypoint.sh"
        for variable in ("DSPACE_UI_SSL", "DSPACE_SSL"):
            with self.subTest(variable=variable), patch.dict(os.environ, {
                "PATH": os.defpath, variable: "true"
            }, clear=True):
                result = subprocess.run(["sh", str(entry)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 78)
                self.assertIn("reverse proxy", result.stderr)

    def test_dependency_patch_rejects_wrong_source_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "package.json").write_text('{}\n')
            (path / "package-lock.json").write_text('{}\n')
            patch_data = json.loads((images.BASE / 'ui-dependencies.json').read_text())
            with self.assertRaisesRegex(ValueError, 'differs'):
                images.apply_ui_patch(path, patch_data)
            self.assertEqual((path / 'package.json').read_text(), '{}\n')

    def test_dependency_patch_rejects_arbitrary_filenames(self):
        with self.assertRaisesRegex(ValueError, 'Only UI'):
            images.apply_ui_patch(Path('/tmp'), {'../unwanted': {}})

    def test_dependency_patch_applies_only_reviewed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            originals = {'package.json': {'version': '10.1.0'},
                         'package-lock.json': {'packages': {'old': {'version': '1'}}}}
            outputs = {'package.json': {'version': '10.1.0', 'dependencies': {'example': '2'}},
                       'package-lock.json': {'packages': {'new': {'version': '2'}}}}
            changes = {}
            for filename in originals:
                before = (json.dumps(originals[filename], indent=2) + '\n').encode()
                after = (json.dumps(outputs[filename], indent=2, sort_keys=True) + '\n').encode()
                (path / filename).write_bytes(before)
                changes[filename] = {'before': images.hashlib.sha256(before).hexdigest(),
                                     'after': images.hashlib.sha256(after).hexdigest()}
            changes['package.json']['value'] = outputs['package.json']
            changes['package-lock.json'].update(remove=['old'], update=outputs['package-lock.json']['packages'])
            images.apply_ui_patch(path, changes)
            self.assertEqual(json.loads((path / 'package-lock.json').read_text()), outputs['package-lock.json'])

    def test_preparation_rejects_mixed_nested_build_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            tools = ('@angular-devkit/build-angular', '@angular/cli', '@ngtools/webpack')
            (path / 'package.json').write_text(json.dumps({'devDependencies': dict.fromkeys(tools, '20.3.36')}))
            packages = {'node_modules/' + tool: {'version': '20.3.36'} for tool in tools}
            (path / 'package-lock.json').write_text(json.dumps({'packages': packages}))
            images.validate_ui_toolchain(path)
            packages['node_modules/other/node_modules/@ngtools/webpack'] = {'version': '20.3.42'}
            (path / 'package-lock.json').write_text(json.dumps({'packages': packages}))
            with self.assertRaisesRegex(ValueError, 'Mixed Angular'):
                images.validate_ui_toolchain(path)


if __name__ == "__main__":
    unittest.main()
