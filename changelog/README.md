# VNMA · Changelog

<p align="center">
  <strong>Versioned release notes for VNMA</strong><br>
  Vendoring, dependency resolution, transactions, and runtime tooling.
</p>

---

## Current release

### [`1.1.0`](changelog_1.1.0.md) · Production

Security, reliability, cross-platform compatibility, and release metadata fixes.

### [`0.3.3`](changelog_0.3.3.md) · Historical

Safe entry-point bootstrap injection and AST import inspection.

### [`0.3.2`](changelog_0.3.2.md) · Beta

Transitive dependencies across Git, local, and PyPI sources, and the
`vnma insert-import` command.

VNMA 1.1.0 is the current production release.

## Release timeline

| Version | Date | Main focus | Notes |
| --- | --- | --- | --- |
| [`1.1.0`](changelog_1.1.0.md) | 2026-11-04 | Security, reliability, and Linux compatibility fixes | Current |
| [`1.0.2`](changelog_1.0.2.md) | — | Previous production release | Superseded |
| [`1.0.1`](changelog_1.0.1.md) | — | Previous production release | Superseded |
| [`1.0.0`](changelog_1.0.0.md) | — | First production release | Superseded |
| [`0.3.3`](changelog_0.3.3.md) | 2026-10-26 | Safe bootstrap injection and AST import inspection | Historical |
| [`0.3.2`](changelog_0.3.2.md) | 2026-10-26 | Nested dependencies and entry-point bootstrap | Beta |
| [`0.3.1`](changelog_0.3.1.md) | 2026-10-24 | Test runner and configuration safety | Beta |
| [`0.3.0`](changelog_0.3.0.md) | 2026-10-24 | Resolver backtracking and transactions | Beta |
| `0.2.9` | — | — | Previous release, not reconstructed |

## How to read these notes

Each release has its own `changelog_*.md` file. Entries are grouped by impact:

- **Breaking changes:** behavior or API changes that may require migration.
- **Added:** new public capabilities and configuration.
- **Changed:** modifications to existing behavior.
- **Fixed:** corrected bugs and regressions.
- **Documentation:** synchronized guides, examples, and release references.
- **Verification:** what was actually run, and its result.
- **Known issues:** limitations that are not resolved in the release.

## Repository conventions

Release notes live in files matching `changelog_*.md` inside this folder. When
preparing a release, keep the version synchronized in the filename, the heading, `pyproject.toml`,
`vnma.toml`, and `vnma.__version__`.
