#!/bin/sh
set -e
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
[ $# -eq 0 ] && set -- serve
if [ "$1" = serve ]; then
  pnpm install --frozen-lockfile
  pnpm build
fi
cd backend
exec uv run --locked python -B -X utf8 -m medplatform "$@"
