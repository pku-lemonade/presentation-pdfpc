"""Check installer failure boundaries without touching installed applications."""

import hashlib
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock

import build_wrapper
import install
from upstream_adapter import CompatibilityError, check_runtime


class InstallerTests(unittest.TestCase):
    def test_download_mismatch_prevents_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "bad.pkg"
            package.write_bytes(b"truncated download")
            with mock.patch.object(install, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                    install.extract_upstream(package, Path(temporary) / "expanded")
                run.assert_not_called()

    def test_matching_download_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "test.pkg"
            package.write_bytes(b"test package")
            with mock.patch.object(install, "UPSTREAM_SHA256", hashlib.sha256(b"test package").hexdigest()):
                install.verify_download(package)

    def test_unexpected_application_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            expanded = Path(temporary) / "expanded"
            contents = expanded / "component.pkg/Payload/Other.app/Contents"
            contents.mkdir(parents=True)
            (contents / "Info.plist").write_bytes(plistlib.dumps({
                "CFBundleIdentifier": "another.application",
                "CFBundleShortVersionString": "3.4.0",
                "CFBundleExecutable": "presentation.py",
            }))
            with mock.patch.object(install, "verify_download"), mock.patch.object(install, "run"):
                with self.assertRaisesRegex(RuntimeError, "identity"):
                    install.extract_upstream(Path(temporary) / "fixture.pkg", expanded)

    def test_missing_python_bindings_report_compatibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(CompatibilityError, "no bundled PyObjC"):
                check_runtime(Path(temporary) / "Sample.app/Contents/MacOS/presentation.py")

    def test_build_refuses_symlink_without_touching_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "existing"
            target.mkdir()
            (target / "keep.txt").write_text("keep")
            destination = Path(temporary) / "Wrapper.app"
            destination.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, "symbolic link"):
                build_wrapper.build(destination)
            self.assertEqual((target / "keep.txt").read_text(), "keep")

    def test_failed_build_preserves_previous_app(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            destination = base / "Wrapper.app"
            destination.mkdir()
            (destination / "keep.txt").write_text("previous app")
            upstream = base / "Upstream.app"
            script = base / "presentation.py"
            script.write_text("pass")
            with mock.patch.object(build_wrapper, "find_upstream", return_value=(upstream, script, {})), \
                    mock.patch.object(build_wrapper, "adapt_source"), \
                    mock.patch.object(build_wrapper, "check_runtime"), \
                    mock.patch.object(build_wrapper, "run", side_effect=subprocess.CalledProcessError(1, "codesign")):
                with self.assertRaises(subprocess.CalledProcessError):
                    build_wrapper.build(destination)
            self.assertEqual((destination / "keep.txt").read_text(), "previous app")
            self.assertEqual(list(base.glob(".presentation-pdfpc-*")), [])


if __name__ == "__main__":
    unittest.main()
