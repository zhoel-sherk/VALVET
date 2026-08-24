#!/usr/bin/env python3
"""Print QSS fragment from ``src/themes/design_tokens.json`` (Figma token bridge helper)."""

from __future__ import annotations

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_root, "src"))

from themes import extra_application_stylesheet  # noqa: E402


def main() -> None:
    print(extra_application_stylesheet().strip())


if __name__ == "__main__":
    main()
