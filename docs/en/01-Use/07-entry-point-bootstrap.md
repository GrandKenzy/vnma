# Entry Points Without `vnma run`

By default, a script only sees packages in `vendor/` when it is started with `vnma run`. For a CLI or application you run often, that is inconvenient. `vnma insert-import` removes the need.

---

## 1. The Command

```bash
# Use the project's entry point (main.py, src/main.py, source/main.py, app.py):
vnma insert-import

# Or name the script:
vnma insert-import cli/entry.py
```

The command inserts this line:

```python
import vendor.__bootstrap__  # From VNMA.
```

If the project uses another vendor directory (for example `vendor_vnma`), that name is used instead of `vendor`.

After that, run the script normally:

```bash
python main.py
```

---

## 2. Behavior

| Situation | Result |
| :--- | :--- |
| File has no bootstrap import | The line is inserted at the top. |
| File starts with a shebang (`#!`) and/or an encoding declaration | The line is inserted right after them. |
| File already references `__bootstrap__` | Nothing changes. |
| File does not exist | It is created with a minimal runnable template. |
| No `target` given and no entry point found | `main.py` is created in the project root. |

Example result for a script with a shebang:

```python
#!/usr/bin/env python3
import vendor.__bootstrap__  # From VNMA.

from my_package.cli import main

if __name__ == "__main__":
    main()
```

> [!IMPORTANT]
> The bootstrap import must run before any import of a vendored package. `vnma insert-import` places it at the top for that reason; keep it there.

---

## 3. Choosing How to Run

| Goal | Use |
| :--- | :--- |
| Run your own script during development | `python main.py` after `vnma insert-import`, or `vnma run main.py` |
| Run a CLI installed from a dependency | `vnma exec <tool>` (see [Runtime Execution](04-runtime-execution.md#5-cli-executables-vnma-exec)) |
| Check that linked directories exist before running | `vnma run` |

`vnma run` additionally sets `PYTHONPATH` and `PYTHONNOUSERSITE=1` for the child process and verifies linked directories before starting. The bootstrap import configures `sys.path` and Windows DLL directories from inside the process. See [Runtime Execution](04-runtime-execution.md) for the details of both.

---

## 4. Limits

* The command inspects the file only for the text `__bootstrap__`; any occurrence counts as an existing import.
* It does not create launcher scripts for your own project. To get a command on `PATH`, publish the project as a package or wrap it in a script of your own.
