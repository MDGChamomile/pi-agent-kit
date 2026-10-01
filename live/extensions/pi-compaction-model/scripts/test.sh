#!/bin/sh
set -eu

# Keep discovery deterministic and module mocks isolated per test file.
export LC_ALL=C
set -- ./test/*.test.ts
if [ ! -f "$1" ]; then
  printf '%s\n' 'No test/*.test.ts files found.' >&2
  exit 1
fi

for file in "$@"; do
  bun test "$file"
done
