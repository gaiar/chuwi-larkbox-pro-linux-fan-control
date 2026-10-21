#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
echo 'Stopping control and returning to full cooling…'
if systemctl list-unit-files larkbox-fan.service --no-legend | grep -q larkbox-fan; then
    systemctl disable --now larkbox-fan.service
fi
if [ -d /sys/module/larkbox_fan ]; then
    if [ "$(cat /sys/module/larkbox_fan/parameters/allow_control)" = Y ]; then
        printf 'on\n' > /sys/kernel/larkbox_fan/command
    fi
    rmmod larkbox_fan
fi
if dkms status -m larkbox-fan -v 0.1.0 | grep -q .; then
    dkms remove -m larkbox-fan -v 0.1.0 --all
fi
rm -f /etc/systemd/system/larkbox-fan.service \
    /etc/systemd/system/larkbox-fan-prepare.service /etc/modprobe.d/larkbox-fan.conf \
    /etc/modules-load.d/larkbox-fan.conf
systemctl daemon-reload
echo 'Removed startup and DKMS registration. Configuration and /opt sources retained.'
echo 'After reboot the original BIOS behavior applies again.'
