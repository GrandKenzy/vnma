# IDE Integration

`vnma` automatically configures Visual Studio Code and JetBrains PyCharm so that auto-completion, linting, type inference, and symbol navigation work out of the box with vendored libraries.

---

## 1. Visual Studio Code

### Configuration: `.vscode/settings.json`

During `vnma init`, `vnma install`, or `vnma sync-ide`, `vnma` updates `.vscode/settings.json`:

```json
{
    "python.analysis.extraPaths": [
        "./vendor"
    ],
    "python.autoComplete.extraPaths": [
        "./vendor"
    ]
}
```

### JSONC Compatibility

VS Code configuration files often contain inline comments (`//`, `/* ... */`) and trailing commas. `vnma` uses a lexical pre-filter to safely parse JSON with comments (JSONC), ensuring existing user customizations are not overwritten or corrupted.

---

## 2. JetBrains PyCharm

### A. Environment File: `.env`

`vnma` creates or updates a root `.env` file containing:

```env
PYTHONPATH=./vendor
```

PyCharm reads `.env` files automatically in run configurations and Python console sessions.

### B. Project Module: `.idea/*.iml`

If the project directory contains a `.idea` folder, `vnma` patches the module file (`.iml`) to register `vendor/` as a recognized source folder:

```xml
<content url="file://$MODULE_DIR$">
  <sourceFolder url="file://$MODULE_DIR$/vendor" isTestSource="false" />
</content>
```

---

## 3. Manual Resynchronization

If IDE configuration files are deleted or modified externally, run:

```bash
vnma sync-ide
```

This reapplies IDE path registrations without touching the packages inside `vendor/`.
