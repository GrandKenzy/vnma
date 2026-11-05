# VNMA `1.1.0`

## Fixed

- Prevented command injection in generated console-script launchers by validating entry-point metadata, shell-escaping executable paths, and dispatching targets without embedding wheel data in shell code.
- Prevented path traversal when storing downloaded wheels by sanitizing cache filenames before every write.
- Added finite timeouts to PyPI requests and Git, pip, test, and runtime subprocesses so network or child processes cannot hang indefinitely.
- Corrected transaction recovery process detection on Windows.
- Prevented corrupted manifests from being treated as empty metadata or silently overwriting `vnma.lock`.
- Corrected TOML serialization so project names, paths, and dependency values are escaped safely.
- Replaced silent broad exception handling in configuration, manifest, IDE, and dependency inspection paths with typed user-facing errors.
- Corrected version consistency checks, CI release validation, documentation status, and repository configuration metadata.
