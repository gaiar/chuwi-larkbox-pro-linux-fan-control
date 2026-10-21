# Validation and limitations

Validated on one CHUWI LarkBox Pro (J4125), BIOS GB01_ZW_1_07, Ubuntu 24.04,
kernel 6.8.0-147-generic, on 2026-10-21. No reboot or firmware flash was performed.

## Software checks

- 43 Python/C-meter tests; Python statement and branch coverage 100%.
- Ruff formatting/lint and strict mypy pass.
- Kernel module built with W=1 and -Werror on the live kernel.
- clangd 18 checked the driver with the real kernel compilation database and the
  C microphone meter: zero errors. ASL helper compiles without warnings.
- ShellCheck and actionlint pass for installation scripts and CI.

## Live control and fault recovery

- Read-only module probe passed its model, BIOS and ACPI checks; control rejected.
- Full-on set SFAN=0 and GPIO 0x44000201. Fan-off set SFAN=1, STMP=65 and GPIO
  0x44000200 at cool temperatures. Linux pinctrl showed GPIO_138 following both.
- A single off lease expired after three seconds; the next four-second observation
  showed full-on, SFAN=0, lease zero and `lease_expired`. Further off commands were
  refused until explicit on reset.
- SIGKILL of the running service while the fan was off restored full-on at the
  three-second observation; the fault stayed latched.
- Module unload/reload left full cooling and reused the helper table successfully.
- The installed DKMS/systemd service is active and enabled. Its first 30-second
  run ended with normal fan-off operation, valid temperatures and no fault.
- The temporary service cooled and stopped the fan after its initial 30-second
  run. Existing thermald, Turbo-enabled state and the server container stayed up.

## Microphone observations

Anker PowerConf C200 beside the mini PC, ALSA hw:C200,0, 48 kHz stereo S16_LE,
capture gain 100. The channels reported identical measurements. No raw audio or
video was saved. The device exposes no AGC switch; internal processing is unknown.

| State | Sample duration | Relative RMS level |
| --- | ---: | ---: |
| Initial native fan-off state | 10 s | -32.25 dBFS |
| Forced full-on | 15 s | -29.44 dBFS |
| Automatic idle, fan off | 3 × 15 s | -32.47, -32.21, -31.63 dBFS |
| Automatic workload, fan on | 15 s | -30.59 dBFS |

The fan-off samples were quieter, with roughly 1–3 dB differences from these
fan-on samples. Room sound and webcam processing limit precision. These are
DC-removed, unweighted dBFS values, **not calibrated dBA/SPL** and not a sound-power
measurement. There is no tachometer, so physical speed is not quantified.

## Performance test

Matched 120-second OpenSSL SHA-256 tests, 16 KiB blocks, four workers, nice +10,
followed by a one-minute cooling observation. Stock schedutil/Turbo settings were
kept. The workload had an 80°C abort limit.

| Policy | Aggregate throughput | Peak hottest CPU |
| --- | ---: | ---: |
| Fan continuously on | 2387.91 MB/s | 63°C |
| Automatic 58°C on / 50°C off | 2375.77 MB/s | 64°C |

The automatic run started at 41°C with the fan off, switched on at 58°C after
13.55 seconds, and stopped the fan at 46°C, 16.12 seconds after the workload
ended. It finished the cooling observation at 45°C, with no fault.

Automatic throughput was 99.49% of the full-on result in this single comparison;
a difference this small is not proof of a repeatable performance penalty. The
policy gives quiet idle intervals and full cooling for sustained load. It is a
measured starting profile, not a globally optimal curve for every environment.
Historical throttle counters existed before this work and did not increase during
the sampled checks; this is not a claim that the machine has never throttled.

## Still unverified

- Cold boot after AC loss, BIOS reset and the installed service's first reboot.
- Suspend/resume on physical hardware (the driver has explicit handling).
- Other BIOS versions or board revisions, fan RPM and continuous PWM capability.
- Kernel crashes, unresponsive firmware and fan electrical/mechanical failure.
- Acoustic behavior in other rooms, enclosures or microphone placements.
