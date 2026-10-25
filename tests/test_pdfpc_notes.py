import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdfpc_notes import (
    LoadResult,
    MAX_EMBEDDED_FILES,
    MAX_PDFPC_BYTES,
    PdfpcError,
    is_notes_filename,
    load_notes,
    parse_pdfpc,
)


def payload(pages=(), **kwargs):
    document = {"pdfpcFormat": 2, "pages": list(pages)}
    document.update(kwargs)
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


class ParseTests(unittest.TestCase):
    def test_unicode_crlf_bom_and_plain_text_survive(self):
        text = "  中文 😀 **plain**\r\nnext\rline  "
        result = parse_pdfpc(b"\xef\xbb\xbf" + payload([{"idx": 0, "note": text}]), 1)
        self.assertEqual(result, {0: ["  中文 😀 **plain**\nnext\rline  "]})

    def test_physical_pages_ignore_shared_logical_labels(self):
        self.assertEqual(
            parse_pdfpc(payload([
                {"idx": 0, "label": "1", "overlay": 0, "note": "first"},
                {"idx": 1, "label": "1", "overlay": 1, "note": "second"},
                {"idx": 2, "label": "500", "note": "third"},
                {"idx": 1, "note": "another block"},
            ]), 3),
            {0: ["first"], 1: ["second", "another block"], 2: ["third"]},
        )

    def test_malformed_entries_skipped_with_warning(self):
        bad = [None, [], "page", {}, {"idx": True, "note": "bad"},
               {"idx": 1.0, "note": "bad"}, {"idx": "1", "note": "bad"},
               {"idx": -1, "note": "bad"}, {"idx": 2, "note": "bad"},
               {"idx": 0, "note": None}, {"idx": 0, "note": ["bad"]}]
        seen = []
        result = parse_pdfpc(payload(bad + [{"idx": 1, "note": "good"}]), 2, seen.append)
        self.assertEqual(result, {1: ["good"]})
        self.assertEqual(len(seen), len(bad))

    def test_empty_and_absent_notes(self):
        self.assertEqual(parse_pdfpc(payload(), 0), {})
        self.assertEqual(parse_pdfpc(payload([{"idx": 0}, {"idx": 0, "note": ""}]), 1), {})
        self.assertEqual(parse_pdfpc(payload([{"idx": 0, "note": " "}]), 1), {0: [" "]})

    def test_invalid_documents(self):
        documents = [b"", b"bad", b"\xff", b"[]", b"null", b"{}",
                     payload(pdfpcFormat=1), payload(pdfpcFormat=True),
                     payload(pdfpcFormat=2.0), payload(pdfpcFormat="2"),
                     b'{"pdfpcFormat":2,"pages":null}',
                     b'{"pdfpcFormat":2,"pages":NaN}', b"[" * 2000]
        for data in documents:
            with self.subTest(data=data[:60]), self.assertRaises(PdfpcError):
                parse_pdfpc(data, 1)

    def test_invalid_note_unicode_skipped(self):
        seen = []
        self.assertEqual(parse_pdfpc(b'{"pdfpcFormat":2,"pages":[{"idx":0,"note":"\\ud800"}]}', 1, seen.append), {})
        self.assertEqual(len(seen), 1)

    def test_input_and_page_count_bounds(self):
        for count in (-1, True, 1.5, "1"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                parse_pdfpc(payload(), count)
        with self.assertRaises(PdfpcError):
            parse_pdfpc("{}", 1)
        with self.assertRaisesRegex(PdfpcError, "4 MiB"):
            parse_pdfpc(b" " * (MAX_PDFPC_BYTES + 1), 1)
        valid = payload()
        self.assertEqual(parse_pdfpc(valid + b" " * (MAX_PDFPC_BYTES - len(valid)), 0), {})


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.pdf = Path(self.directory.name) / "a.deck.pdf"
        self.sidecar = self.pdf.with_suffix(".pdfpc")
        self.warnings = []

    def load(self, attachments=None):
        loader = None if attachments is None else lambda: iter(attachments)
        return load_notes(self.pdf, 3, loader, self.warnings.append)

    def test_missing_files_normal_empty(self):
        self.assertEqual(self.load(), LoadResult({}, None))
        self.assertEqual(self.warnings, [])

    def test_adjacent_sidecar_exact_name(self):
        (self.pdf.parent / "unrelated.pdfpc").write_bytes(payload([{"idx": 0, "note": "wrong"}]))
        self.assertEqual(self.load(), LoadResult({}, None))
        self.sidecar.write_bytes(payload([{"idx": 2, "note": "correct"}]))
        self.assertEqual(self.load(), LoadResult({2: ["correct"]}, str(self.sidecar)))

    def test_embedded_precedence_no_sidecar_duplicate(self):
        data = payload([{"idx": 1, "note": "embedded"}])
        self.sidecar.write_bytes(data)
        self.assertEqual(self.load([("deck.pdfpc", data)]), LoadResult({1: ["embedded"]}, "embedded:deck.pdfpc"))

    def test_embedded_empty_authoritative(self):
        self.sidecar.write_bytes(payload([{"idx": 0, "note": "stale"}]))
        self.assertEqual(self.load([("speaker-notes.json", payload())]), LoadResult({}, "embedded:speaker-notes.json"))

    def test_invalid_attachment_try_next_and_skip_other_files(self):
        self.sidecar.write_bytes(payload([{"idx": 0, "note": "sidecar"}]))
        good = payload([{"idx": 1, "note": "中文"}])
        self.assertEqual(self.load([
            ("unrelated.json", b"invalid"), ("old.pdfpc", payload(pdfpcFormat=1)),
            ("bad.pdfpc", b"broken"), ("SPEAKER-NOTES.JSON", good),
        ]), LoadResult({1: ["中文"]}, "embedded:SPEAKER-NOTES.JSON"))
        self.assertEqual(len(self.warnings), 2)

    def test_failed_attachments_fall_back(self):
        self.sidecar.write_bytes(payload([{"idx": 0, "note": "fallback"}]))
        self.assertEqual(self.load([("broken.pdfpc", b"{")]).notes, {0: ["fallback"]})
        self.assertTrue(self.warnings)

    def test_extraction_failure_falls_back(self):
        self.sidecar.write_bytes(payload([{"idx": 0, "note": "fallback"}]))
        def failing_loader():
            raise RuntimeError("broken PDF attachment tree")
        result = load_notes(self.pdf, 3, failing_loader, self.warnings.append)
        self.assertEqual(result.notes, {0: ["fallback"]})
        self.assertIn("broken PDF attachment tree", self.warnings[0])

    def test_scan_is_bounded(self):
        count = [0]
        def endless():
            while True:
                count[0] += 1
                yield "media.mov", b""
        self.assertEqual(load_notes(self.pdf, 3, endless, self.warnings.append), LoadResult({}, None))
        self.assertEqual(count[0], MAX_EMBEDDED_FILES)
        self.assertEqual(len(self.warnings), 1)

    def test_malformed_pairs_and_bytes_are_skipped(self):
        good = payload([{"idx": 0, "note": "good"}])
        result = self.load([None, ("x.pdfpc",), ("bad.pdfpc", "text"), ("good.pdfpc", good)])
        self.assertEqual(result.notes, {0: ["good"]})
        self.assertEqual(len(self.warnings), 3)

    def test_malformed_sidecar_and_oversize_attachment(self):
        self.sidecar.write_bytes(b"invalid")
        self.assertEqual(self.load([("huge.pdfpc", b" " * (MAX_PDFPC_BYTES + 1))]), LoadResult({}, None))
        self.assertEqual(len(self.warnings), 2)

    def test_invalid_sidecar_read_is_nonfatal(self):
        self.sidecar.mkdir()
        self.assertEqual(self.load(), LoadResult({}, None))
        self.assertEqual(len(self.warnings), 1)

    def test_filename_filter(self):
        for name in ("x.pdfpc", "x.PDFPC", "folder/speaker-notes.json", "C:\\folder\\SPEAKER-NOTES.JSON"):
            self.assertTrue(is_notes_filename(name), name)
        for name in (None, 7, "notes.json", "movie.mp4", "x.pdfpc.txt", "speaker-notes.json/"):
            self.assertFalse(is_notes_filename(name), name)


if __name__ == "__main__":
    unittest.main()
