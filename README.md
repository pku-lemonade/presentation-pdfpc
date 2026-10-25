# Présentation PDFPC

A macOS extension for [Présentation.app](https://iihm.imag.fr/blanch/software/osx-presentation/)
that displays speaker notes from `.pdfpc` files beside a PDF or embedded inside it.
The presenter UI comes from Présentation. This is not the GTK-based pdfpc app.

**Status:** installable Mac wrapper; GPL-3.0-or-later. Windows is not supported.
The independent cross-platform app is **research only**, described in
[CROSS_PLATFORM_PROPOSAL.md](docs/CROSS_PLATFORM_PROPOSAL.md).

## Give this to your coding agent

> Install https://github.com/pku-lemonade/presentation-pdfpc on this Mac.
> Read README.md and AGENTS.md, follow the installation runbook, and verify the
> result. Preserve my original apps, PDFs, notes, and default PDF application.

An agent with local shell access can perform the steps below. This is an agent
instruction, not a command recognized by a bare terminal. The agent may still
need you to complete an Apple Command Line Tools dialog or a macOS approval.
No paid developer account is required for this local installation.

## Installation runbook for agents

### 1. Check the host

```sh
uname -s
sw_vers -productVersion
xcode-select -p
/usr/bin/python3 --version
```

Requirements:

- macOS 12.5 or newer. Intel and Apple Silicon are upstream targets, but do not
  treat that as a claim that every OS/architecture combination was tested here.
- Apple's Command Line Tools and their `/usr/bin/python3`. Présentation 3.4.0
  bundles PyObjC for Python 3.8 and 3.9; the runtime check rejects other versions.
  A sufficiently new macOS version alone does not guarantee a compatible Python.
- Network access for cloning and, if upstream is missing, downloading its package.

If the Command Line Tools are missing, run `xcode-select --install`, tell the user
to complete Apple's dialog, then retry. Do not repeatedly trigger the dialog or
claim the installation finished while it is pending. If Apple's selected Python
does not match the bundled bindings, report that incompatibility; do not replace
system Python. This wrapper does not yet provide a portable Python runtime.

On Windows/Linux, stop before making changes and explain the platform limitation.

### 2. Clone and inspect

Choose an unused local directory, for example:

```sh
git clone https://github.com/pku-lemonade/presentation-pdfpc.git
cd presentation-pdfpc
```

Read this file, `AGENTS.md`, `install.sh`, `install.py`, and `build_wrapper.py`
before execution. For an existing checkout, inspect `git status` and preserve local
changes; never reset them to perform an update.

### 3. Install

```sh
./install.sh
```

This command:

1. Reuses an installed compatible Présentation in `/Applications` or
   `~/Applications`. Incompatible installed versions cause an explicit failure.
2. If absent, downloads **Présentation 3.4.0** from its author's HTTPS site,
   verifies a pinned SHA-256 and the package signature, extracts the app without
   running installer scripts, verifies its app signature and runtime, and places
   it in `~/Applications`. It does not invoke `sudo` or Apple's system installer.
3. Builds `~/Applications/Présentation PDFPC.app`, copies the runtime modules and
   notices into it, applies an ad-hoc signature, and verifies its integration.
   A previous wrapper is replaced only after the new build passes checks; a
   different app at that destination is never overwritten.

Pinned package:

```text
https://iihm.imag.fr/blanch/software/osx-presentation/releases/osx-presentation-3.4.0.pkg
SHA-256: 6fb258e6eec0407f1fb1d99064a53418da2a9865f74f2298c876694e76fe4209
```

If verification fails, stop and report it. Do not silently change the hash or
download a moving `latest` release. The maintainer must review a new upstream
version and update the compatibility tests and pin together.

You can run `./install.sh --check` for a read-only dependency/runtime preflight.
It does not verify that a wrapper has already been installed.

### 4. Verify and report

```sh
/usr/bin/python3 -m unittest discover -s tests -v
"$HOME/Applications/Présentation PDFPC.app/Contents/MacOS/presentation-pdfpc" --runtime-check
```

`--wrapper-check` checks source compatibility only. `--runtime-check` also imports
upstream's native bindings and required framework symbols. Neither opens a GUI.

With a user-selected PDF and matching notes, launch:

```sh
open -a "$HOME/Applications/Présentation PDFPC.app" "/absolute/path/to/talk.pdf"
```

Check that notes appear, navigation works, and **r** reloads the PDF and notes.
With two physical screens, check that only slides appear on the audience screen.
If no test PDF or second display is available, report those checks as untested.

Report the installed paths, upstream and Python versions, automated check
results, and any remaining GUI/OS steps. Do not imply Windows support.

### macOS prompts

Building from a Git checkout often avoids the downloaded-app workflow, but this
does not guarantee that macOS or university device policy will allow launching.
The wrapper is locally signed, not Developer ID signed or notarized. If macOS
blocks this trusted app as unidentified/unnotarized, the user may need to try
opening it, then use **System Settings → Privacy & Security → Open Anyway**.
Follow [Apple's instructions](https://support.apple.com/en-us/102445); do not
disable Gatekeeper or broadly remove quarantine attributes. Managed Macs may
require IT assistance. A damaged/signature-invalid app needs diagnosis, not an
automatic security bypass.

## Using notes

Keep matching exports together:

```text
talk.pdf
talk.pdfpc
```

- JSON format 2 is supported. `pages[].idx` is a zero-based **physical PDF page**;
  `pages[].note` is plain text. Unicode and per-overlay notes are supported.
- Existing PDF text annotations take precedence on their pages. Otherwise, a
  valid embedded `*.pdfpc` or `speaker-notes.json` takes precedence over a sidecar.
  A valid empty embedded notes file is authoritative. Invalid optional sources
  are skipped with a diagnostic.
- Markdown, pdfpc timer settings, hidden-slide flags, and navigation metadata are
  not imported. The original presenter's timer still works independently.
- **r** reopens the PDF and rereads notes. Re-export PDF and notes together after
  changing slide order; logical slide labels cannot repair mismatched page indices.
- Opening a `.pdfpc` file directly is not supported; open the PDF.

The wrapper copies its runtime into the app. Deleting the Git checkout does not
break normal launching. Keep the upstream app installed: it is loaded at launch.

## Updating and uninstalling

Quit the wrapper, preserve any local repository edits, pull a reviewed version,
and rerun `./install.sh`. Upstream is not automatically upgraded. After separately
updating upstream, run `--runtime-check` before relying on the wrapper for a talk.

To uninstall, move `~/Applications/Présentation PDFPC.app` to Trash. If the
installer added upstream to `~/Applications`, remove it separately only if you no
longer use it. The repository can be deleted independently. No shell profile,
default PDF association, slide source, or editor settings are changed.

## Development and provenance

```sh
/usr/bin/python3 build_wrapper.py --destination "/tmp/Présentation PDFPC Test.app"
```

Use a fresh temporary destination for development. See `tests/gui_smoke.py` for
the optional native presenter rendering check; it is not run by unit tests.

The starting implementation had local validation against Présentation 3.4.0:
parser/adapter tests and presenter rendering with Chinese, sidecar and embedded
notes. Camera behavior and multiple physical screens were not validated by that
check. The repository adds installation and runtime checks; consult commit history
for changes. No research-group slide decks, screenshots, or personal notes are
included.

License and attribution: [NOTICE.md](NOTICE.md), [GPL text](LICENSE).
