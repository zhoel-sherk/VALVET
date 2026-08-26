#!/usr/bin/env bash
# Match GitHub Actions CI (see .github/workflows/ci.yml and doc/info/TESTING.md).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=src
export QT_QPA_PLATFORM=offscreen
python -m pytest tests -q --ignore=tests/test_pcb_preview_gerber.py "$@"
