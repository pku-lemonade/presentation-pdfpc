"""Read embedded pdfpc notes through Présentation's existing CoreGraphics bridge.

This module is injected after upstream's PDF annotation loading. It does not
change the PDF, launch Cocoa, or replace upstream's annotation notes.
"""

import sys

from pdfpc_notes import (
    LoadResult,
    MAX_EMBEDDED_FILES,
    MAX_PDFPC_BYTES,
    is_notes_filename,
    load_notes,
)


MAX_TREE_DEPTH = 16
MAX_TREE_NODES = 512


def _warn(message):
    """Keep diagnostics brief and never print the contents of a note."""
    message = str(message).replace("\r", " ").replace("\n", " ")[:400]
    print("[PresentationPDFPC] " + message, file=sys.stderr)


def iter_embedded_notes(namespace, warn=None):
    """Yield supported attachment names and bytes without extracting other media.

    Both flat and nested PDF name trees are supported. The size declared by the
    PDF is checked before decompression where available, then the actual size
    is checked too. CoreGraphics itself allocates a decoded stream in one call.
    """
    warn = warn or _warn
    from Quartz import (
        CGPDFArrayGetCount,
        CGPDFDictionaryGetObject,
        CGPDFDocumentGetCatalog,
        CGPDFObjectGetType,
        CGPDFObjectGetValue,
    )

    get = namespace["cgpdf_get"]

    def optional(obj, *path):
        try:
            return get(obj, *path)
        except LookupError:
            return None

    def raw_field(obj, key):
        # cgpdf_get converts terminal stream objects to bytes. Keep the stream
        # reference here so its size can be checked before that conversion.
        ok, value = CGPDFDictionaryGetObject(obj, key.encode("ascii"), None)
        if not ok:
            raise LookupError("missing embedded-file stream")
        ok, value = CGPDFObjectGetValue(value, CGPDFObjectGetType(value), None)
        if not ok:
            raise TypeError("invalid embedded-file stream")
        return value

    try:
        catalog = CGPDFDocumentGetCatalog(namespace["_pdf"])
        tree = optional(catalog, "Names", "EmbeddedFiles")
    except Exception as error:
        warn("Cannot read embedded-file catalog (%s)." % type(error).__name__)
        return
    if tree is None:
        return

    nodes_seen = 0
    files_seen = 0
    stack = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        nodes_seen += 1
        if nodes_seen > MAX_TREE_NODES:
            warn("Embedded-file name tree exceeds the node limit; remaining branches skipped.")
            return
        if depth > MAX_TREE_DEPTH:
            warn("Embedded-file name tree exceeds the depth limit; branch skipped.")
            continue

        try:
            names = optional(node, "Names")
            count = CGPDFArrayGetCount(names) if names is not None else 0
            if count % 2:
                warn("Malformed embedded-file name array; incomplete final entry skipped.")
            for index in range(0, count - 1, 2):
                files_seen += 1
                if files_seen > MAX_EMBEDDED_FILES:
                    warn("Embedded-file count exceeds the limit; remaining files skipped.")
                    return
                try:
                    key = get(names, index)
                    spec = get(names, index + 1)
                    candidates = [optional(spec, "UF"), optional(spec, "F"), key]
                    name = next((str(value) for value in candidates
                                 if value is not None and is_notes_filename(str(value))), None)
                    if name is None:
                        continue
                    streams = get(spec, "EF")
                    stream = None
                    for field in ("UF", "F"):
                        try:
                            stream = raw_field(streams, field)
                            break
                        except LookupError:
                            pass
                    if stream is None:
                        raise LookupError("missing embedded-file stream")
                    for path in (("Length",), ("Params", "Size")):
                        size = optional(stream, *path)
                        if isinstance(size, (int, float)) and size > MAX_PDFPC_BYTES:
                            raise ValueError("embedded notes exceed the size limit")
                    payload = bytes(get(stream))
                    if len(payload) > MAX_PDFPC_BYTES:
                        raise ValueError("embedded notes exceed the size limit")
                    yield name, payload
                except Exception as error:
                    warn("Embedded notes entry skipped (%s)." % type(error).__name__)
        except Exception as error:
            warn("Malformed embedded-file name branch skipped (%s)." % type(error).__name__)

        # A malformed Names branch must not suppress otherwise valid children.
        try:
            kids = optional(node, "Kids")
            if kids is not None:
                count = CGPDFArrayGetCount(kids)
                remaining = MAX_TREE_NODES - nodes_seen - len(stack)
                if count > remaining:
                    warn("Embedded-file child count exceeds the limit; extra branches skipped.")
                    count = max(0, remaining)
                for index in reversed(range(count)):
                    try:
                        stack.append((get(kids, index), depth + 1))
                    except Exception as error:
                        warn("Malformed embedded-file child skipped (%s)." % type(error).__name__)
        except Exception as error:
            warn("Malformed embedded-file children skipped (%s)." % type(error).__name__)


def attach_notes(namespace):
    """Fill pages with imported notes only when upstream has no annotation notes.

    Source selection and pdfpc parsing belong to ``pdfpc_notes.load_notes``.
    The returned result describes the selected source, even when PDF annotation
    notes already cover all of its pages. ``_pdfpc_notes_added`` counts pages
    whose presenter notes actually changed.
    """
    namespace["_pdfpc_note_source"] = None
    namespace["_pdfpc_notes_added"] = 0
    try:
        result = load_notes(
            str(namespace["url"].path()),
            namespace["page_count"],
            embedded_loader=lambda: iter_embedded_notes(namespace, _warn),
            warn=_warn,
        )
        notes = namespace["pdf_notes"]
        for page, imported in result.notes.items():
            if not notes.get(page) and imported:
                notes[page] = list(imported)
                namespace["_pdfpc_notes_added"] += 1
        namespace["_pdfpc_note_source"] = result.source
        return result
    except Exception as error:
        # A malformed optional notes source must not prevent a presentation.
        _warn("Optional pdfpc notes could not be loaded (%s)." % type(error).__name__)
        return LoadResult(notes={}, source=None)
