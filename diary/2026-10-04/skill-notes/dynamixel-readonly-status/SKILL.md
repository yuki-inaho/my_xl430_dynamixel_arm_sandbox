---
name: dynamixel-readonly-status
description: Inspect and monitor the five-motor DYNAMIXEL arm on Ubuntu using PING, READ, and validated SYNC_READ only; save register snapshots and typed telemetry without changing settings or torque.
---

# DYNAMIXEL Read-Only Status

Use `/home/inaho-omen/Project/my_dynamixel_arm_sandbox` as the working directory.
Read its `AGENTS.md`, `README.md`, and `config/arm.toml`. Defaults are DXHUB E148,
Protocol 2.0, 1 Mbps, expected IDs 1..5, model 1060 (XL430-W250).

The user authorizes information reads only. The CLI allows unicast PING/READ and
SYNC_READ (0x82) only for address 64 length 7 and address 120 length 27, with valid
unique IDs. It checks outgoing bytes before transmitting. Never bypass this
guard or use movement/setup commands from the older sandbox or copied upstream
scripts. Even Torque OFF and LED changes are writes and are outside this workflow.
Do not instantiate `low_cost_robot.robot.Robot`: construction changes torque.
The only recorded write exception is the bounded ID3 opening command `arm-id3-open`
(see AGENTS.md and the `bounded-servo-motion` skill); it is not part of this skill.

Run shell commands with the user's required `rtk` prefix. Set the tool working
directory instead of chaining `cd` commands.

```bash
rtk proxy date --iso-8601=seconds
rtk proxy uv sync --locked
rtk proxy uv run arm-status ports
rtk proxy uv run arm-status status --scan --samples 3 --interval 0.25
rtk proxy uv run arm-status metadata
rtk proxy uv run arm-status watch --rate 20 --duration 5 --quiet
```

If code changed, run `rtk proxy uv run pytest` before hardware execution.
The CLI checks serial ownership and refuses a busy port. Report the owner and
leave Wizard/other processes running. Do not kill another process to free it.
Use the stable `/dev/serial/by-id/` path in the configuration. `ports` does not
open an interface. Changing `--baudrate` affects the host only, never the motors.

Reports are saved as time-stamped JSON and Markdown under `reports/`; the port
closes before snapshot files are written. Watch saves JSONL incrementally and emits
its EndEvent with port_closed=True only after the bus context closes. Errors and
interrupts also close the port. An aborted or failed output may lack EndEvent; do
not infer successful completion from file existence. Evidence used to authorize another
workflow also needs explicit `simulated=false` and a matching acquisition ID at the actual
acquisition boundary. Legacy nullable provenance may remain readable for diagnostics but is
not proof of hardware origin. A source field alone is not evidence against deliberate forgery;
retain the raw capture/hash, command and acquisition provenance. Exit
code 2 means incomplete inspection; inspect missing values and read errors before
making a diagnosis. Do not claim that absent values mean zero or torque OFF.

Use `watch` for finite live observations, `metadata --full` for all supported
registers, and `status` for a detailed snapshot. Metadata is read at startup and,
by default, every thirty seconds; `--metadata-every 0` disables periodic refresh.
Watch uses two ordinary Sync Read packets per frame, not Fast Sync Read or an
indirect-address setup. Current firmware 42/43 is not eligible for Fast Sync Read.
Report achieved Hz, missing frames, deadline misses, and read durations. The local
20 Hz measurement had no misses; requesting 50 Hz achieved only 25 Hz. Later runs showed
isolated SYNC_READ "no status packet" frames (about 0.5 %, up to 2 % after a motion
test) and 15.9 Hz in one 10 s run; report them as incomplete frames, never fill them,
and do not tune USB latency or return delay without a separate request. This is
best-effort sampling and does not guarantee simultaneous motor readings.
Use `--format jsonl` for structured stdout; diagnostics and summaries use stderr.
For changes to exchange types or transport, read
`docs/readonly-architecture.md`, regenerate the contract, and run quality gates.

Summarize detected IDs/models, firmware, torque, hardware errors, voltage,
temperature, signed position/velocity/PWM/load, position change across samples,
and communication settings. Inspect position limits, profiles, PWM/velocity
limits, gains, watchdog, and goal/current position difference in the report.
Version-gated registers are omitted when unsupported, even if a read of a reserved
address might return zero. Unsupported models get identity checks only.

Present Load on XL430 is estimated load, not measured current or torque. Encoder
angles are not calibrated joint angles. Sequential samples do not prove stability
under torque or load. A successful scan does not verify physical ID order or rule
out all duplicate-ID collisions. Profile Velocity/Acceleration=0 in velocity-based
profile mode does not establish gentle motion. Do not change these values here.
PING/READ traffic can refresh an enabled bus watchdog; do not promise that reads
will stop an already torque-enabled motor. Report observed torque without writing.

When checking the local HTTP bridge or viewer status from the shell, use
`rtk proxy curl ...`; the plain `rtk curl` rewrite reformats JSON and breaks parsers.
Starting a READ from the viewer opens the port; stop it (port_closed=true) before any
other tool needs the serial device.

Link the captured report and append relevant observations to `diary/`. Keep
observations separate from proposed joint roles and future movement prerequisites.
For interpretation, use the [official XL430 control table](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/).
