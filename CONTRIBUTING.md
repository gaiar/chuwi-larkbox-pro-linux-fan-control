# Contributing

Original project code defaults to MIT; kernel C/AML uses GPL-2.0-only OR MIT.
Read [LICENSING.md](LICENSING.md) and [DISCLAIMER.md](DISCLAIMER.md).

Use Python >=3.10 in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pre-commit install
.venv/bin/ruff format larkbox_fan.py tests
.venv/bin/ruff check larkbox_fan.py tests
.venv/bin/mypy
.venv/bin/pytest
shellcheck scripts/*.sh
```

Tests must keep >=90% statement and branch coverage. The C microphone meter is
checked against known signals and malformed input. For Linux kernel work:

```sh
sudo apt install clangd acpica-tools linux-headers-$(uname -r)
scripts/check-kernel-lsp.sh
clangd --check=tools/pcm_rms.c
(cd kernel && iasl -we -tc larkbox_control.asl)
```

The kernel build uses W=1 and -Werror. `.clangd` removes GCC-only flags from its
analysis view; the real compiler still receives the normal kernel build flags.
The generated ACPI header must correspond to the checked-in ASL. Different iasl
versions change the compiler header bytes and checksum.

Preserve a full-on recovery path before experimenting with fan-off. Mark findings
**seen**, **inferred** or **unknown**, cite firmware hashes/offsets and distinguish
static analysis from physical validation. Do not use an unsupported board just
because a GPIO address looks similar. Do not publish BIOS/Windows images, private
IP addresses, serials, credentials or microphone recordings in issues or commits.

Update status.md after significant work and run the complete checks before a
commit. CI compiles modules but never loads them on hosted runners. Reboot,
resume and physical fan operation need testing on the exact supported hardware.
