# Project status — 2026-10-21

- Published with MIT default licensing, dual-licensed kernel code, installation
  and tuning guides, a risk disclaimer and GitHub Actions.
- Fan control demonstrated on CHUWI LarkBox Pro J4125, BIOS GB01_ZW_1_07,
  Ubuntu 24.04, kernel 6.8.0-147-generic.
- DKMS module and systemd service installed, enabled and running on the test unit.
- Measured default: 58°C on, 50°C off, 10-second cooling delay, 30-second minimum
  run. Matched workload retained 99.49% of full-on throughput with a 64°C peak.
- Three-second off-lease recovery demonstrated, including daemon SIGKILL.
- Windows factory image inspected: Intel DPTF 8.4.11000.6436 corroborates the
  ACPI participant path. No proprietary binaries are included.
- Local checks: 43 tests, 100% Python statement/branch coverage, Ruff, mypy,
  compiler warnings, clangd, ShellCheck, ASL compiler and actionlint.
- Hosted CI is validating Python 3.10/3.12/3.14 and two Ubuntu HWE kernel builds.
- Still unverified: cold boot/AC loss, physical suspend/resume, other BIOS versions,
  fan RPM/PWM and recovery during a kernel or ACPI hang. See docs/validation.md.
