# VNMA 1.0.2

## Improvements

- **Smart `.gitignore` Visitor (`GitignoreVisitor`)**:
  - Normalizes existing `.gitignore` lines (handling leading/trailing slashes, wildcards like `./` or `**/`, inline comments `# ...`, and UTF-8 BOM) so existing rules are recognized and kept intact.
  - Appends strictly missing entries to the bottom without duplicating `# --- VNMA (Vendor Manager) ---` headers or accumulating blank lines across repeated `uninstall`/`install` cycles.
