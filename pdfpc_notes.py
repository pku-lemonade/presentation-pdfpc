"""Read pdfpc format 2 speaker notes without changing presentation metadata.

Notes are indexed by physical, zero-based PDF page. Logical labels, overlays,
timers, and navigation settings are deliberately not interpreted here.
"""

import json
import os
import warnings
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple


MAX_PDFPC_BYTES = 4 * 1024 * 1024
MAX_EMBEDDED_FILES = 128
Warn = Optional[Callable[[str], None]]


class PdfpcError(ValueError):
    """The supplied file is not a supported, valid pdfpc notes document."""


@dataclass(frozen=True)
class LoadResult:
    notes: Dict[int, List[str]]
    source: Optional[str]


def _warn(warn: Warn, message: str) -> None:
    if warn is None:
        warnings.warn(message, RuntimeWarning, stacklevel=3)
    else:
        warn(message)


def _validate_page_count(page_count: int) -> None:
    if type(page_count) is not int or page_count < 0:
        raise ValueError("page_count must be a nonnegative integer")


def is_notes_filename(name: str) -> bool:
    """Identify supported attachment names before any stream is decompressed."""
    if not isinstance(name, str):
        return False
    basename = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return basename.endswith(".pdfpc") or basename == "speaker-notes.json"


def _reject_json_constant(value: str) -> None:
    raise ValueError("nonstandard JSON constant: " + value)


def parse_pdfpc(data: bytes, page_count: int, warn: Warn = None) -> Dict[int, List[str]]:
    """Parse UTF-8 format 2 JSON, skipping malformed individual page entries.

    Input must be at most MAX_PDFPC_BYTES. A UTF-8 BOM is accepted. The original
    plain note text is retained, except that CRLF becomes LF. Missing and empty
    note strings add no notes; multiple entries for one physical page retain
    their order. No logical label is used to infer a page number.
    """
    _validate_page_count(page_count)
    if not isinstance(data, (bytes, bytearray)):
        raise PdfpcError("pdfpc input must be UTF-8 bytes")
    if len(data) > MAX_PDFPC_BYTES:
        raise PdfpcError("pdfpc input exceeds the 4 MiB limit")
    try:
        document = json.loads(data.decode("utf-8-sig"), parse_constant=_reject_json_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise PdfpcError("invalid UTF-8 pdfpc JSON: {}".format(error)) from error
    if not isinstance(document, dict):
        raise PdfpcError("pdfpc document must be a JSON object")
    version = document.get("pdfpcFormat")
    if type(version) is not int or version != 2:
        raise PdfpcError("unsupported pdfpcFormat {!r}; expected integer 2".format(version))
    pages = document.get("pages")
    if not isinstance(pages, list):
        raise PdfpcError("pdfpc pages must be an array")

    notes: Dict[int, List[str]] = {}
    for entry_number, entry in enumerate(pages):
        prefix = "pdfpc pages[{}]".format(entry_number)
        if not isinstance(entry, dict):
            _warn(warn, prefix + ": expected an object; skipped")
            continue
        index = entry.get("idx")
        if type(index) is not int or not 0 <= index < page_count:
            _warn(warn, prefix + ": idx must be an in-range physical page integer; skipped")
            continue
        if "note" not in entry:
            continue
        note = entry["note"]
        if not isinstance(note, str):
            _warn(warn, prefix + ": note must be a string; skipped")
            continue
        try:
            note.encode("utf-8")
        except UnicodeError:
            _warn(warn, prefix + ": note contains an invalid Unicode surrogate; skipped")
            continue
        if note:
            notes.setdefault(index, []).append(note.replace("\r\n", "\n"))
    return notes


def load_notes(
    pdf_path: str,
    page_count: int,
    embedded_loader: Optional[Callable[[], Iterable[Tuple[str, bytes]]]] = None,
    warn: Warn = None,
) -> LoadResult:
    """Choose one notes source: first valid attachment, then adjacent sidecar.

    ``embedded_loader()`` yields ``(filename, bytes)`` pairs in the adapter's
    stable document order. A valid empty attachment is authoritative. Failed
    candidates warn and allow the next candidate or sidecar to be tried. The
    fallback is exactly the PDF path with its final extension replaced by
    ``.pdfpc``; no directory search or timestamp heuristic is used.
    """
    _validate_page_count(page_count)
    if embedded_loader is not None:
        try:
            attachments = iter(embedded_loader())
            for _ in range(MAX_EMBEDDED_FILES):
                try:
                    attachment = next(attachments)
                except StopIteration:
                    break
                if not isinstance(attachment, (tuple, list)) or len(attachment) != 2:
                    _warn(warn, "embedded pdfpc attachment entry is not a name/data pair; skipped")
                    continue
                name, data = attachment
                if not is_notes_filename(name):
                    continue
                try:
                    notes = parse_pdfpc(data, page_count, warn=warn)
                except PdfpcError as error:
                    _warn(warn, "embedded {!r}: {}; trying another source".format(name, error))
                    continue
                return LoadResult(notes, "embedded:" + name)
            else:
                _warn(warn, "embedded attachment scan reached the {} entry limit".format(MAX_EMBEDDED_FILES))
        except Exception as error:
            # Native PDF extraction may fail on an individual document. Notes
            # failure must not prevent that PDF from opening for presentation.
            _warn(warn, "could not read embedded pdfpc notes: {}; trying sidecar".format(error))

    sidecar = os.path.splitext(os.path.abspath(os.fspath(pdf_path)))[0] + ".pdfpc"
    try:
        with open(sidecar, "rb") as stream:
            data = stream.read(MAX_PDFPC_BYTES + 1)
    except FileNotFoundError:
        return LoadResult({}, None)
    except OSError as error:
        _warn(warn, "could not read pdfpc sidecar {!r}: {}".format(sidecar, error))
        return LoadResult({}, None)
    try:
        notes = parse_pdfpc(data, page_count, warn=warn)
    except PdfpcError as error:
        _warn(warn, "pdfpc sidecar {!r}: {}".format(sidecar, error))
        return LoadResult({}, None)
    return LoadResult(notes, sidecar)
