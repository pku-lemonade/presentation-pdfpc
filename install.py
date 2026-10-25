#!/usr/bin/python3
"""Install the notes wrapper and, if absent, the pinned upstream app per-user."""

import argparse
import hashlib
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
import tempfile

from build_wrapper import build
from upstream_adapter import BUNDLE_ID, CompatibilityError, adapt_source, check_runtime, find_upstream

UPSTREAM_URL = "https://iihm.imag.fr/blanch/software/osx-presentation/releases/osx-presentation-3.4.0.pkg"
UPSTREAM_SHA256 = "6fb258e6eec0407f1fb1d99064a53418da2a9865f74f2298c876694e76fe4209"


def run(*args):
    subprocess.run(args, check=True, cwd=Path(__file__).resolve().parent)


def verify_download(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != UPSTREAM_SHA256:
        raise RuntimeError("Upstream SHA-256 mismatch. Nothing was installed; do not bypass this check.")


def extract_upstream(package, expanded):
    verify_download(package)
    run("/usr/sbin/pkgutil", "--check-signature", str(package))
    run("/usr/sbin/pkgutil", "--expand-full", str(package), str(expanded))
    candidates = list(expanded.glob("*.pkg/Payload/*.app"))
    if len(candidates) != 1:
        raise RuntimeError("Unexpected upstream package layout")
    app = candidates[0]
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if (info.get("CFBundleIdentifier") != BUNDLE_ID
            or info.get("CFBundleShortVersionString") != "3.4.0"
            or info.get("CFBundleExecutable") != "presentation.py"):
        raise RuntimeError("Unexpected upstream application identity")
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", str(app))
    script = app / "Contents/MacOS/presentation.py"
    adapt_source(script.read_text(), str(script))
    # Run this in a fresh process: native modules must not retain staging paths.
    run("/usr/bin/python3", "-c",
        "import sys; from pathlib import Path; from upstream_adapter import check_runtime; "
        "check_runtime(Path(sys.argv[1]))", str(script))
    return app


def install_upstream():
    applications = Path.home() / "Applications"
    applications.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".presentation-upstream-", dir=applications) as temporary:
        stage = Path(temporary)
        package = stage / "upstream.pkg"
        run("/usr/bin/curl", "--fail", "--location", "--proto", "=https",
            "--proto-redir", "=https", "--connect-timeout", "30", "--max-time", "300",
            "--output", str(package), UPSTREAM_URL)
        app = extract_upstream(package, stage / "expanded")
        destination = applications / app.name
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Refusing to overwrite an existing app: " + str(destination))
        app.rename(destination)
        print("Installed upstream:", destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check installed dependencies without installing")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise RuntimeError("This wrapper supports macOS only")
    if os.geteuid() == 0:
        raise RuntimeError("Run as your normal user, without sudo")
    if tuple(int(x) for x in platform.mac_ver()[0].split(".")[:2]) < (12, 5):
        raise RuntimeError("macOS 12.5 or later is required by the pinned upstream app")
    try:
        upstream, script, info = find_upstream()
    except CompatibilityError as error:
        # Only absence authorizes a download; never replace an incompatible install.
        if args.check or str(error) != "Install Renaud Blanch's Présentation.app in Applications first.":
            raise
        install_upstream()
        upstream, script, info = find_upstream()
    adapt_source(script.read_text(), str(script))
    check_runtime(script)
    print("Compatible upstream:", upstream, info.get("CFBundleShortVersionString"))
    if not args.check:
        build()
    print("Dependency checks passed. A real presentation still needs a GUI/display check.")


if __name__ == "__main__":
    try:
        main()
    except (CompatibilityError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print("Installation stopped:", error, file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        sys.exit(1)
