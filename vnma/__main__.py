"""Direct execution entry point for python -m vnma."""

import sys
from vnma.cli import main

if __name__ == "__main__":
    sys.exit(main())
