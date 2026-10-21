# Changelog

## Unreleased

- Require explicit CPU sensor and fan-driver preparation before daemon startup.
- Report module-load failures instead of silently skipping the service.
- Build support for installed fallback kernels when their headers are present.
- Validate systemd dependencies in the installer and hosted CI.
- Document startup after BIOS Smart Fan resets and the remaining cold-boot test.

## 0.1.0

- LarkBox Pro BIOS 1.07 control through its native ACPI Smart Fan routine.
- Binary fan policy with configurable temperatures, hysteresis and minimum on time.
- Three-second off lease, kernel temperature guard and full-on fault recovery.
- All-core/package CPU monitoring and atomic runtime status.
- DKMS installation, persistent systemd service and safe removal instructions.
- Streaming microphone level tool; no audio recordings retained.
- Python policy tests, C meter tests, compiler/clangd checks and hosted DKMS CI.
- MIT default license, with dual MIT/GPL-2.0-only kernel code.
