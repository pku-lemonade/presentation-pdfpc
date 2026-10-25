#!/usr/bin/python3
"""Build a small local launcher; the upstream Présentation.app stays untouched."""

import ast
import argparse
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile

from upstream_adapter import adapt_source, check_runtime, find_upstream

SOURCE = Path(__file__).resolve().parent
DESTINATION = Path.home() / "Applications" / "Présentation PDFPC.app"
MODULES = ("pdfpc_notes.py", "presentation_pdfpc.py", "upstream_adapter.py")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def build(destination=DESTINATION):
    destination = Path(destination).expanduser().absolute()
    if destination.suffix != ".app":
        raise ValueError("Destination must end in .app")
    if destination.is_symlink():
        raise RuntimeError("Refusing to replace a symbolic link: " + str(destination))
    upstream, script, _ = find_upstream()
    adapt_source(script.read_text(), str(script))
    check_runtime(script)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".presentation-pdfpc-", dir=destination.parent))
    stage = temp / destination.name
    committed = False
    try:
        macos = stage / "Contents/MacOS"
        resources = stage / "Contents/Resources"
        macos.mkdir(parents=True)
        resources.mkdir()
        for name in MODULES:
            ast.parse((SOURCE / name).read_text())
            shutil.copy2(SOURCE / name, resources / name)
        for name in ("LICENSE", "NOTICE.md"):
            shutil.copy2(SOURCE / name, resources / name)
        shutil.copy2(SOURCE / "wrapper.py", macos / "presentation-pdfpc")
        (macos / "presentation-pdfpc").chmod(0o755)

        # Reuse the upstream icon distributed under its original license.
        upstream_icons = list((upstream / "Contents/Resources").glob("*.icns"))
        icon_name = None
        if upstream_icons:
            icon_name = upstream_icons[0].name
            shutil.copy2(upstream_icons[0], resources / icon_name)
        info = {
            "CFBundleIdentifier": "xyz.youwei.presentation-pdfpc",
            "CFBundleName": "Présentation PDFPC",
            "CFBundleDisplayName": "Présentation PDFPC",
            "CFBundleExecutable": "presentation-pdfpc",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.1.0",
            "CFBundleVersion": "2",
            "LSMinimumSystemVersion": "12.5",
            "NSHighResolutionCapable": True,
            "NSCameraUsageDescription": "Show the presenter's camera in the presentation.",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "PDF document",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["com.adobe.pdf"],
            }],
            "NSHumanReadableCopyright": (
                "PDFPC notes wrapper, GPLv3-or-later. Présentation.app by Renaud Blanch."
            ),
        }
        if icon_name:
            info["CFBundleIconFile"] = icon_name
        (stage / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
        entitlements = temp / "entitlements.plist"
        entitlements.write_bytes(plistlib.dumps({
            "com.apple.security.cs.allow-unsigned-executable-memory": True,
            "com.apple.security.device.camera": True,
        }))
        run("/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none",
            "--options", "runtime", "--entitlements", str(entitlements), str(stage))
        run("/usr/bin/codesign", "--verify", "--deep", "--strict", str(stage))
        run(str(macos / "presentation-pdfpc"), "--runtime-check")
        if destination.exists():
            # Only replace our own identified wrapper bundle.
            existing = plistlib.loads((destination / "Contents/Info.plist").read_bytes())
            if existing.get("CFBundleIdentifier") != info["CFBundleIdentifier"]:
                raise RuntimeError("Refusing to replace a different application at " + str(destination))
            destination.rename(temp / "previous.app")
        try:
            stage.rename(destination)
            committed = True
        except Exception:
            if (temp / "previous.app").exists():
                (temp / "previous.app").rename(destination)
            raise
        print("Installed wrapper:", destination)
        print("Upstream remains unchanged:", upstream)
    finally:
        if not committed and (temp / "previous.app").exists():
            print("Recovery copy retained:", temp / "previous.app")
        else:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DESTINATION)
    args = parser.parse_args()
    build(args.destination)
