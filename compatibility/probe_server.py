#!/usr/bin/env python3
"""Backward-compatible entry point; the application now serves /compatibility."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.app import main

if __name__ == "__main__":
    raise SystemExit(main())
