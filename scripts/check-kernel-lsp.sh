#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
project_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
kernel_build=${1:-/lib/modules/$(uname -r)/build}
python_bin=${PYTHON:-$project_root/.venv/bin/python}
[ -x "$python_bin" ] || { echo 'Create the project virtual environment first.' >&2; exit 1; }
make -C "$project_root/kernel" KDIR="$kernel_build"
"$python_bin" "$kernel_build/scripts/clang-tools/gen_compile_commands.py" \
    -d "$kernel_build" -o "$project_root/kernel/compile_commands.json" "$project_root/kernel"
clangd --check="$project_root/kernel/larkbox_fan.c" \
    --compile-commands-dir="$project_root/kernel"
