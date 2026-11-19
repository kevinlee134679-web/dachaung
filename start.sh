#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -B run.py "$@"
fi
exec "${DACHAUNG_PYTHON:-python3.14}" -B run.py "$@"
