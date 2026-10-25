#!/usr/bin/python3
"""Launch the installed Présentation.app with local pdfpc notes support."""

import os
from pathlib import Path
import subprocess
import sys

LAUNCHER = Path(__file__).resolve()
RESOURCES = LAUNCHER.parent.parent / "Resources"
if RESOURCES.is_dir():
    sys.path.insert(0, str(RESOURCES))

from upstream_adapter import CompatibilityError, adapt_source, check_runtime, find_upstream


def relaunch(path, page, launcher=str(LAUNCHER)):
    os.execv(launcher, [launcher, "--page", str(page), os.fspath(path)])


def accept_document(filename, upstream, launcher=LAUNCHER):
    # Launch Services sends the executable itself before the actual dropped PDF.
    # samefile handles NFC/NFD spellings of Présentation on macOS filesystems.
    for executable in (launcher, upstream):
        try:
            if os.path.samefile(filename, executable):
                return False
        except OSError:
            pass
    return True


def report_error(message):
    print("Présentation PDFPC: " + message, file=sys.stderr)
    if "presentation" in os.environ.get("XPC_SERVICE_NAME", ""):
        script = ('on run argv\n'
                  'display alert "Présentation PDFPC" message (item 1 of argv) '
                  'as warning buttons {"OK"} default button "OK"\nend run')
        subprocess.run(["/usr/bin/osascript", "-e", script, message], check=False)


def main():
    try:
        app, script, info = find_upstream()
        code = adapt_source(script.read_text(), str(script))
        if sys.argv[1:] == ["--runtime-check"]:
            check_runtime(script)
    except (CompatibilityError, OSError) as error:
        report_error(str(error))
        return 1
    if sys.argv[1:] in (["--wrapper-check"], ["--runtime-check"]):
        print("Upstream:", app)
        print("Version:", info.get("CFBundleShortVersionString"))
        print("Notes and reload integration: compatible")
        if sys.argv[1:] == ["--runtime-check"]:
            print("Python and macOS framework bindings: compatible")
        return 0

    from presentation_pdfpc import attach_notes
    namespace = {
        "__name__": "__main__",
        "__file__": str(script),
        "__package__": None,
        "__builtins__": __builtins__,
        "__pdfpc_wrapper_attach__": attach_notes,
        "__pdfpc_wrapper_relaunch__": relaunch,
        "__pdfpc_wrapper_accept_document__": lambda filename: accept_document(filename, script),
    }
    # __file__ continues to point at upstream so its version-matched PyObjC
    # bindings are found after an app upgrade. sys.argv[0] remains this wrapper.
    exec(code, namespace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
