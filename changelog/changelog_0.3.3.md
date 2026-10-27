# VNMA `0.3.3`

**Release date:** 2026-10-26

> **Beta** — Safe entry-point bootstrap injection and AST import inspection

This patch release fixes syntax errors and false positive detections in `vnma insert-import`.

## Fixed

- **`from __future__` placement in `vnma insert-import`:** bootstrap import is now placed immediately after the last `from __future__ import ...` statement instead of the top of the file, preventing Python `SyntaxError: from __future__ imports must occur at the beginning of the file`.
- **AST-based import inspection:** replaced substring search for `__bootstrap__` with full AST analysis. Incidental mentions in comments or strings no longer block bootstrap insertion.
- **Header and docstring preservation:** shebang, PEP 263 encoding declarations, and module docstrings are strictly preserved before the bootstrap import.
- **Syntax validation and atomic writing:** target files are parsed and compiled before and after modification. Invalid source files are not modified, and writes are performed atomically.
- **BOM and line endings:** UTF-8 BOM and CRLF line endings are preserved.

## Verification

- Extended test suite with 9 dedicated regression tests for `vnma insert-import` covering empty files, annotations, multiline futures, BOM, CRLF, and syntax errors.
- 36/36 tests in `test_cli.py` passing.
