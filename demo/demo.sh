#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${1:-results}"

if command -v judgeprobe >/dev/null 2>&1; then
  JP=(judgeprobe)
elif command -v python3 >/dev/null 2>&1; then
  JP=(python3 -m judgeprobe)
else
  JP=(python -m judgeprobe)
fi

"${JP[@]}" validate probes/
run_output="$("${JP[@]}" run --model mock --arm both --runs 3 --out "$OUT" --seed 0)"
printf '%s\n' "$run_output"
csv_path="$(printf '%s\n' "$run_output" | awk '/^CSV: / { print $2 }')"
"${JP[@]}" report "$csv_path"
