"""Render the real upstream presenter view through the wrapper adapter.

Usage: /usr/bin/python3 tests/gui_smoke.py INPUT.pdf OUTPUT_DIRECTORY
This draws AppKit views directly, without requiring screen-recording permission.
"""

import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1]
BUNDLE = Path.home() / "Applications/Présentation PDFPC.app"
sys.path.insert(0, str(SOURCE))

from presentation_pdfpc import attach_notes
from upstream_adapter import adapt_source, find_upstream


def main():
    pdf = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app, script, _ = find_upstream()
    source = script.read_text()
    assert source.count("sys.exit(app.run())") == 1
    source = source.replace("sys.exit(app.run())", "__pdfpc_test_render__(globals())")
    code = adapt_source(source, str(script))
    sys.argv = [str(BUNDLE / "Contents/MacOS/presentation-pdfpc"), "--page", "0", str(pdf)]

    def render(ns):
        from AppKit import NSPNGFileType
        records = []
        for page in range(ns["page_count"]):
            ns["goto_page"](page)
            view = ns["presenter_view"]
            view.setNeedsDisplay_(True)
            bitmap = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
            view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), bitmap)
            png = bitmap.representationUsingType_properties_(NSPNGFileType, {})
            (output / ("page-%02d.png" % (page + 1))).write_bytes(bytes(png))
            records.append(dict(page=page, notes=ns["pdf_notes"].get(page, [])))
        (output / "notes.json").write_text(json.dumps(dict(
            source=ns.get("_pdfpc_note_source"), added=ns.get("_pdfpc_notes_added"),
            records=records), ensure_ascii=False, indent=2))
        ns["cleanup_tmp"]()
        print("Rendered", len(records), "presenter pages; imported", ns.get("_pdfpc_notes_added"), "notes")

    namespace = dict(__name__="__main__", __file__=str(script), __package__=None,
                     __builtins__=__builtins__, __pdfpc_wrapper_attach__=attach_notes,
                     __pdfpc_wrapper_relaunch__=lambda path, page: None,
                     __pdfpc_wrapper_accept_document__=lambda filename: filename.endswith(".pdf"),
                     __pdfpc_test_render__=render)
    exec(code, namespace)


if __name__ == "__main__":
    main()
