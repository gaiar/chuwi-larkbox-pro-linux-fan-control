# Firmware evidence and Linux control path

Claims below distinguish **seen** evidence from **inferred** behavior and **unknown**
capabilities. Analysis uses the leanrea process: preserve inputs, identify file
formats, inventory, extract, then trace targeted code and compare with the machine.

## Inputs and extraction

The supplied `LarkBox Pro 原物のBIOS.rar` is a RAR5 archive, SHA-256
`3b66c22d570dde798d6252a14c3375c326e02e1a62b69779ecaca2a7e17c1b8d`.
It contains the directory `GB01_ZW_1_05_202009171748` and an 8 MiB `bios.bin`, hash
`54a0d9b21033e38167245d4f7a08a65f964b9ab6499c7efdd129d9f79e224e73`.
The live BIOS is **GB01_ZW_1_07**, dated 2022-06-08. No firmware was flashed.

`7zz l` inventoried the archive. This installed 7zz build could not decompress its
RAR method; `bsdtar -xf` succeeded. UEFIExtract A75's initial BPDT traversal did
not expose the DXE volume. Carving the valid FV at file offset `0x343000`, length
`0x34f000`, and extracting that copy recovered the DXE/SMM/ACPI components.
IFRExtractor 1.6.1 decoded Setup; iasl 20260408 disassembled ACPI; LLVM objdump
traced `CpuFanControlSmi`. Work copies remain under `$TMPDIR/re/larkbox-pro-20261021`.

## The fan is controlled by firmware AML and a GPIO

**Seen, live BIOS 1.07:** SSDT `DptfTab`, length 17231, CRC32 `434cda59`, SHA-256
`bbd13f37bcc2d718fdf3735f43953fa7a9ee7e724faf2b21ef343a109ee0f2ac`.
In disassembled `SSDT1.dsl`, `\_SB.SEN4._TMP` (line 2091) does this:

- If `SFAN == 1`: turn on above `STMP`, turn off below `STMP - 3`.
- Otherwise: force on.
- The output values are `0x44000201` (on) and `0x44000200` (off).
- Temperature comes from `\_SB.PCI0.TCPU.TMP1`, not the value returned by SEN4.

**Seen:** DSDT `\_SB.GPO0.TMPN` maps eight bytes at physical `0xd0c509e0`.
The 32-bit `TMPE` field controls the output. Its AML declaration begins at DSDT
file offset `0x70c3` (the `TMPN` name starts at `0x70c5`). Linux pinctrl debug
output independently shows `INT3453:01` pin 62, `GPIO_138`, changing between those
values when fan commands change. The driver uses ACPI, not direct MMIO writes.

**Seen:** `\SFAN` and `\STMP` are fields in GNVS (ACPI NVS RAM). The initial
live read returned `SFAN=1`, `STMP=65`, output off and CPU roughly 44–48°C.
Changing them through AML changes current runtime behavior; this project never
writes persistent UEFI variables or flashes a BIOS.

**Seen, archive 1.05:** its DptfTab instead switches the same output at a fixed
55°C, without the later SFAN/STMP branch. This is why the old archive is useful
research evidence but is not the compatibility target for the driver.
`CpuFanControlSmi` GUID `3C1FB503-BDA8-41A7-BB5C-12E2083E6DDB`, image offset
`0x424`, also writes to this GPIO in its sleep-state handler.

## Misleading interfaces

**Seen:** `H_EC._STA` returns zero; `ECRD` returns constants and `ECWT` cases have
empty bodies. The generic ACPI `FAN0` power methods call these stubs. Linux's
`cooling_device0` therefore reports an on/off fan state that is not reliable
feedback for this physical fan. An ITE comment in `Startup.nsh` is not proof of an
ITE controller: the actual script invokes an AMI BIOS flasher.

**Seen:** `SEN4._TMP` returns `0x0bb8`, exposed as 26.85°C, when the EC is
unavailable. Its apparent “skin temperature” is a placeholder; reading it also
runs the GPIO control logic. `INT3400 Thermal` is not a measured CPU sensor.
The daemon uses all five `coretemp` inputs; the kernel guard checks TCPU's package
reading. Wi-Fi temperature is available but is not a fan policy input.

**Unknown:** tachometer/RPM, variable-speed PWM, additional fan electrical modes,
and any independent controller watchdog. No RPM or continuous PWM interface is
claimed. This project implements a binary temperature policy.

## Implementation and recovery

The module gates control on CHUWI vendor/model, BIOS 1.07, the live DptfTab
fingerprint and exact DSDT GPIO-field declaration. It loads our small helper SSDT
with a unique method that changes SFAN/STMP through the interpreter and invokes
the existing SEN4 routine. It does not replace or patch vendor AML.

On = SFAN 0 plus a native poll. Off = SFAN 1, STMP 65 plus a native poll, only
accepted below a 64°C package reading (60°C before 0.2.0). Native polls can still turn cooling back
on above 65°C. Off must be renewed within three seconds. A 250 ms kernel worker
checks the lease and package temperature; 65°C, read failure or lease expiry
requests full cooling and latches a fault. An explicit on command clears a fault.
Suspend/resume and module unload also request full cooling.

The helper namespace is unloaded with the module. ACPICA retains table
descriptors, so its 159-byte heap buffer stays resident and is reused on reload;
it never points into freed module memory. No persistent firmware change remains.

These are software safeguards. A stalled kernel or ACPI interpreter can prevent
recovery. See [DISCLAIMER.md](../DISCLAIMER.md).

## Windows factory-image cross-check

**Seen:** the supplied Windows archive completed during the investigation. Its
SHA-256 is `a6cfd8e5ca5cf95631c9ec50afdc7aaba02da2567280b631d3b421b75baf8f43`.
The main WIM identifies Windows 10 Home build 18363.1256. A copy was extracted
with `bsdtar`; `7zz` inventoried the WIM and extracted only the two DPTF driver
packages, 29 files totaling about 20 MB. No Windows binaries were executed.

Under `Windows/System32/DriverStore/FileRepository`:

- `dptf_acpi.inf_amd64_9d4c8f33f98958fc/dptf_acpi.inf`, line 29, identifies Intel
  DPTF **8.4.11000.6436**, dated 2018-04-27. Lines 52–65 bind the standard Intel
  ACPI participant IDs, including INT3403 (generic) and INT3404 (fan).
- `dptf_cpu.inf_amd64_52334f33ec642379/dptf_cpu.inf` registers `esif_lf` and
  `esifsvc`, with `esif_lf.sys`, `esif_umdf2.dll` and `esif_uf.exe`.
- `esif_lf.sys`, SHA-256
  `01c157d26996a27b5c3d06ddfa0f58319681bb6c7b9089d21b8e61b3e826655d`,
  has a `_TMP` action dispatch at image RVA `0xa4c8`, branching to `0xa541` and
  calling the handler at `0xae14`. This is static code evidence, not a trace of
  the running Windows system.
- `dptf_acpi.sys`, SHA-256
  `0203f6844fdec4eaa31d0f8441e2e0be07f9b7cf55155addd15cf52008bdde2b`,
  contains the diagnostic identifier `acpi_evaluate_object` at file offset
  `0x8b80`. The framework also carries temperature and polling policy components.

**Inferred:** Intel DPTF's ACPI temperature queries are a plausible trigger for
this BIOS's side-effecting SEN4 temperature method under Windows. The installed
packages support that explanation; their presence does not prove the exact
Windows polling schedule. Linux live tests independently established the control
path. No Windows driver is needed by the service, and no vendor binaries are
redistributed. Variable-speed capability remains unconfirmed.

## Follow-up: PWM versus on/off

The [PWM investigation](pwm-investigation.md) adds PEI/SMM disassembly, Intel pin
capabilities, live ACPI queries and the Windows fan-level dispatch. GPIO_138 has
no native hardware PWM alternate function; the apparent ACPI percentage backend
is inactive. Electrical modification or software PWM remains unverified.

## Primary references

- [Intel Gemini Lake pinctrl driver](https://github.com/torvalds/linux/blob/v6.8/drivers/pinctrl/intel/pinctrl-geminilake.c)
- [Intel GPIO register implementation](https://github.com/torvalds/linux/blob/v6.8/drivers/pinctrl/intel/pinctrl-intel.c)
- [ACPICA dynamic table loading and lifetime contract](https://github.com/torvalds/linux/blob/v6.8/drivers/acpi/acpica/tbxfload.c)
- [ACPICA table-unload implementation](https://github.com/torvalds/linux/blob/v6.8/drivers/acpi/acpica/tbdata.c)
- [Linux ACPI configfs table loading](https://github.com/torvalds/linux/blob/v6.8/drivers/acpi/acpi_configfs.c)

The owner reports that Smart Fan resets after loss of power because the machine
has no backup battery. The power-loss condition has not been reproduced during
this investigation; the server was kept running. Runtime full-on/off paths have
been tested independently of persistent BIOS settings.
