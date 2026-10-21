"""Exercise thermal limits, config rejection, lease timing and full-on recovery."""

import json
import signal

import pytest

import larkbox_fan as fan


@pytest.mark.parametrize(
    "key,value",
    [
        ("on_c", True),
        ("off_c", "50"),
        ("on_c", float("nan")),
        ("min_on_s", float("inf")),
        ("off_c", 39),
        ("off_c", 56),
        ("on_c", 60),
        ("min_on_s", 9),
        ("min_on_s", 301),
        ("cool_delay_s", 1),
        ("cool_delay_s", 61),
        ("interval_s", 0.2),
        ("interval_s", 0.8),
    ],
)
def test_invalid_profile(key, value):
    with pytest.raises(ValueError):
        fan.Profile(**{key: value})


@pytest.mark.parametrize("data", [[], {"unknown": 1}, {"on_c": None}, {"off_c": 59}])
def test_bad_config(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        fan.load_profile(path)


def test_good_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"on_c": 59, "off_c": 49}')
    profile = fan.load_profile(path)
    assert profile.on_c == 59
    assert profile.off_c == 49
    assert profile.interval_s == 0.5


def test_hysteresis_and_minimum_run():
    policy = fan.Policy(fan.Profile(), 0)
    for tick in range(30):
        assert policy.update(45, tick)
    assert not policy.update(45, 30)
    assert not policy.update(57.9, 31)
    assert policy.update(58, 32)
    assert policy.update(75, 33)
    assert policy.changed_at == 32
    for tick in range(34, 62):
        assert policy.update(49, tick)
    assert not policy.update(49, 62)


def test_cooling_must_stay_below_threshold():
    policy = fan.Policy(fan.Profile(min_on_s=10, cool_delay_s=5), 0)
    for tick in range(12):
        assert policy.update(52 if tick % 4 == 0 else 49, tick)
    for tick in range(12, 17):
        result = policy.update(49, tick)
    assert not result


@pytest.mark.parametrize("temperature", [-1, 111, float("nan"), float("inf")])
def test_invalid_temperature(temperature):
    with pytest.raises(ValueError):
        fan.Policy(fan.Profile(), 0).update(temperature, 0)


@pytest.mark.parametrize("now", [-1, 2.01, float("inf"), float("nan")])
def test_stale_or_reversed_clock(now):
    with pytest.raises(ValueError, match="deadline"):
        fan.Policy(fan.Profile(), 0).update(45, now)


def make_sensors(tmp_path):
    other = tmp_path / "hwmon0"
    other.mkdir()
    (other / "name").write_text("acpitz")
    hwmon = tmp_path / "hwmon1"
    hwmon.mkdir()
    (hwmon / "name").write_text("coretemp\n")
    paths = [hwmon / f"temp{i}_input" for i in range(1, 6)]
    for i, path in enumerate(paths):
        path.write_text(str(45000 + i * 1000))
    return paths


def test_sensor_discovery_and_maximum(tmp_path):
    paths = make_sensors(tmp_path)
    assert fan.discover_cpu(tmp_path) == paths
    assert fan.read_cpu(paths) == 49
    paths[-1].write_text("111000")
    with pytest.raises(ValueError):
        fan.read_cpu(paths)
    paths[-1].unlink()
    with pytest.raises(OSError):
        fan.read_cpu(paths)
    with pytest.raises(ValueError):
        fan.discover_cpu(tmp_path)
    with pytest.raises(ValueError):
        fan.read_cpu(paths[:2])


def test_missing_cpu(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        fan.discover_cpu(tmp_path)


def good_status(on=1):
    return {
        "control_enabled": 1,
        "fault": "none",
        "gpio_raw": 0x44000200 | on,
        "fan_on": on,
    }


@pytest.mark.parametrize(
    "status",
    [
        [],
        {},
        {**good_status(), "control_enabled": 0},
        {**good_status(), "fault": "lease_expired"},
        {**good_status(), "gpio_raw": 9},
    ],
)
def test_device_rejects_bad_status(tmp_path, status):
    (tmp_path / "status").write_text(json.dumps(status))
    with pytest.raises(ValueError):
        fan.Device(tmp_path).status()


def test_device_and_state(tmp_path):
    (tmp_path / "status").write_text(json.dumps(good_status()))
    device = fan.Device(tmp_path)
    assert device.status() == good_status()
    device.command(True)
    assert (tmp_path / "command").read_text() == "on\n"
    device.command(False)
    assert (tmp_path / "command").read_text() == "off\n"
    fan.write_state(tmp_path / "state.json", {"fan_on": True})
    assert json.loads((tmp_path / "state.json").read_text()) == {"fan_on": True}
    assert not (tmp_path / "state.tmp").exists()


class FakeDevice(fan.Device):
    def __init__(self, mismatch=False):
        self.commands = []
        self.on = True
        self.mismatch = mismatch

    def command(self, on):
        self.on = on
        self.commands.append(on)

    def status(self):
        return good_status(int(not self.on if self.mismatch else self.on))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_loop_transitions_and_shutdown(tmp_path):
    sensors = make_sensors(tmp_path)
    device = FakeDevice()
    clock = FakeClock()
    fan.run(
        fan.Profile(),
        device,
        sensors,
        tmp_path / "state.json",
        lambda: clock.now >= 34,
        clock,
        clock.sleep,
    )
    assert device.commands[0] and device.commands[-1]
    assert False in device.commands
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["temperature_c"] == 49
    assert state["fan_on"] is False


def test_mismatch_restores_full_on(tmp_path):
    device = FakeDevice(mismatch=True)
    with pytest.raises(ValueError, match="differs"):
        fan.run(
            fan.Profile(),
            device,
            make_sensors(tmp_path),
            tmp_path / "state.json",
            lambda: False,
        )
    assert device.commands[-1] is True


def test_sensor_failure_restores_full_on(tmp_path):
    device = FakeDevice()
    sensors = make_sensors(tmp_path)
    sensors[-1].unlink()
    with pytest.raises(OSError):
        fan.run(fan.Profile(), device, sensors, tmp_path / "state.json", lambda: False)
    assert device.commands[-1] is True


def test_main_config_check_and_error(tmp_path, capsys):
    config = tmp_path / "config.json"
    config.write_text("{}")
    assert fan.main(["--config", str(config), "--check-config"]) == 0
    assert '"on_c": 58.0' in capsys.readouterr().out
    config.unlink()
    assert fan.main(["--config", str(config)]) == 1


def test_main_signal_and_run(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text("{}")
    callbacks = {}
    monkeypatch.setattr(
        fan.signal, "signal", lambda sig, callback: callbacks.update({sig: callback})
    )
    monkeypatch.setattr(fan, "discover_cpu", lambda: [])

    def fake_run(profile, device, sensors, state_path, stopped):
        assert not stopped()
        callbacks[signal.SIGTERM](signal.SIGTERM, None)
        assert stopped()

    monkeypatch.setattr(fan, "run", fake_run)
    assert fan.main(["--config", str(config)]) == 0
