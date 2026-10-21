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
- [Hosted CI passed](https://github.com/gaiar/chuwi-larkbox-pro-linux-fan-control/actions/runs/39596525546): Python 3.10/3.12/3.14 and both Ubuntu HWE
  DKMS/compiler/clangd jobs.
- Still unverified: cold boot/AC loss, physical suspend/resume, other BIOS versions,
  fan RPM/PWM and recovery during a kernel or ACPI hang. See docs/validation.md.

## PWM follow-up

- Used leanrea to inventory 252 distinct firmware PE/TE images, including newly
  extracted PEI volumes; traced GPIO_138's PlatformInit record and SMM off write.
- Intel pin map rules out native hardware PWM on GPIO_138; PWM0–3 use GPIO_42–45.
- Read-only live queries confirmed DFAN=0, ECAV=0, TFN1 absent and RPM undefined.
- Windows DPTF primitive 87 maps to _FSL, whose firmware backend is inactive.
- Documented the distinction between proven stock on/off control and unverified
  electrical modifications or software PWM. Existing daemon/config unchanged.
