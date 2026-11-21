#!/bin/sh
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec uv run --locked python -B -X utf8 -m medplatform "$@"
