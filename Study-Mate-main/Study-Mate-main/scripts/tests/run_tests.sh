#!/usr/bin/env bash
# Compatibility entry point; npm scripts are the shared local/CI test commands.
set -u
cd "$(dirname "$0")/../.." || exit 1

case "${1:-}" in
  '') exec npm test ;;
  --static) exec npm run test:static ;;
  --browser)
    fail=0
    npm test || fail=1
    npm run test:browser || fail=1
    exit "$fail"
    ;;
  *)
    printf 'Usage: bash scripts/tests/run_tests.sh [--static|--browser]\n' >&2
    exit 2
    ;;
esac
