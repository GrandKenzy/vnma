"""Automated runner for the isolated nested Gram dependency test."""

import subprocess
import sys
from pathlib import Path


def run() -> None:
    example_root = Path(__file__).parent.resolve()
    main_project = example_root / "main_project"

    print("Running isolated nested Gram test in:", main_project)

    # 1. Run main.py using python directly (uses vendor.__bootstrap__)
    res_direct = subprocess.run(
        [sys.executable, str(main_project / "main.py")],
        cwd=str(main_project),
        capture_output=True,
        text=True,
    )
    print("Direct run output:\n", res_direct.stdout)
    if res_direct.returncode != 0:
        print("Error:\n", res_direct.stderr)
        sys.exit(res_direct.returncode)

    # 2. Run using vnma run
    res_vnma = subprocess.run(
        [sys.executable, "-m", "vnma", "run", "main.py"],
        cwd=str(main_project),
        capture_output=True,
        text=True,
    )
    print("VNMA run output:\n", res_vnma.stdout)
    if res_vnma.returncode != 0:
        print("Error:\n", res_vnma.stderr)
        sys.exit(res_vnma.returncode)

    # 3. Test CLI executable wrapper
    res_exec = subprocess.run(
        [sys.executable, "-m", "vnma", "exec", "gram"],
        cwd=str(main_project),
        capture_output=True,
        text=True,
    )
    print("Gram exec output:\n", res_exec.stdout)
    if res_exec.returncode != 0:
        print("Error:\n", res_exec.stderr)
        sys.exit(res_exec.returncode)

    print("\n[ALL CHECKS PASSED] Nested Gram test verified successfully!")


if __name__ == "__main__":
    run()
