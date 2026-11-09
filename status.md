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

## Startup persistence hardening

- Added a required one-shot preparation service that explicitly loads coretemp
  and the fan driver before each daemon start; failures are visible rather than
  skipped by ConditionPathExists. Runtime safety faults still require manual
  restart after diagnosis, preserving full-on behavior.
- Installer now builds the running kernel plus installed fallback boot images
  with available headers. Both 6.8.0-147 and 6.8.0-146 are installed on the target.
- Live test began with SFAN=0, full-on output and the module unloaded. Starting
  only the main service loaded dependencies and returned to quiet operation at
  40°C after 30 seconds, with no fault.
- Server boot ID, existing container, thermald, schedutil and Turbo state stayed
  unchanged. Physical AC-loss/BIOS-reset validation remains outstanding.
- Added systemd verification to installer/CI and documented the boot sequence,
  diagnostic commands and distinction from BIOS automatic power-on behavior.
- Full local checks: 43 tests, 100% Python statement/branch coverage, Ruff, mypy,
  ShellCheck and actionlint passed. Driver source and thermal policy unchanged.

## 63°C switch-on threshold — 0.2.0

- Two weeks of logs showed the 58°C profile starting the fan three to four
  times a day, almost always for the 30-second minimum after short load spikes.
- Kernel off-admission limit raised from 60°C to 64°C; `on_c` may now be up to
  63°C. The 65°C emergency guard and firmware STMP=65 threshold are unchanged.
  The shipped default remains the validated 58°C profile.
- Installer and uninstaller remove every registered DKMS version.
- 45 tests, 100% statement/branch coverage, Ruff, mypy and ShellCheck passed.
- Live check with `on_c` 63 passed: no switch-on at 59–61°C, off accepted at
  62°C TCPU, on at 63°C, peak 65°C, no faults. See docs/validation.md.
