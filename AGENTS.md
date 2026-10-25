# Agent instructions

Read [README.md](README.md) first. It is the installation runbook.

- An installation request means install the existing macOS wrapper. Execute the
  documented preflight, installer, and checks; do not start the proposed rewrite.
- The existing app depends on Apple's Python and upstream's matching PyObjC.
  Do not substitute Homebrew Python or run `sudo pip` to work around a failed check.
- Preserve the original Présentation app and users' PDFs, notes, default PDF
  association, and editor configuration. The installer writes only user app bundles
  and temporary staging files; it does not require sudo.
- Do not disable Gatekeeper, strip quarantine recursively, or fabricate a passing
  installation report. Explain a concrete macOS prompt when one occurs.
- Before changing integration hooks, read `upstream_adapter.py` and its tests.
  Compatibility failures must be visible rather than silently dropping notes.
- Verify changes using `/usr/bin/python3 -m unittest discover -s tests -v`.
  Build to a temporary `--destination` to avoid replacing a working user app during
  development. Structural checks and runtime imports do not prove GUI behavior.
- The future independent Windows/macOS application is described only in
  [the proposal](docs/CROSS_PLATFORM_PROPOSAL.md). It is not implemented here.
  Do not copy this GPL implementation into a permissively licensed new app.
- No indexing or extra frameworks are needed for the current wrapper.
