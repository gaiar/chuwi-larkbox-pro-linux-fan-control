# Project status

Version 0.1.0: implemented and live-tested on LarkBox Pro BIOS GB01_ZW_1_07,
Ubuntu 24.04 and kernel 6.8.0-147-generic. DKMS driver and systemd service installed.

Confirmed binary fan control, temperature policy, lease expiry, SIGKILL recovery,
module unload/reload, microphone comparisons and matched CPU benchmarks.
43 tests pass with 100% Python statement and branch coverage; clangd reports no
errors for the driver and meter. See docs/validation.md for measurements.

Remaining: physical cold-boot/power-loss and suspend/resume validation; other BIOS
versions; additional evidence for PWM or RPM. The Windows image is being inspected
as supplementary evidence. Public CI is configured; hosted results are pending.
