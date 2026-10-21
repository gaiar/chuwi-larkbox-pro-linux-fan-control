# CHUWI LarkBox Pro Fan Control for Linux and Ubuntu

[![CI](https://github.com/gaiar/chuwi-larkbox-pro-linux-fan-control/actions/workflows/ci.yml/badge.svg)](https://github.com/gaiar/chuwi-larkbox-pro-linux-fan-control/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Quiet **CHUWI LarkBox Pro Linux fan control** for the Intel Celeron J4125 mini PC.
A guarded kernel module and Python systemd service stop the fan when the CPU is
cool and start full cooling when needed. The runtime policy works independently
of the saved BIOS **Smart Fan** setting, addressing the always-running fan after
that setting resets.

**Experimental hardware control. Use it at your own risk and responsibility.**
Read the [disclaimer](DISCLAIMER.md) and verify your exact hardware before install.

## Supported machine

| Component | Validated target |
| --- | --- |
| Mini PC | CHUWI LarkBox Pro |
| CPU | Intel Celeron J4125, four cores |
| BIOS | `GB01_ZW_1_07`, 2022-06-08 |
| Operating system | Ubuntu 24.04 Server |
| Live-tested kernel | `6.8.0-147-generic` |
| Fan interface | Firmware ACPI Smart Fan routine driving a GPIO: on/off |

The module also verifies the ACPI implementation. Other BIOS versions, LarkBox X,
LarkBox S and other CHUWI models are not supported. **RPM feedback and adjustable
PWM speed have not been found.** The configurable curve is an on/off temperature
policy; no fan-speed numbers are invented. The [deeper PWM investigation](docs/pwm-investigation.md)
traces the BIOS initialization, inactive ACPI percentage methods, Windows drivers
and the fan pin’s lack of hardware PWM multiplexing.

## What it does

- Samples CPU package and all four core temperatures; uses the hottest reading.
- Starts cooling immediately at 58°C; allows stopping at/below 50°C after a stable
  10-second cooling period and a minimum 30-second fan run.
- Uses a three-second kernel off lease and independent temperature guard.
- Requests full cooling on service exit, missed leases, temperature faults,
  suspend/resume and module unload.
- Builds through DKMS for kernel updates and starts through systemd.
- Leaves CPU Turbo, clock/power policy and thermald in place.
- Includes a microphone level tool that retains statistics, not audio recordings.

A kernel or ACPI failure can defeat software safeguards. GPIO state is not proof
that the fan is physically spinning; see [limitations](DISCLAIMER.md).

## Install on Ubuntu

```sh
sudo apt update
sudo apt install git build-essential dkms python3-venv linux-headers-$(uname -r)
git clone https://github.com/gaiar/chuwi-larkbox-pro-linux-fan-control.git
cd chuwi-larkbox-pro-linux-fan-control
sudo ./scripts/install.sh
```

First read [installation and Secure Boot requirements](docs/installation.md).
The installer probes compatibility read-only before enabling control, preserves
existing configuration and never flashes firmware or reboots the server.

```sh
systemctl status larkbox-fan --no-pager
cat /run/larkbox-fan/state.json
cat /sys/kernel/larkbox_fan/status
journalctl -u larkbox-fan -f
```

## Tune temperature, hysteresis and noise

Edit `/etc/larkbox-fan.json`, validate it, then restart the service:

```sh
sudoedit /etc/larkbox-fan.json
sudo /opt/larkbox-fan/venv/bin/python /opt/larkbox-fan/larkbox_fan.py \
  --config /etc/larkbox-fan.json --check-config
sudo systemctl restart larkbox-fan
```

The [configuration guide](docs/configuration.md) explains every parameter, safe
bounds, alternative thresholds, microphone measurement and rollback. Wider
hysteresis and minimum run time reduce frequent starts/stops. The best settings
depend on airflow, ambient temperature and workload.

## Why Linux needs this

The live BIOS implements Smart Fan inside `SEN4._TMP`, an ACPI temperature-read
method. Reading it executes fan control, even though its reported “skin” reading
is a placeholder. The apparent ACPI EC/fan controls are stubs. Our module invokes
the verified native routine through an original, temporary ACPI helper and
reapplies the runtime state when commanded. It does not need a Windows driver,
a BIOS flash or direct `/dev/mem` writes.

See [firmware findings and sensor limitations](docs/research.md) and
[validation results](docs/validation.md). BIOS 1.05 differs from the live 1.07
implementation and is not treated as compatible.

## Measured result

In one matched two-minute, four-worker SHA-256 comparison, the automatic policy
achieved **99.49% of full-on throughput**, with a **64°C** peak versus 63°C with
the fan continuously on. Idle microphone samples were roughly 1–3 dB lower than
fan-on samples. These are relative webcam readings, not calibrated dBA. See the
[test method and limitations](docs/validation.md) before comparing results.

## Kernel updates, removal and development

DKMS rebuilds for new kernels when headers and a compatible toolchain are present.
Check the build and module signature before rebooting; follow the
[kernel-update checklist](docs/installation.md#kernel-upgrades). CI compiles on
Ubuntu HWE kernels; hosted runners never load the module.

Remove the startup service and DKMS registration with:

```sh
sudo ./scripts/uninstall.sh
```

See [contributing and tests](CONTRIBUTING.md). MIT is the default license; kernel
C/AML is dual-licensed **GPL-2.0-only OR MIT**. [Licensing details](LICENSING.md).
This is an independent community project, not affiliated with CHUWI or Intel.
