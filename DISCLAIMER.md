# Experimental hardware control — your responsibility

You use, install, modify and tune this software at your own risk and on your own
responsibility. It can stop the fan. Incorrect settings, unsupported hardware,
software defects or failures can cause overheating, instability, data loss,
service interruption or permanent hardware damage.

The project is provided without warranty under the MIT license, with the kernel
code alternatively available under GPL-2.0-only. It is independent of CHUWI and
Intel and is not a vendor-supported firmware update or product.

A three-second kernel lease, temperature checks and full-on recovery reduce risk;
they cannot guarantee cooling. A kernel crash, blocked ACPI interpreter, failed
fan, unavailable temperature sensor or power problem can defeat software controls.
No fan tachometer has been found: a GPIO output reading is not proof of rotation.
Keep the vents clear and verify temperatures and physical fan behavior yourself.

Only the exact documented board and firmware implementation are supported. Do not
bypass compatibility checks or reuse register addresses on another computer.
Back up important data and plan validation around your own service availability.
