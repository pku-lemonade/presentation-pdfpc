"""Verify in-memory upstream adaptation without starting Cocoa or editing apps."""

import hashlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from upstream_adapter import CompatibilityError, adapt_source, find_upstream
from wrapper import accept_document


FIXTURE = '''
import os
events = []
args = []
if True:
    class DropApplicationDelegate(object):
        def application_openFile_(self, app, filename):
            if filename != os.path.abspath(__file__):
                args.append(filename)
def cgpdf_get(*args):
    pass
def cgpdf_array2list(*args):
    pass
def cgpdf_stream2str(*args):
    pass
def exit_relaunch(path, page):
    raise AssertionError("original reload must not execute")
def annotations(page):
    return []
def prepare_animations(widgets):
    events.append("prepare animations")
_pdf = object()
url = "fixture.pdf"
page_count = 2
pdf_notes = {}
widgets = {}
for page_number in range(page_count):
    for annotation in annotations(page_number):
        pdf_notes.setdefault(page_number, []).append(annotation)
pdf_notes[0] = ["existing annotation"]
events.append("annotations collected")
prepare_animations(widgets)
events.append("upstream continues")
beamer_notes = {}
renderer_sources = [pdf_notes, beamer_notes]
'''


class AdapterTests(unittest.TestCase):
    def test_adaptation_compiles_without_executing_source_or_hooks(self):
        source = 'raise AssertionError("must not execute while adapting")\n' + FIXTURE
        with mock.patch("builtins.exec", side_effect=AssertionError("exec called")):
            code = adapt_source(source, "in-memory-fixture.py")
        self.assertIsInstance(code, types.CodeType)
        self.assertEqual(code.co_filename, "in-memory-fixture.py")

    def execute_fixture(self, source=FIXTURE):
        hook_calls = []
        reload_calls = []
        def attach(namespace):
            hook_calls.append(namespace)
            self.assertEqual(namespace["pdf_notes"][0], ["existing annotation"])
            namespace["pdf_notes"][1] = ["imported pdfpc note"]
            namespace["events"].append("attach pdfpc")
        def relaunch(path, page):
            reload_calls.append((path, page))
            return "wrapper relaunched"
        namespace = {"__pdfpc_wrapper_attach__": attach,
                     "__pdfpc_wrapper_relaunch__": relaunch,
                     "__pdfpc_wrapper_accept_document__": lambda filename: True}
        exec(adapt_source(source, "in-memory-fixture.py"), namespace)
        return namespace, hook_calls, reload_calls

    def test_notes_hook_follows_annotations_and_preserves_renderer(self):
        namespace, calls, _ = self.execute_fixture()
        self.assertEqual(namespace["events"], [
            "annotations collected", "prepare animations", "attach pdfpc", "upstream continues"])
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0], namespace)
        self.assertIs(namespace["renderer_sources"][0], namespace["pdf_notes"])
        self.assertIs(namespace["renderer_sources"][1], namespace["beamer_notes"])
        self.assertEqual(namespace["pdf_notes"], {
            0: ["existing annotation"], 1: ["imported pdfpc note"]})

    def test_reload_routes_through_wrapper_and_preserves_arguments(self):
        namespace, _, calls = self.execute_fixture()
        result = namespace["exit_relaunch"]("/some path/中文.pdf", 7)
        self.assertEqual(result, "wrapper relaunched")
        self.assertEqual(calls, [("/some path/中文.pdf", 7)])

    def test_finder_drop_guard_routes_through_filter_callback(self):
        namespace, _, _ = self.execute_fixture()
        wrapper = "/Applications/Présentation PDFPC.app/Contents/MacOS/presentation-pdfpc"
        upstream = "/Applications/Présentation.app/Contents/MacOS/presentation.py"
        document = "/Users/example/My talk/中文.pdf"
        seen = []
        def accept(filename):
            seen.append(filename)
            return filename not in (wrapper, upstream)
        namespace["__pdfpc_wrapper_accept_document__"] = accept
        delegate = namespace["DropApplicationDelegate"]()
        for filename in (wrapper, document, upstream):
            delegate.application_openFile_(None, filename)
        self.assertEqual(seen, [wrapper, document, upstream])
        self.assertEqual(namespace["args"], [document])

    def test_missing_or_changed_drop_guard_is_rejected(self):
        original = "if filename != os.path.abspath(__file__):"
        replacements = ["if True:", "if filename == os.path.abspath(__file__):",
                        "if filename != __file__:", "if other_filename != os.path.abspath(__file__):"]
        for replacement in replacements:
            with self.subTest(replacement=replacement), self.assertRaises(CompatibilityError):
                adapt_source(FIXTURE.replace(original, replacement), "fixture.py")
        with self.assertRaises(CompatibilityError):
            adapt_source(FIXTURE.replace("class DropApplicationDelegate(", "class RenamedDelegate("), "fixture.py")
        with self.assertRaises(CompatibilityError):
            adapt_source(FIXTURE.replace("def application_openFile_(", "def renamed_openFile_("), "fixture.py")

    def test_document_filter_excludes_executables_and_filesystem_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            launcher = base / "Présentation PDFPC"
            upstream = base / "Présentation.py"
            document = base / "my talk 中文.pdf"
            for path in (launcher, upstream, document):
                path.write_text("fixture")
            for executable in (launcher, upstream):
                symlink = base / (executable.name + ".symlink")
                symlink.symlink_to(executable)
                hardlink = base / (executable.name + ".hardlink")
                os.link(executable, hardlink)
                for alias in (executable, symlink, hardlink):
                    with self.subTest(alias=alias):
                        self.assertFalse(accept_document(alias, upstream, launcher))
            self.assertTrue(accept_document(document, upstream, launcher))

    def test_document_filter_tolerates_missing_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            document = base / "not-created.pdf"
            self.assertTrue(accept_document(document, base / "missing-upstream", base / "missing-wrapper"))

    def test_missing_or_renamed_required_helpers_fail_clearly(self):
        for name in ("cgpdf_get", "cgpdf_array2list", "cgpdf_stream2str", "annotations", "exit_relaunch"):
            with self.subTest(name=name), self.assertRaisesRegex(CompatibilityError, "helpers"):
                adapt_source(FIXTURE.replace("def " + name + "(", "def renamed_" + name + "("), "fixture.py")

    def test_missing_required_state_fails_clearly(self):
        for name in ("_pdf", "url", "page_count", "pdf_notes", "beamer_notes"):
            replacement = FIXTURE.replace(name, "renamed_" + name)
            with self.subTest(name=name), self.assertRaisesRegex(CompatibilityError, "state"):
                adapt_source(replacement, "fixture.py")

    def test_hook_state_initialization_after_hook_is_rejected(self):
        for assignment in ("_pdf = object()", 'url = "fixture.pdf"',
                           "page_count = 2", "pdf_notes = {}"):
            changed = FIXTURE.replace(assignment + "\n", "")
            changed = changed.replace("events.append(\"upstream continues\")",
                                      assignment + "\nevents.append(\"upstream continues\")")
            with self.subTest(assignment=assignment), self.assertRaises(CompatibilityError):
                adapt_source(changed, "fixture.py")

    def test_required_state_only_in_unrelated_function_is_rejected(self):
        for assignment in ("_pdf = object()", 'url = "fixture.pdf"',
                           "page_count = 2", "pdf_notes = {}"):
            changed = FIXTURE.replace(assignment + "\n", "")
            changed = "def unrelated():\n    " + assignment + "\n" + changed
            with self.subTest(assignment=assignment), self.assertRaises(CompatibilityError):
                adapt_source(changed, "fixture.py")

    def test_pdf_notes_reset_after_hook_is_rejected(self):
        changed = FIXTURE.replace("events.append(\"upstream continues\")",
                                  "pdf_notes = {}\nevents.append(\"upstream continues\")")
        with self.assertRaises(CompatibilityError):
            adapt_source(changed, "fixture.py")

    def test_renderer_before_hook_is_rejected(self):
        renderer = "renderer_sources = [pdf_notes, beamer_notes]"
        changed = FIXTURE.replace(renderer + "\n", "")
        changed = changed.replace("\nprepare_animations(widgets)\n",
                                  "\n" + renderer + "\nprepare_animations(widgets)\n")
        with self.assertRaises(CompatibilityError):
            adapt_source(changed, "fixture.py")

    def test_missing_duplicated_or_changed_hook_fails_clearly(self):
        call = "prepare_animations(widgets)\n"
        # Leading line boundary avoids changing the function declaration.
        call = "\n" + call
        changes = ["\n", call + call, "\nprepare_animations(other_widgets)\n",
                   "\nprepare_animations(widgets, extra_argument)\n"]
        for replacement in changes:
            with self.subTest(replacement=replacement), self.assertRaisesRegex(CompatibilityError, "rendering"):
                adapt_source(FIXTURE.replace(call, replacement), "fixture.py")

    def test_missing_duplicate_or_changed_renderer_fails_clearly(self):
        original = "renderer_sources = [pdf_notes, beamer_notes]"
        replacements = ["renderer_sources = []",
                        original + "\nother_renderer = [pdf_notes, beamer_notes]",
                        "renderer_sources = [beamer_notes, pdf_notes]",
                        "renderer_sources = [pdf_notes, beamer_notes, other_notes]"]
        for replacement in replacements:
            with self.subTest(replacement=replacement), self.assertRaisesRegex(CompatibilityError, "rendering"):
                adapt_source(FIXTURE.replace(original, replacement), "fixture.py")

    def test_changed_reload_parameters_fail_clearly(self):
        for signature in ("filename, page", "path", "path, page, extra"):
            with self.subTest(signature=signature), self.assertRaisesRegex(CompatibilityError, "reload arguments"):
                adapt_source(FIXTURE.replace("exit_relaunch(path, page)", "exit_relaunch(" + signature + ")"), "fixture.py")

    def test_syntax_error_reports_compatibility_error(self):
        with self.assertRaisesRegex(CompatibilityError, "Python version"):
            adapt_source("def invalid(\n", "fixture.py")

    def test_installed_upstream_compiles_without_disk_changes(self):
        try:
            app, script, info = find_upstream()
        except CompatibilityError as error:
            self.skipTest(str(error))
        before = script.read_bytes()
        stat_before = script.stat()
        plist_before = (app / "Contents/Info.plist").read_bytes()
        with mock.patch("builtins.exec", side_effect=AssertionError("upstream executed")):
            code = adapt_source(before.decode("utf-8"), str(script))
        self.assertIsInstance(code, types.CodeType)
        self.assertEqual(code.co_filename, str(script))
        self.assertEqual(info["CFBundleExecutable"], "presentation.py")
        self.assertEqual(hashlib.sha256(script.read_bytes()).digest(), hashlib.sha256(before).digest())
        self.assertEqual(script.stat().st_mtime_ns, stat_before.st_mtime_ns)
        self.assertEqual(script.stat().st_mode, stat_before.st_mode)
        self.assertEqual((app / "Contents/Info.plist").read_bytes(), plist_before)


if __name__ == "__main__":
    unittest.main()
