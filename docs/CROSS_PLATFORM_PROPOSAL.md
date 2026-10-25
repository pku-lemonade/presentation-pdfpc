# Independent Windows/macOS PDF presenter: research and agent handoff

Research updated: 2026-10-24. **Proposal only; no cross-platform implementation or
framework benchmark has been built.** The existing GPL Mac wrapper is unchanged.

## 1. Decision and constraints

**Recommend PySide6 + Qt Widgets with custom painting, Qt PDF for rendering, and
pypdf for PDF attachment/annotation metadata that Qt PDF does not expose.**
The same GUI architecture could be written with C++ Qt if avoiding the Python
runtime becomes a hard requirement. Language preference is currently neutral.

The user likes Présentation's simple interface: slides, a timer, notes and a compact
thumbnail strip. Preserve that visual restraint with an original implementation.
Do not interpret “Qt Widgets” as a request for toolbars, ribbons, menus everywhere,
or a generic document viewer. Two custom-painted views can provide the desired UI.

**Tauri and Electron are ruled out.** Earlier browser-stack recommendations have
been removed from this handoff. Rust is a candidate, not a user preference.

Current ranking:

| Rank | Candidate | Assessment for this application |
|---|---|---|
| 1 | PySide6 / Qt Widgets | Closest overall match to the existing drawing, text, input, windows and optional multimedia workload; smallest integration risk in my judgment. |
| 2 | Rust / egui + eframe / pdfium-render | Credible fit for the custom-painted core UI; active project with actual adopters. More PDF library, fonts, window behavior and optional multimedia integration to own. |
| 3 | Rust / Iced / pdfium-render | Active and viable; supports interactive canvas drawing. Its declarative structure is not a decisive advantage for this particular two-canvas application. |

This ranks engineering fit, not measured speed, memory, package size, or aesthetic
quality. Qt can reproduce the minimalist appearance. egui may be attractive for a
restricted slide/notes/timer tool, but neither toolkit choice gives complete PDF
multimedia compatibility automatically. All three need a prototype on both OSes.

**PageCue** is a name suggestion only; availability and trademark were not checked.
The future application should be independently authored in a separate repository
under a license chosen by its maintainer. MIT is proposed, subject to dependency
obligations; this repository remains GPL-3.0-or-later.

## 2. What the Présentation code actually does

Inspected installed upstream **Présentation 3.4.0**, `Contents/MacOS/presentation.py`,
2,592 lines. SHA-256:
`9924ca533b96cdc21e56dbb7e3e6d8e87f5687b95d7d4f92133da32e75e63e5c`.
The following are observations from that version, not inferred from screenshots.
Line references are to that upstream script, which is not copied into this repo.

| Upstream location | Observed behavior | Implication for framework choice |
|---|---|---|
| `PresenterView`, lines 1427–2249 | One custom NSView handles most layout, drawing and interaction. | This is chiefly a canvas UI, not a form-heavy application. egui is more plausible than a generic widget comparison suggests. Qt custom painting is equally applicable. |
| `PresenterView.drawRect_`, around 1490–1725 | Manually positions current/next slides, timer, page number, notes and help. | An original `QWidget.paintEvent` + QPainter design can retain the restrained layout; no QML or web UI is required. |
| Notes drawing, around 1657–1673 | Concatenates note strings and draws them in a rectangle with font sizing. | Notes are displayed text, not a rich-text editor. Complex editing features are not a core requirement; CJK font layout still matters. |
| `draw_miniatures`, around 1443; thumbnail generation around 1019 | Prepares thumbnails, scrolls a strip and previews a hovered page. | All candidates can do this. Cache/lazy generation policy matters more than language. |
| `SlideView.drawRect_`, lines 1116–1165 | Fits the PDF page, applies transforms, draws ink and a laser/spotlight overlay. | QPainter/QTransform/QPainterPath offer a close conceptual match; egui/Iced can compose textures and geometry. |
| Input methods, roughly 1755–2249 | Keyboard commands, clickers, zoom, hit testing, scroll, drawing, selection and dragging. | A visually sparse UI still has substantial interaction state and coordinate handling. Rewrite this state machine explicitly. |
| Window creation/fullscreen, lines 2405–2557 | Two windows, keyboard routing, screen choice/swap and fullscreen changes. | Native window behavior is a release gate, not something to infer from successful single-window rendering. |
| `MovieView`, lines 1212–1290; `VideoView`, 1294–1413 | Movie playback/seek and a camera overlay backed by AVFoundation layers. | Qt Multimedia provides relevant cross-platform primitives. egui/Iced do not themselves replace AVFoundation. Full feature scope strengthens the Qt recommendation. |
| Animation handling, around 664–963 | Interprets specific embedded PDF animation/media structures using Apple PDF/JS helpers. | A PDF bitmap renderer does not automatically reproduce these semantics. Separate milestone for every candidate. |
| `Refresher`, lines 2570–2590 | A one-second timer invalidates presenter views; input triggers other redraws. | The app is not inherently a continuous high-frame-rate scene. Cache PDF images and repaint only when needed. |

The direct API mapping favoring Qt is **NSView custom drawing → QWidget/QPainter,
NSAffineTransform → QTransform, NSBezierPath → QPainterPath**, with Qt's screen,
event and multimedia facilities supporting the surrounding application.
QPainter supports text, images, paths and transforms; Qt PDF provides queued
page-rendering requests; Qt Multimedia supports camera capture sessions.
These are capability matches, not tested parity. [S29–S31]

Iced has an interactive 2D canvas API, so it is not disqualified for custom drawing.
I rank it below egui here because the declarative widget architecture adds no clear
project-specific benefit over a compact canvas-oriented implementation; this is an
engineering judgment, not evidence that Iced is slower or incapable. [S32]

The existing wrapper's parser, hooks and installer are a different codebase. It
passed 51 local tests and a temporary signed-app/runtime check during packaging.
Those results do not establish that any proposed replacement works on Windows.

## 3. Maintenance, adoption and growth evidence

Checked official release pages, GitHub repository metadata and default-branch
commits on 2026-10-24. **All three are actively maintained.**

| Project | Release evidence | Development/adoption evidence | Interpretation |
|---|---|---|---|
| Qt / PySide6 | Qt for Python 6.12 announcement dated Oct 9, 2026 | PySide mirror contains fixes dated Oct 23, 2026; official Qt release/development infrastructure | Active, established option; its GitHub mirror's star count is not comparable to GitHub-native projects. |
| egui | 0.37.0 released Oct 15, 2026; 0.36.2 Sept 8; 0.36.1 Aug 7; 0.36.0 Aug 5 | Default-branch fixes Oct 21; 31,733 GitHub stars at query time; project documents Rerun sponsorship and use | Frequent releases, live maintenance and an actual adopter. APIs remain in flux. |
| Iced | Latest GitHub release observed: 0.14.0, Dec 7, 2025 | Default-branch text/font fixes Oct 20–21, 2026; 31,828 stars; COSMIC's libcosmic is based on Iced | Active despite slower tagged releases. An older release date alone does not imply abandonment. |

Sources: [Qt release announcement](https://www.qt.io/blog/qt-for-python-release-6.12-is-here),
[PySide commits](https://github.com/pyside/pyside-setup/commits/dev/),
[egui releases](https://github.com/emilk/egui/releases),
[egui commits](https://github.com/emilk/egui/commits/main/),
[Iced releases](https://github.com/iced-rs/iced/releases),
[Iced commits](https://github.com/iced-rs/iced/commits/master/),
[egui's project statement](https://github.com/emilk/egui), and
[libcosmic](https://github.com/pop-os/libcosmic).

The query used the GitHub `/repos/{owner}/{repo}`, `/releases?per_page=8` and
`/commits?per_page=4` endpoints for `emilk/egui`, `iced-rs/iced`, and
`pyside/pyside-setup`. Recent commit subjects included real fixes, not only release
markers: egui's stale debug-ID entries, Iced's font preservation/text selection,
and PySide converter lookup handling.

**Popularity growth was not measured.** These are point-in-time counts, not active
user counts or a growth curve. No historical star/download series was collected.
Do not claim that egui or Iced is growing faster than Qt from these numbers. Rerun
and COSMIC establish adoption, not proof of our exact Windows/macOS requirements.

Activity also has costs: egui explicitly says interfaces are still changing, and
0.37 lists breaking changes involving fonts, screenshot callbacks and ID APIs.
Pin versions and use matching documentation. For Iced, verify that needed fixes
are in a released version instead of silently building the application against
an unpinned development branch. [S33]

The maintainer is comfortable with some immaturity for a small application. Thus
maturity is not a veto against egui/Iced. The remaining deciding work is concrete:
PDF rendering, readable Chinese notes, dual-display behavior and packaged launch.

## 4. Independent implementation and licensing boundaries

Présentation is GPL-3.0-or-later. Keeping and distributing the existing wrapper
under GPL is compatible with research-group sharing; GPL is not a license fee.
The desire for a different license is a reason to author a separate app, not to
rename or mechanically translate the old source. See the upstream statement and
the GPL text shipped with this repository. [S1]

For the new project:

1. Start a new repository and choose its license explicitly; MIT is recommended.
2. Implement functional requirements from this proposal and public library APIs.
   Do not copy/translate upstream or wrapper source, tests, distinctive UI artwork,
   icons, or documentation into the new app. This includes the existing notes parser
   and fixtures unless their rights holders separately authorize relicensing.
3. Use fresh application structure, original visual design, and newly authored
   synthetic test documents. Record dependency and asset provenance.
4. Give the implementing agent a fresh context with this functional proposal,
   rather than asking it to port the GPL Python files line by line.
5. Do not label the result “clean-room certified.” This research session did inspect
   GPL code. A new agent/context is a practical separation measure, not a legal
   determination of independence.

The US Copyright Office distinguishes protected program expression from functional
ideas; this supports writing to requirements rather than copying expression, but
does not settle every question about a particular derivative work or another
jurisdiction. [S2] Rewriting in another language by itself changes nothing about
whether source expression was copied.

LGPL and GPL are different choices. An MIT application can use eligible LGPL
libraries while fulfilling their conditions. Qt specifically documents notices,
corresponding library source, and replacement/relinking requirements; check every
selected module and packaged build. [S12–S13] Qt is recommended here on technical grounds; fulfill its applicable LGPL obligations
if that route is selected. Choosing a permissive GUI library instead does not remove
its dependency and asset obligations.

## 5. Recommended minimal Qt architecture

Use **two custom QWidget views**, one shared session/controller, and a small
PDF-service boundary. Avoid a browser engine, QML, a plugin architecture and a
large application framework for the first version.

- **Session/controller:** physical page index, notes source, timer, blanking,
  display selection, document generation and navigation commands.
- **PresenterView:** paint the current/next images, timer and thumbnail selection;
  compose a text area for notes and limited controls when useful. Do not add chrome
  just because standard widgets are available.
- **AudienceView:** paint only the slide and explicitly enabled overlays. Never
  reuse a presenter component that can expose notes or dialogs to the audience.
- **PDF service:** Qt PDF's document/page renderer produces QImages. Use pypdf for
  attachments and note annotations where the selected Qt API lacks access. Avoid
  parsing PDF bytes independently throughout the UI. Treat differences between the
  two libraries' page/rotation/crop interpretations as an integration test concern.
- **Domain logic:** independently authored notes validation, source selection,
  navigation and timer rules, testable without opening a window.

Keep PDF rasterization outside paintEvent. Request images through the supported
queued renderer, then update the relevant widget. Tag requests/results with
(document generation, physical page, size) so old results cannot overwrite a new
page. A page turn during rendering must not freeze input. Use bounded nearby-page
and thumbnail caches; a 3840×2160 RGBA image alone is about 31.6 MiB.

Model pointer, ink and crop transforms explicitly in PDF/page coordinates and
convert to widget coordinates at drawing/hit-test boundaries. Make one-screen
rehearsal useful. Handle unplugging a display and negative/mixed-DPI screen geometry.
Do not equate support for two windows with reliable projector behavior.

Use a monotonic timer. On reload, validate the new document before replacing the
old session; preserve the current presentation on failure. Define whether elapsed
time and ink survive reload, then test that contract.

For packaging, evaluate `pyside6-deploy` and PyInstaller with the actual selected
modules. Package a private interpreter and native libraries; do not reproduce the
old wrapper's reliance on `/usr/bin/python3`. The latest PySide wheel observed
(6.12.0) targets macOS 14+ and Python >=3.10,<3.16. Select the supported OS baseline
before pinning a version. That metadata observation is not a validated lockfile.
[S21–S23, S28]

### Native Rust alternative

Use egui/eframe for the two native viewports, pdfium-render for rendering and
attachment/annotation inspection, serde_json for new notes parsing, and Instant
for timing. One worker should own PDFium operations initially; review its actual
thread-safety contract rather than assuming separate documents allow parallel calls.

Use deferred viewports where appropriate, reuse rendered textures, and repaint
only for input, completed rendering and timer ticks. Bundle/test fonts for Chinese
notes separately from embedded fonts in the PDF. Ship a pinned PDFium DLL/dylib
and load it from application resources. The bindings do not include PDFium, and
PDFium is a C++ dependency, so this would not be an entirely pure-Rust program.
[S34–S35]

Iced can use an equivalent renderer/service and state-update model with its canvas
and multiple-window facilities. Do not assume a third-party camera/video widget
has the same coverage as Qt Multimedia; prototype any required media functionality.

All implementations must retain original PDF/notes files, avoid executing embedded
PDF scripts or files automatically, keep notes plain text initially, and treat
parser byte/time limits as controls rather than guarantees about native allocations.

## 6. Product scope and notes compatibility

### First usable release

1. Open a PDF through a file picker, drag/drop, or a path argument. Retain offline
   functionality after installation and restart.
2. Show current/next page and notes to the presenter; show the current page alone
   in the audience window, with fit-to-screen letterboxing.
3. Provide previous/next, first/last, go-to-page, blackout, timer pause/reset,
   display selection/swap, fullscreen and explicit reload.
4. Read sidecar and embedded format-2 `.pdfpc` notes, including Unicode and multiple
   physical overlay pages with the same logical slide label.
5. Package and smoke-test on Windows x64 and macOS arm64; add macOS x64 only when
   the lab needs it and the chosen runtime supports the declared minimum OS.
6. Provide a truthful agent installation runbook and diagnosis command.

Use normal keyboard events while either app window is active; global hotkeys are
not required. Choose original, discoverable shortcuts and test them with common
presentation clickers. The initial release does not need to mimic every upstream
binding or screen arrangement.

### Notes behavior to specify and test independently

The desired interchange data is an object with integer `pdfpcFormat: 2` and a
`pages` array. Each relevant entry has integer `idx` and string `note`. Indices refer
to physical pages, not displayed labels. Create new examples/fixtures for the new
implementation; do not copy existing test code.

Recommended compatibility policy:

- Missing notes are ordinary. Invalid optional notes should not prevent PDF viewing.
- Keep notes plain text in version one; preserve Unicode and line breaks.
- Reject invalid top-level format/version; skip malformed entries with a diagnostic
  that does not log note contents. Define the treatment of duplicates explicitly.
- Use the adjacent file obtained by replacing the final PDF extension with `.pdfpc`.
  Do not search unrelated directories or guess by modification timestamps.
- Give valid embedded notes priority over the sidecar. An intentionally empty valid
  embedded notes document should not revive stale sidecar notes.
- Existing PDF text annotations can take precedence on their pages. Extract note
  text without showing annotation popups or comment icons on the audience view.
- When several embedded candidates exist, use a deterministic documented order and
  expose the chosen source in presenter diagnostics. A different PDF library may not preserve the
  same ordering as Apple's extraction; exact source-selection parity needs fixtures.
- Out-of-range indices cannot repair a stale PDF/notes pairing. Show a useful
  presenter diagnostic and recommend exporting both together.
- Put limits on note bytes, entries and attachment candidates. Check both declared
  and actual sizes where available. Attachment filenames are metadata, not paths to
  extract blindly. Avoid automatically materializing unrelated embedded media.

Do not import pdfpc timer/navigation/hidden-slide metadata until its semantics have
been separately specified. Basic timer support is application state, not a claim
of complete `.pdfpc` compatibility.

### Deferred features and why

| Feature | Why it is a separate milestone |
|---|---|
| Beamer slides with notes in a second page region | Requires explicit crop/layout rules; the first release should report unsupported layouts rather than silently guessing |
| Markdown notes | Requires an agreed rendering dialect and handling of links/images; plain text already meets the core need |
| Ink, whiteboard, spotlight | Requires input coordinates stable across DPI, resizing, and rotation; start with a simple pointer later |
| Camera overlay and recording | Permissions, device lifecycle and media testing on both platforms |
| Embedded movies and legacy PDF multimedia annotations | Extracting attachment bytes does not provide codec support, synchronization or PDF multimedia semantics |
| LaTeX `animate`, PDF JavaScript and page transitions | Not delivered automatically by a PDF raster renderer; arbitrary PDF script execution is excluded |
| Automatic file watching | Must survive atomic replacement, partial writes and bursts; explicit reload should be reliable first |
| Linux, Windows ARM, remote control, cloud sync | Outside the currently requested platform and sharing scope |

## 7. Prototype and implementation gates

**Start with Qt, given the neutral language preference.** Build a small disposable
spike proving two windows, PDF rendering, Chinese notes, display placement,
fullscreen, reload and a packaged offline launch on Windows and macOS. Use new
synthetic fixtures and user-approved real PDFs. Record actual versions, hardware,
rendering behavior, startup, package size and memory before proposing performance
budgets. No toolkit has been benchmarked in this survey.

If Qt has a concrete blocker or unacceptable measured cost, run the same small
spike with egui. Do not build three full apps merely to select a toolkit. Iced is a
credible reserve option, not a necessary third prototype without a reason.

After the gate:

1. Implement the core domain behavior, presenter/audience views, timer, notes and
   safe reload; add behavioral tests as each feature is implemented.
2. Produce locked, reproducible native builds, a diagnosis command and a per-user
   installer; validate updates/uninstall without changing unrelated files/settings.
3. Add ink, camera, embedded media or animation only when requested, each with its
   own feature/license review and two-platform tests. None is automatically provided
   by changing the PDF renderer.

Agents can implement and automate this, but physical display validation requires
appropriate hardware. Do not attach a calendar estimate until the spike resolves
platform, PDF and packaging risks.

## 8. Validation matrix and release criteria

| Area | Required evidence |
|---|---|
| Notes | New tests for Unicode, empty sources, invalid JSON, duplicate entries, out-of-range pages, embedded/sidecar precedence, annotation priority and overlay labels |
| Rendering | Visually inspect math, CJK, embedded fonts, vectors, raster images, transparency, rotated pages and varied page sizes on both target OSes |
| Reload | Atomic file replacement, temporary invalid file, shorter PDF, changed notes, rapid navigation during reload; original files remain unchanged |
| Displays | One screen; extended two screens; projector on either side/negative coordinates; mixed DPI; connect/disconnect; sleep/wake; macOS Spaces/fullscreen; Windows scaling |
| Audience separation | Screenshots and IPC/component assertions show no presenter notes, thumbnails, dialogs or developer errors on the audience window |
| Input | Keyboard and common clicker events, focus in notes, external links, window activation and exiting fullscreen |
| Packaging | Launch packaged build offline on a clean machine, including workers/fonts; no developer Python/Node required; paths with spaces and Unicode |
| Installation | Repeat install, update, uninstall, failure rollback, unsupported OS, missing runtime, blocked security approval and managed-device limitations |
| Resources | Measure RSS and bitmap cache after repeated navigation/reload; no monotonic growth caused by unreleased documents/canvases |

Provisional usability targets, **not measured claims**: cached next-page display
within 100 ms at the 95th percentile, responsive controls during uncached rendering,
and no visible blank-frame flash on a cached page turn. Record hardware, resolution,
PDF corpus and measurement method. Establish practical startup/memory/package-size
budgets after the spike instead of selecting attractive but unsupported numbers.

Use unit tests for pure state/data behavior, native GUI integration checks for real
windows/screenshots, and packaged-app smoke tests. For Qt, use Qt Test or pytest-qt
with a pinned version; do not substitute a widget import test for real launch tests.
Virtual displays and CI screenshots do not replace physical-monitor testing.

## 9. Agent installation and handoff

The desired future user prompt is “Install https://github.com/OWNER/NEW-APP,
following its README and AGENTS.md, and verify it.” That future app is not present
in this repository. This repository's installer installs the existing GPL Mac
wrapper only.

The new app's agent runbook should detect supported OS/architecture, prefer a
versioned release artifact with a checksum, and otherwise build with pinned tools
and a lockfile in an unused checkout. Preserve local changes, install per-user,
report actual paths/versions and distinguish automated checks from physical-screen
checks. Students using prebuilt releases need neither Python nor Rust installed.
Build and test on each target OS; do not claim cross-platform success from one host.

No framework removes OS approval requirements. Local builds do not guarantee a
Gatekeeper exemption; unsigned downloads and managed computers can require user
or IT action. Never disable protections to satisfy a one-command-install promise.
[Apple's guidance](https://support.apple.com/en-us/102445).

Suggested prompt for the implementing agent:

> Implement an independent Windows/macOS PDF presenter in a new repository, using
> this proposal as functional requirements. Do not copy or translate the existing
> GPL application, wrapper, tests or artwork. There is no Rust preference; start
> with PySide6/Qt Widgets custom painting and the prototype gate. Keep the UI as
> restrained as Présentation: current/next slides, notes, timer, thumbnails and a
> separate audience screen. Tauri and Electron are excluded. Use original fixtures
> and visual design. Confirm the new app name/license, record real prototype
> results, and reconsider egui only for a concrete advantage or Qt blocker.
> Preserve the existing working Mac app. Deliver native packages, tests and an
> honest agent installation runbook. Identify untested platforms and hardware.

## 10. Sources and evidence limits

This is source inspection plus documentation/repository research, not a working
prototype, formal clean-room process, measured popularity trend or complete
third-party license audit. Unversioned docs can move ahead of installed libraries:
the unversioned Qt PDF URLs redirected to development snapshots during research.
Use exact-version docs and package contents for implementation decisions.

- **S1:** [Présentation project/license/features](https://iihm.imag.fr/blanch/software/osx-presentation/).
- **S2:** [US Copyright Office Circular 61](https://www.copyright.gov/circs/circ61.pdf).
- **S11:** [Qt PDF 6.8 licensing](https://doc.qt.io/qt-6.8/qtpdf-licensing.html).
- **S12:** [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).
- **S13:** [Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations).
- **S14:** [pypdf attachments](https://pypdf.readthedocs.io/en/stable/user/handle-attachments.html).
- **S21:** [Qt for Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html).
- **S22:** [pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html).
- **S23:** [PyInstaller operation](https://pyinstaller.org/en/stable/operating-mode.html). Qt's separate PyInstaller page contains a warning dated March 2021; do not assume it describes current support.
- **S28:** [PySide6 registry metadata](https://pypi.org/pypi/PySide6/json), queried during research; resolve and test a release-specific dependency set.
- **S29:** [QPainter](https://doc.qt.io/qt-6/qpainter.html).
- **S30:** [QPdfPageRenderer, versioned documentation](https://doc.qt.io/qt-6.8/qpdfpagerenderer.html).
- **S31:** [QMediaCaptureSession](https://doc.qt.io/qt-6/qmediacapturesession.html).
- **S32:** [Iced interactive canvas](https://docs.rs/iced/latest/iced/widget/canvas/index.html).
- **S33:** [egui 0.37 release/breaking changes](https://github.com/emilk/egui/releases/tag/0.37.0).
- **S34:** [egui native viewports](https://docs.rs/egui/latest/egui/viewport/index.html); match documentation to the chosen version.
- **S35:** [pdfium-render](https://github.com/ajrcarey/pdfium-render) and [license](https://github.com/ajrcarey/pdfium-render/blob/master/LICENSE.md).

Maintenance/adoption evidence and its retrieval method are recorded in section 3.
Original app source was inspected locally at the hash recorded in section 2; no
upstream source or private presentation artifacts are added to this repository.
