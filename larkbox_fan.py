# SPDX-License-Identifier: MIT
"""Control the verified LarkBox Pro's binary fan with bounded kernel leases."""

from __future__ import annotations

import argparse
import json
import logging
import math
import signal
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from types import FrameType
from typing import Any

LOG = logging.getLogger("larkbox-fan")


@dataclass(frozen=True)
class Profile:
    """Define conservative temperatures and delays for the on/off fan."""

    on_c: float = 58.0
    off_c: float = 50.0
    min_on_s: float = 30.0
    cool_delay_s: float = 10.0
    interval_s: float = 0.5

    def __post_init__(self) -> None:
        """Reject values that could defeat the tested thermal and lease limits."""
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        # The kernel refuses off leases at 64 C, so cooling must start by 63 C.
        if not 40 <= self.off_c <= self.on_c - 5 or not self.on_c <= 63:
            raise ValueError("Require 40 <= off_c <= on_c - 5 and on_c <= 63")
        if not 10 <= self.min_on_s <= 300:
            raise ValueError("min_on_s must be between 10 and 300")
        if not 2 <= self.cool_delay_s <= 60:
            raise ValueError("cool_delay_s must be between 2 and 60")
        if not 0.25 <= self.interval_s <= 0.75:
            raise ValueError("interval_s must be between 0.25 and 0.75")


def load_profile(path: Path) -> Profile:
    """Read and strictly validate a JSON profile."""
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")
    unknown = set(data) - set(Profile.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Unknown configuration keys: {sorted(unknown)}")
    return Profile(**data)


class Policy:
    """Switch cooling on promptly and require stable cooling before stopping."""

    def __init__(self, profile: Profile, now: float) -> None:
        """Start with full cooling and no pending cool-down."""
        self.profile = profile
        self.on = True
        self.changed_at = now
        self.cool_since: float | None = None
        self.previous = now

    def update(self, temp_c: float, now: float) -> bool:
        """Return the requested state or reject stale/invalid samples."""
        if not math.isfinite(temp_c) or not 0 <= temp_c <= 110:
            raise ValueError("CPU temperature outside 0..110 C")
        if not math.isfinite(now) or not 0 <= now - self.previous <= 2:
            raise ValueError("Control loop missed its two-second deadline")
        self.previous = now
        if temp_c >= self.profile.on_c:
            if not self.on:
                self.changed_at = now
            self.on = True
            self.cool_since = None
        elif self.on:
            if temp_c > self.profile.off_c:
                self.cool_since = None
            else:
                if self.cool_since is None:
                    self.cool_since = now
                if (
                    now - self.cool_since >= self.profile.cool_delay_s
                    and now - self.changed_at >= self.profile.min_on_s
                ):
                    self.on = False
                    self.changed_at = now
                    self.cool_since = None
        return self.on


def discover_cpu(root: Path = Path("/sys/class/hwmon")) -> list[Path]:
    """Find all five coretemp readings on the supported four-core J4125."""
    for hwmon in sorted(root.glob("hwmon*")):
        if (hwmon / "name").read_text().strip() == "coretemp":
            paths = sorted(hwmon.glob("temp*_input"))
            if len(paths) != 5:
                raise ValueError("Expected package plus four core temperatures")
            return paths
    raise ValueError("coretemp sensor not found")


def read_cpu(paths: list[Path]) -> float:
    """Read every CPU channel and fail rather than ignore an unavailable core."""
    if len(paths) != 5:
        raise ValueError("Expected five CPU channels")
    temperatures = [int(path.read_text().strip()) / 1000 for path in paths]
    if any(not 0 <= value <= 110 for value in temperatures):
        raise ValueError("Invalid coretemp reading")
    return max(temperatures)


class Device:
    """Use only the driver's bounded on/off command interface."""

    def __init__(self, root: Path = Path("/sys/kernel/larkbox_fan")) -> None:
        """Select the kernel driver's sysfs directory."""
        self.root = root

    def status(self) -> dict[str, Any]:
        """Validate the driver state before renewing a cooling lease."""
        value = json.loads((self.root / "status").read_text())
        if not isinstance(value, dict):
            raise ValueError("Driver status is not an object")
        if value.get("control_enabled") != 1:
            raise ValueError("Kernel driver is not enabled for control")
        if value.get("fault") != "none":
            raise ValueError(f"Kernel safety guard: {value.get('fault')}")
        if value.get("gpio_raw") not in (0x44000200, 0x44000201):
            raise ValueError("Unexpected GPIO configuration")
        return value

    def command(self, on: bool) -> None:
        """Request full cooling or renew a three-second off lease."""
        (self.root / "command").write_text("on\n" if on else "off\n")


def write_state(path: Path, state: dict[str, Any]) -> None:
    """Replace the runtime state atomically for status readers."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True) + "\n")
    temporary.replace(path)


def run(
    profile: Profile,
    device: Device,
    sensors: list[Path],
    state_path: Path,
    stopped: Callable[[], bool],
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Run the control loop, restoring full cooling on every orderly exit."""
    try:
        device.command(True)
        device.status()
        policy = Policy(profile, clock())
        previous: bool | None = None
        LOG.info("Started; profile=%s", asdict(profile))
        while not stopped():
            before = clock()
            temperature = read_cpu(sensors)
            device.status()
            on = policy.update(temperature, clock())
            device.command(on)
            observed = device.status()
            if observed.get("fan_on") != int(on):
                raise ValueError("Fan output differs from requested state")
            state = {
                "temperature_c": temperature,
                "fan_on": on,
                "profile": asdict(profile),
                "driver": observed,
                "updated_unix": time.time(),
            }
            write_state(state_path, state)
            if on != previous:
                LOG.info(
                    "Fan %s; hottest CPU %.1f C", "on" if on else "off", temperature
                )
            previous = on
            sleep(max(0, profile.interval_s - (clock() - before)))
    finally:
        device.command(True)
        LOG.info("Stopped; requested full cooling")


def main(argv: list[str] | None = None) -> int:
    """Validate a profile or run the fan-control service."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/larkbox-fan.json"))
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        profile = load_profile(args.config)
        if args.check_config:
            print(json.dumps(asdict(profile), indent=2))
            return 0
        stopping = False

        def stop(signum: int, frame: FrameType | None) -> None:
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        run(
            profile,
            Device(),
            discover_cpu(),
            Path("/run/larkbox-fan/state.json"),
            lambda: stopping,
        )
    except (OSError, ValueError, TypeError) as error:
        LOG.error(
            "Fan control stopped: %s; kernel off lease expires within 3.25 s", error
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
