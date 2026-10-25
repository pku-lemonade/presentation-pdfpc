"""Integration checks against macOS CoreGraphics and upstream's own PDF helpers."""

import ast
from collections import defaultdict
import importlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock
import zlib


SUPPORT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUPPORT))
from upstream_adapter import CompatibilityError, find_upstream


def _load_native_helpers():
    if sys.platform != "darwin":
        raise unittest.SkipTest("Native PDF checks require macOS")
    try:
        app, _, _ = find_upstream()
    except CompatibilityError as error:
        raise unittest.SkipTest(str(error)) from error
    version = "%s.%s" % sys.version_info[:2]
    sys.path.insert(0, str(app / "Contents/Resources/packages" / version))
    try:
        quartz = importlib.import_module("Quartz")
        foundation = importlib.import_module("Foundation")
    except ImportError as error:
        raise unittest.SkipTest("Run native tests with /usr/bin/python3 and bundled PyObjC") from error
    source = (app / "Contents/MacOS/presentation.py").read_text()
    functions = {"cgpdf_dictionary2dict", "cgpdf_array2list", "cgpdf_stream2str", "cgpdf_get"}
    tree = ast.parse(source)
    helpers = [node for node in tree.body
               if isinstance(node, ast.FunctionDef) and node.name in functions]
    if len(helpers) != len(functions):
        raise RuntimeError("Upstream PDF helper functions have changed")
    names = ["CGPDFDictionaryApplyFunction", "CGPDFDictionaryRef", "CGPDFArrayRef",
             "CGPDFStreamRef", "CGPDFStringRef", "CGPDFDictionaryGetObject",
             "CGPDFArrayGetCount", "CGPDFArrayGetObject", "CGPDFObjectGetType",
             "CGPDFObjectGetValue", "CGPDFStreamGetDictionary", "CGPDFStreamCopyData",
             "CGPDFDataFormatRaw", "CGPDFStringCopyTextString"]
    namespace = {name: getattr(quartz, name) for name in names}
    module = ast.Module(body=helpers, type_ignores=[])
    exec(compile(module, str(app / "Contents/MacOS/presentation.py"), "exec"), namespace)
    return namespace, quartz, foundation


def _write_pdf(path, payload=None, nested=False, malformed=False,
               declared_size=None, attachment_name="speaker-notes.json", unicode_field=False):
    """Write a one-page PDF; avoid adding a PDF library just for these fixtures."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 640 360] /Resources <<>> >>",
    ]
    if payload is not None:
        objects[0] = b"<< /Type /Catalog /Pages 2 0 R /Names << /EmbeddedFiles 4 0 R >> >>"
        name = attachment_name.encode("ascii")
        names = b"<< /Names [(" + name + b") 5 0 R] >>"
        objects.append(b"<< /Kids [7 0 R] >>" if nested else names)
        field = b"UF" if unicode_field else b"F"
        objects.append(b"<< /Type /Filespec /" + field + b" (" + name +
                       b") /EF << /" + field + b" 6 0 R >> >>")
        compressed = zlib.compress(payload)
        size = len(payload) if declared_size is None else declared_size
        objects.append(("<< /Type /EmbeddedFile /Filter /FlateDecode /Length %d "
                        "/Params << /Size %d >> >>\nstream\n" % (len(compressed), size)).encode()
                       + compressed + b"\nendstream")
        if nested:
            if malformed:
                # The malformed parent must not suppress its valid child.
                objects[3] = b"<< /Names [(incomplete)] /Kids [7 0 R] >>"
            objects.append(names)
    body = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body.extend(("%d 0 obj\n" % number).encode() + obj + b"\nendobj\n")
    xref = len(body)
    body.extend(("xref\n0 %d\n0000000000 65535 f \n" % len(offsets)).encode())
    for offset in offsets[1:]:
        body.extend(("%010d 00000 n \n" % offset).encode())
    body.extend(("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                 % (len(offsets), xref)).encode())
    path.write_bytes(body)


class NativePdfpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers, cls.quartz, cls.foundation = _load_native_helpers()
        cls.bridge = importlib.import_module("presentation_pdfpc")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="presentation-native-test-")
        self.addCleanup(self.temp.cleanup)
        self.pdf_path = pathlib.Path(self.temp.name) / "slides.pdf"
        self.payload = json.dumps({"pdfpcFormat": 2, "pages": [
            {"idx": 0, "note": "中文备注：保持 Unicode。\nSecond line."}
        ]}, ensure_ascii=False).encode("utf-8")

    def namespace(self, path=None):
        path = path or self.pdf_path
        url = self.foundation.NSURL.fileURLWithPath_(str(path))
        doc = self.quartz.CGPDFDocumentCreateWithURL(url)
        if doc is None:
            raise AssertionError("CoreGraphics could not open the test PDF")
        result = dict(self.helpers)
        result.update(_pdf=doc, url=url, pdf_notes=defaultdict(list),
                      page_count=self.quartz.CGPDFDocumentGetNumberOfPages(doc))
        return result

    def test_compressed_utf8_attachment(self):
        _write_pdf(self.pdf_path, self.payload)
        namespace = self.namespace()
        self.assertEqual(list(self.bridge.iter_embedded_notes(namespace)),
                         [("speaker-notes.json", self.payload)])
        result = self.bridge.attach_notes(namespace)
        self.assertEqual(result.source, "embedded:speaker-notes.json")
        self.assertEqual(namespace["pdf_notes"][0], ["中文备注：保持 Unicode。\nSecond line."])
        self.assertEqual(namespace["_pdfpc_notes_added"], 1)

    def test_nested_name_tree_and_uf_stream(self):
        _write_pdf(self.pdf_path, self.payload, nested=True, unicode_field=True,
                   attachment_name="slides.PDFPC")
        self.assertEqual(list(self.bridge.iter_embedded_notes(self.namespace())),
                         [("slides.PDFPC", self.payload)])

    def test_malformed_parent_does_not_suppress_valid_child(self):
        _write_pdf(self.pdf_path, self.payload, nested=True, malformed=True)
        warnings = []
        found = list(self.bridge.iter_embedded_notes(self.namespace(), warnings.append))
        self.assertEqual(found, [("speaker-notes.json", self.payload)])
        self.assertTrue(any("Malformed" in message for message in warnings))

    def test_skip_unrelated_media_before_stream_decoding(self):
        _write_pdf(self.pdf_path, self.payload, attachment_name="video.mp4")
        namespace = self.namespace()
        original_get = namespace["cgpdf_get"]
        decoded = []

        def tracked_get(obj, *path):
            if not path and isinstance(obj, self.quartz.CGPDFStreamRef):
                decoded.append(True)
            return original_get(obj, *path)

        namespace["cgpdf_get"] = tracked_get
        self.assertEqual(list(self.bridge.iter_embedded_notes(namespace)), [])
        self.assertEqual(decoded, [])

    def test_declared_oversized_payload_is_rejected_before_decoding(self):
        _write_pdf(self.pdf_path, self.payload, declared_size=self.bridge.MAX_PDFPC_BYTES + 1)
        warnings = []
        self.assertEqual(list(self.bridge.iter_embedded_notes(self.namespace(), warnings.append)), [])
        self.assertTrue(warnings)

    def test_real_pdf_annotations_take_precedence_and_repeated_attach_is_idempotent(self):
        _write_pdf(self.pdf_path, self.payload)
        namespace = self.namespace()
        namespace["pdf_notes"][0] = ["Original PDF annotation"]
        self.bridge.attach_notes(namespace)
        self.assertEqual(namespace["pdf_notes"][0], ["Original PDF annotation"])
        self.assertEqual(namespace["_pdfpc_notes_added"], 0)
        namespace["pdf_notes"].clear()
        self.bridge.attach_notes(namespace)
        imported = list(namespace["pdf_notes"][0])
        self.bridge.attach_notes(namespace)
        self.assertEqual(namespace["pdf_notes"][0], imported)
        self.assertEqual(namespace["_pdfpc_notes_added"], 0)

    def test_sidecar_integration_without_pdf_attachment(self):
        _write_pdf(self.pdf_path)
        sidecar = self.pdf_path.with_suffix(".pdfpc")
        sidecar.write_bytes(self.payload)
        namespace = self.namespace()
        result = self.bridge.attach_notes(namespace)
        self.assertEqual(result.source, str(sidecar))
        self.assertEqual(namespace["_pdfpc_notes_added"], 1)
        self.assertIn("中文备注", namespace["pdf_notes"][0][0])

    def test_optional_loader_failure_does_not_interrupt_presentation(self):
        _write_pdf(self.pdf_path)
        namespace = self.namespace()
        with mock.patch.object(self.bridge, "load_notes", side_effect=ValueError("secret note")):
            with mock.patch.object(self.bridge, "_warn") as warning:
                result = self.bridge.attach_notes(namespace)
        self.assertEqual(result.notes, {})
        self.assertNotIn("secret note", warning.call_args.args[0])

if __name__ == "__main__":
    unittest.main()
