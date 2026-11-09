#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
version=0.2.0
project_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$(cat /sys/class/dmi/id/product_name)" != 'LarkBox Pro' ] ||
   [ "$(cat /sys/class/dmi/id/bios_version)" != 'GB01_ZW_1_07' ]; then
    echo 'Only CHUWI LarkBox Pro BIOS GB01_ZW_1_07 is supported.' >&2
    exit 1
fi
for tool in dkms make cc python3 systemctl systemd-analyze modprobe rmmod; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
[ -d "/lib/modules/$(uname -r)/build" ] || {
    echo 'Install headers matching the running kernel first.' >&2; exit 1;
}
printf 'Preparing full cooling and building the kernel module…\n'
if systemctl is-active --quiet larkbox-fan.service; then
    systemctl stop larkbox-fan.service
fi
if [ -d /sys/module/larkbox_fan ]; then
    if [ "$(cat /sys/module/larkbox_fan/parameters/allow_control)" = Y ]; then
        printf 'on\n' > /sys/kernel/larkbox_fan/command
    fi
    rmmod larkbox_fan
fi
# Remove every registered version, including releases before this script.
for registered in $(dkms status -m larkbox-fan |
    sed -n 's|^larkbox-fan[/, ]\{1,2\}\([^,:]*\)[,:].*|\1|p' | sort -u); do
    dkms remove -m larkbox-fan -v "$registered" --all
done
install -d "/usr/src/larkbox-fan-$version"
install -m 0644 "$project_root/kernel/Makefile" "$project_root/kernel/dkms.conf" \
    "$project_root/kernel/larkbox_fan.c" "$project_root/kernel/larkbox_control.hex" \
    "/usr/src/larkbox-fan-$version"/
dkms add -m larkbox-fan -v "$version"
dkms build -m larkbox-fan -v "$version" -k "$(uname -r)"
dkms install -m larkbox-fan -v "$version" -k "$(uname -r)"
# Cover installed fallback boot images too; DKMS autoinstall covers future kernels.
for kernel_image in /boot/vmlinuz-*; do
    [ -f "$kernel_image" ] || continue
    kernel_version=${kernel_image##*/vmlinuz-}
    [ "$kernel_version" != "$(uname -r)" ] || continue
    if [ ! -d "/lib/modules/$kernel_version/build" ]; then
        printf 'WARNING: %s lacks headers; install linux-headers-%s before booting it.\n' \
            "$kernel_version" "$kernel_version" >&2
        continue
    fi
    printf 'Building fan support for fallback kernel %s…\n' "$kernel_version"
    dkms build -m larkbox-fan -v "$version" -k "$kernel_version"
    dkms install -m larkbox-fan -v "$version" -k "$kernel_version"
done
printf 'Checking firmware compatibility in read-only mode…\n'
modprobe larkbox_fan allow_control=0
cat /sys/kernel/larkbox_fan/status
rmmod larkbox_fan
printf 'Installing and validating the thermal service…\n'
install -d /opt/larkbox-fan
python3 -m venv --without-pip /opt/larkbox-fan/venv
install -m 0644 "$project_root/larkbox_fan.py" /opt/larkbox-fan/
if [ ! -e /etc/larkbox-fan.json ]; then
    install -m 0644 "$project_root/deploy/larkbox-fan.json" /etc/larkbox-fan.json
fi
/opt/larkbox-fan/venv/bin/python /opt/larkbox-fan/larkbox_fan.py \
    --config /etc/larkbox-fan.json --check-config
install -m 0644 "$project_root/deploy/larkbox-fan.service" \
    "$project_root/deploy/larkbox-fan-prepare.service" /etc/systemd/system/
printf 'options larkbox_fan allow_control=1\n' > /etc/modprobe.d/larkbox-fan.conf
printf 'coretemp\nlarkbox_fan\n' > /etc/modules-load.d/larkbox-fan.conf
systemd-analyze verify /etc/systemd/system/larkbox-fan.service \
    /etc/systemd/system/larkbox-fan-prepare.service
systemctl daemon-reload
systemctl enable --now larkbox-fan.service
systemctl is-active --quiet larkbox-fan.service
printf 'Installed. Watch: journalctl -u larkbox-fan -f\n'
printf 'Configuration: /etc/larkbox-fan.json; changes require a service restart.\n'
