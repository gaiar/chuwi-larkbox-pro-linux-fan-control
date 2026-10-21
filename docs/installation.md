# Install on Ubuntu Server

## Supported hardware

Tested on **CHUWI LarkBox Pro, Intel Celeron J4125, BIOS GB01_ZW_1_07**
(2022-06-08), Ubuntu 24.04, kernel 6.8.0-147-generic. This is not support for
LarkBox X, LarkBox S, the original non-Pro board, or arbitrary CHUWI mini PCs.
The supplied older BIOS 1.05 was analyzed but is not supported by this driver.

The module checks the model, vendor, BIOS version and the exact ACPI control
implementation. A matching name alone is insufficient. Unknown firmware fails
closed. There is no override parameter to bypass those checks.

Read [the responsibility disclaimer](../DISCLAIMER.md) before installing. You
should be able to observe the physical fan and temperature during first use.
The installer enables a service that can stop the fan when the CPU is cool.

## Prerequisites

```sh
cat /sys/class/dmi/id/product_name
cat /sys/class/dmi/id/bios_version
uname -r
sudo apt update
sudo apt install git build-essential dkms python3-venv linux-headers-$(uname -r)
```

Python 3.10 or later is required. Runtime Python uses only the standard library.

An unsigned module cannot load when Secure Boot policy requires a trusted
signature. Use your Ubuntu DKMS/MOK signing workflow, or disable Secure Boot in
firmware if that is appropriate for your machine. Check with `mokutil --sb-state`.
See [Ubuntu Secure Boot documentation](https://wiki.ubuntu.com/UEFI/SecureBoot).
Plan any required reboot around your services; the installer never reboots.

## Install

```sh
git clone https://github.com/gaiar/chuwi-larkbox-pro-linux-fan-control.git
cd chuwi-larkbox-pro-linux-fan-control
sudo ./scripts/install.sh
```

The installer builds through DKMS, first probes the machine in read-only mode,
then enables guarded control and the systemd service. It preserves an existing
`/etc/larkbox-fan.json`. Hardware rejection or a build error stops installation.
It does not flash firmware, write UEFI variables, change CPU clocks/power limits,
or disable thermald. No BIOS Smart Fan change is needed for the runtime control
path: the service selects the native runtime policy whenever it commands the fan.

Check the result:

```sh
systemctl status larkbox-fan --no-pager
cat /sys/kernel/larkbox_fan/status
cat /run/larkbox-fan/state.json
journalctl -u larkbox-fan -f
```

Expect full cooling for at least the first 30 seconds. If all CPU readings remain
cool, the fan can then stop. `fan_on` is GPIO state, not RPM. Confirm the physical
fan operates and temperatures remain sensible.

## Kernel upgrades

DKMS registers `larkbox-fan/0.1.0` and rebuilds for new kernels when matching headers
are available. The module and service are configured to load at boot. Build and
verify the next kernel before rebooting:

```sh
dkms status -m larkbox-fan -v 0.1.0
# Substitute the actual installed next-kernel version:
sudo dkms autoinstall -k NEXT_KERNEL_VERSION
modinfo -k NEXT_KERNEL_VERSION larkbox_fan
```

After reboot, check `uname -r`, `dkms status`, module status and service status.
A kernel API change, missing headers or Secure Boot signature failure can prevent
loading. Hosted CI checks DKMS compilation on Ubuntu HWE headers; it does not
prove live cooling on every kernel. If the driver cannot load, the firmware's
original behavior applies and the custom service cannot control cooling.

The reboot/power-loss path has not yet been physically validated on the original
server; deployment was tested without interrupting its services.

## Update this project

```sh
git pull --ff-only
sudo ./scripts/install.sh
```

The installer stops an existing service and requests full cooling before
replacing the module. Configuration is preserved and validated before restart.
If a new BIOS no longer matches, keep full cooling and collect fresh read-only
ACPI evidence; do not remove the compatibility gate.

## Troubleshooting and removal

- `No such device` during module load: unsupported board, BIOS or ACPI fingerprint.
- `Key was rejected by service`: Secure Boot/module-signing issue.
- `control_enabled: 0`: module is in read-only mode. Stop the service, unload it,
  then load with `sudo modprobe larkbox_fan allow_control=1` and start the service.
- `lease_expired`, temperature or output errors: inspect `journalctl -u larkbox-fan`
  and `journalctl -k`. Full cooling is requested. Resolve the cause, then restart.
- No RPM: the confirmed firmware interface exposes only an on/off output.

```sh
sudo ./scripts/uninstall.sh
```

Removal requests full cooling, unloads the helper/module and removes DKMS/startup
registration. It retains configuration and `/opt/larkbox-fan` for review. Original
BIOS behavior returns after reboot.
