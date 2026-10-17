#!/usr/bin/env python3
"""Run self.os from a clone without installing: python tools/selfos.py <command>."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from selfos.cli import entry  # noqa: E402

entry()
