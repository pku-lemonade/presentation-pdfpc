#!/bin/sh
# Run with Apple's Python: upstream's native bindings are version-specific.
set -eu
if [ "$(uname -s)" != Darwin ]; then
    echo 'This wrapper requires macOS. See docs/CROSS_PLATFORM_PROPOSAL.md for the proposed independent app.' >&2
    exit 1
fi
if ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
    echo 'Apple Command Line Tools are required. Run xcode-select --install, complete the Apple dialog, then retry.' >&2
    exit 1
fi
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 "$repo_dir/install.py" "$@"
