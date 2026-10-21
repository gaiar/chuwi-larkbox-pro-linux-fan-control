# Can the CHUWI LarkBox Pro fan use PWM?

## Result

For the tested J4125 / BIOS **GB01_ZW_1_07**, the working stock firmware interface
is **on/off**. The confirmed fan signal, **GPIO_138**, has **no native hardware PWM
multiplexing option**. The apparent percentage-based ACPI interface terminates in
an inactive EC implementation. The supplied Windows image contains standard DPTF
fan-level support, but that support does not supply the missing board backend.

This rules out simply exposing the existing fan pin as an Intel hardware PWM
channel or unlocking the advertised ACPI fan percentages. It does **not** prove
that every possible electrical modification or software-generated waveform would
be impossible. Fan wiring, switching circuitry and any additional control input
have not been physically inspected.

## Firmware investigation with leanrea

Original inputs were preserved. In addition to the previous DXE/SMM extraction,
valid firmware volumes at BIOS offsets `0x0a3000` (length `0x1000`), `0x0a4000`
(`0x80000`) and `0x124000` (`0xb0000`) were carved and extracted using UEFIExtract
A75. The combined inventory contains **252 distinct PE/TE images**, deduplicated
by SHA-256. Byte/string searches narrowed the investigation; they are not a proof
that every computed register address or instruction was understood.

Targeted disassembly covered `PlatformInit`, `PlatformInitPreMem`, `SiInit`,
`CpuFanControlSmi` and `Dptf`. The PEI modules are IA32 TE images; their unchanged
section bytes were placed in analysis-only COFF wrappers for LLVM objdump, using
the TE stripped-header adjustment. Vendor firmware was never executed or flashed.

### Early GPIO configuration

**Seen, archive BIOS 1.05:** `PlatformInit`, GUID
`0A5EA2E1-BE0B-44A0-A775-F429C9A018A0`, TE SHA-256
`e866bd2b25caea6ef54535da46e68f5ff730bb376ae2a1dddff7adb3b810e5be`.
Its 20-byte table record at **TE file offset `0xa620`** contains:

- configuration DWORDs `0x04000200` and `0x0003c000`;
- community `0xc5`, pad offset `0x09e0`;
- pointer `0xfff1cb98` to UTF-16 `GPIO_138`, at TE offset `0xbfc4`.

The configuration encodes GPIO mode with output enabled and output state zero,
consistent with the same pad used by the live fan routine. It is not a PWM mode.
This is static evidence from the older archive, corroborated by the live GPIO
mapping; it is not a complete dump of BIOS 1.07's native firmware modules.

### Native SMM fan routine

**Seen:** `CpuFanControlSmi`, GUID
`3C1FB503-BDA8-41A7-BB5C-12E2083E6DDB`, SHA-256
`32948c13ca3e77536c5eaa125686d50460f0595809b59483d24e7b13c7dcec8a`.
The callback at image offset `0x410` checks sleep-state values 3, 4 and 5; at
`0x422` it clears EAX, and at **`0x424`** writes AL to `0xd0c509e0`. The registration
path at `0x430` passes that callback at `0x478`. This is an off write in the sleep
handler, not a duty-cycle or frequency-setting routine.

### The percentage-based ACPI path is inactive

**Seen, live BIOS 1.07:** `SSDT1.dsl` defines `TFN1` / `INT3404` at line 1066.
`_FIF` advertises fine-grained control, and `_FPS` contains percentage/RPM entries.
But `_FSL` at line 1210 only acts when `H_EC.ECAV` is nonzero. `DSDT.dsl` line 6687
initializes ECAV to zero; no assignment changing it was found in the captured
DSDT/SSDTs. `ECWT` at line 6825 has empty case bodies, and `ECMD` at line 6874 is
empty. The advertised RPM numbers are table entries, not measured fan speed.

Read-only queries on the running machine confirmed:

```text
DFAN                       = 0
H_EC.ECAV                  = 0
TFN1._STA                  = 0
TFN1._FIF                  = [0, 1, 2, 0]
TFN1._FST                  = [0, 0xffffffff, 0xffffffff]
```

The generic `FAN0` path also calls the stubbed EC functions. The working path is
`SEN4._TMP`, which writes `0x44000200` or `0x44000201` to GPIO_138. The only
matching `_FIF/_FPS/_FSL/_FST` implementations in the captured tables are TFN1's.
The older Setup IFR's “FAN Device” toggle enables a participant; it does not
implement missing EC writes. Its “PWM-Normal/PWM-Inverted” options belong to
**display backlight control**, not the fan.

## Hardware PWM cross-check

**Seen:** Intel's Gemini Lake datasheet, document 336560 revision 005, page 41,
lists GPIO_138's alternate functions as UART, ISH GPIO and SATA GP0; none is PWM.
Page 45 places PWM0–PWM3 on GPIO_42–GPIO_45. Linux's Gemini Lake pinctrl driver
independently maps the PWM groups to pins 42–45 in mode 2.

On this running unit, those four pads are in mode 1 (display/USB functions), while
GPIO_138 is in GPIO mode. `/sys/class/pwm` is empty even though the running kernel
has all three `CONFIG_PWM_LPSS*` options enabled. The ACPI `PCI0.PWM` declaration
names PCI address `00:1a.0`, which is not enumerated in the live PCI inventory.
Merely enabling that controller would not route its output to GPIO_138.

Sources: [Intel datasheet, pages 41 and 45](https://cdrdv2-public.intel.com/336560/336560-glk-datasheet-volume1_rev005.pdf),
[Linux pinctrl source](https://github.com/torvalds/linux/blob/v6.8/drivers/pinctrl/intel/pinctrl-geminilake.c),
[coreboot pin-function map](https://github.com/coreboot/coreboot/blob/main/util/inteltool/gpio_names/geminilake.h).

## Windows driver cross-check

**Seen:** all **677 DriverStore INF files** in the supplied WIM were extracted and
searched, including UTF-16 files. The relevant fan matches are Intel DPTF's
`INT3404` participant and Windows' generic ACPI fan declaration. PWM references
in the graphics package concern panel brightness. No separate vendor fan/PWM
controller driver was identified by this inventory.

The DPTF libraries contain generic fan-speed policy code. More specifically,
`dsp.dv` contains a 52-byte record at **`0x46c1e`** with primitive ID **87** and
`_FSL` at **`0x46c3e`**. Adjacent records pair IDs 84/85/86 with `_FIF/_FPS/_FST`.
`esif_lf.sys`'s ID-to-name code at RVA `0x1bf04`–`0x1bf23` maps 87 to
`SET_FAN_LEVEL`. Intel's published primitive definitions confirm these IDs.

**Inferred from this mapping:** Windows' generic percentage request uses the
standard ACPI fan interface. The supplied board's `_FSL` backend is inactive, so
the existence of a Windows “set fan level” API is not evidence of working PWM on
this hardware. The separately observed Smart Fan behavior is consistent with
DPTF polling the temperature method that performs binary switching. Windows was
not booted, so its exact runtime polling remains unobserved.

Sources: [Intel primitive IDs](https://github.com/intel/dptf/blob/master/Common/esif_sdk_primitive_type.h),
[ACPI fan method contract](https://uefi.org/specs/ACPI/6.5/11_Thermal_Management.html#fan-device).
Windows artifacts retain the hashes recorded in [research.md](research.md).

## What remains possible, but unverified

- A second control wire or an additional board controller would require physical
  inspection or a schematic to identify. Neither is established by the firmware.
- Software PWM of the on/off GPIO would pulse the existing electrical control.
  Whether that produces stable, safe intermediate fan speed depends on the fan
  and switching circuit. It is not equivalent to discovering a hardware PWM
  channel and was not attempted on the running server.
- No complete BIOS 1.07 SPI image was available; its live ACPI tables were used
  alongside the older 1.05 archive. No destructive bus probing, pin remapping,
  firmware change or service interruption was performed in this follow-up.

The installed daemon remains the measured **58°C on / 50°C off** policy. No
PWM percentage or RPM control is exposed or claimed.
