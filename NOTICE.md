# Attribution and license

This repository's wrapper, installer, tests, and documentation are distributed
under GPL-3.0-or-later. See [LICENSE](LICENSE). This is an unofficial extension,
not a release of the GTK-based pdfpc project.

The presenter is **Présentation.app**, copyright IIHM/LIG — Renaud Blanch,
distributed by its author under GPL-3.0-or-later:

- Project and releases: https://iihm.imag.fr/blanch/software/osx-presentation/
- Upstream source: https://foss.heptapod.net/macos-apps/osx-presentation
- Source version used for the installer: 3.4.0

The installer downloads the original upstream package from the author's website.
It does not commit that package or a modified upstream script to this repository.
The wrapper adapts the installed script in memory. The app icon is copied from
the user's upstream installation; upstream credits David Lanham for the icon.
Its original attribution is retained. The icon is not a proposed asset for the
independent app described in the research document.

Upstream includes PyObjC and its own third-party notices. Those files remain in
the upstream app. When redistributing binaries, provide the applicable license
notices and corresponding source as required, including for components you bundle.

The independent rewrite in `docs/CROSS_PLATFORM_PROPOSAL.md` is a proposal only.
It does not change this repository's GPL license or authorize relicensing copied
code. Any future independent app should use a separate repository and an explicit
license chosen by its maintainers.
