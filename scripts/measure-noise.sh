#!/bin/bash
# SPDX-License-Identifier: MIT
set -euo pipefail
seconds=${1:-15}
if ! [[ "$seconds" =~ ^[0-9]+$ ]] || (( seconds < 1 || seconds > 60 )); then
    echo 'Duration must be 1–60 seconds.' >&2; exit 2
fi
project_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
task_build=$(mktemp -d)
trap 'rm -rf "$task_build"' EXIT
cc -std=c11 -O2 -Wall -Wextra -Werror "$project_root/tools/pcm_rms.c" -lm -o "$task_build/pcm-rms"
echo "Measuring $seconds seconds from hw:C200,0; keep placement and gain fixed…" >&2
cat /sys/kernel/larkbox_fan/status >&2
arecord -q -D hw:C200,0 -t raw -f S16_LE -r 48000 -c 2 -d "$seconds" | "$task_build/pcm-rms"
echo 'Complete: relative unweighted dBFS, not calibrated dBA. No audio saved.' >&2
