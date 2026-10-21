# Tune the LarkBox Pro temperature policy

The confirmed hardware interface is **on/off**. A custom “fan curve” here means
choosing when to run and stop the fan, not selecting RPM or a PWM percentage.

Edit `/etc/larkbox-fan.json`, validate, then restart:

```sh
sudo cp /etc/larkbox-fan.json /etc/larkbox-fan.json.backup
sudoedit /etc/larkbox-fan.json
sudo /opt/larkbox-fan/venv/bin/python /opt/larkbox-fan/larkbox_fan.py \
  --config /etc/larkbox-fan.json --check-config
sudo systemctl restart larkbox-fan
journalctl -u larkbox-fan -f
```

| Key | Default | Allowed | Effect |
| --- | ---: | --- | --- |
| `on_c` | 58 | At least 5 above `off_c`; at most 59 | Immediately start full cooling at this hottest-core/package temperature |
| `off_c` | 50 | 40 or above | Allow the fan to stop after stable cooling below this value |
| `min_on_s` | 30 | 10–300 seconds | Minimum continuous run time once the fan starts |
| `cool_delay_s` | 10 | 2–60 seconds | How long temperature must remain at/below `off_c` before stopping |
| `interval_s` | 0.5 | 0.25–0.75 seconds | Temperature sampling and kernel off-lease renewal interval |

The service starts with full cooling. Temperature reaching `on_c` turns it on
without delay. Stopping needs both minimum on time and a complete cooling delay.
There is no minimum-off timer that could delay required cooling. CPU Turbo and
power limits are unchanged.

For more conservative cooling, try `on_c: 55`, `off_c: 47` with other defaults.
For fewer starts/stops, lower `off_c` or increase `min_on_s`; that makes each
cooling run longer. Raising `on_c` can lengthen quiet intervals but raises peak
temperature. Keep airflow unobstructed and measure on your actual machine.
There is no universal optimum for every room, placement and workload.

The service reads the hottest of package plus all four core sensors. Missing or
invalid readings, delayed loops or kernel faults stop it and request full-on.
The kernel's fixed 60°C off-admission limit, 65°C emergency limit and three-second
lease cannot be relaxed in the JSON file. The service does not restart itself
after a fault; inspect the journal before restarting it.

## Measure sound without saving recordings

With an Anker PowerConf C200 microphone connected:

```sh
sudo apt install alsa-utils build-essential
sudo amixer -c C200 contents
sudo ./scripts/measure-noise.sh 15
```

Keep microphone position, gain and room noise constant. The tool reports
DC-removed, unweighted **dBFS**, not calibrated dBA or sound-pressure level. It
retains statistics only. Internal webcam processing may affect measurements.
For another microphone, change the ALSA device in the script after identifying
it with `arecord -l`.

The GPIO readback confirms the requested output, not fan RPM or physical rotation.
Check that the fan really runs when commanded, and watch CPU temperature.

## Restore the previous configuration

```sh
sudo cp /etc/larkbox-fan.json.backup /etc/larkbox-fan.json
sudo systemctl restart larkbox-fan
```

To leave the fan running continuously for investigation:

```sh
sudo systemctl stop larkbox-fan
printf 'on\n' | sudo tee /sys/kernel/larkbox_fan/command
```

Resume the configured policy with `sudo systemctl start larkbox-fan`.
