@/home/inaho-omen/.codex/RTK.md

# Arm Workspace

The project/distribution name is my-dynamixel-arm-sandbox; the Python import
package is `arm_observer` under `src/arm_observer`. Keep the `arm-status` CLI name.

The user currently authorizes motor information reads only. Use `arm-status` from
this project. Motor instructions are restricted to unicast Protocol 2.0 PING,
READ, and SYNC_READ (0x82) for the two validated telemetry blocks. Do not change
torque, goals, IDs, modes, LED, EEPROM, firmware, or reset the
motors. Do not import `low_cost_robot.robot.Robot` for inspection: its constructor
changes torque. The older sandbox's movement/setup commands are outside this scope.

One recorded exception (user instruction, 2026-10-03): the bounded ID3 elbow opening
of `temp/workdoc_Oct03-2026_id3_open_10deg.md` may run only through
`arm-id3-open --execute` (`id3_motion.py`, `motion_guard.py`). It writes ID3 RAM
registers 64/100/108/112/116 inside a per-run envelope, needs hardware direction
evidence, and ends with ID3 torque OFF. Run it only after the user confirms support
and the supply OUTPUT OFF stop are ready. All other commands keep the read-only guard;
do not widen the envelope, add motors or registers, or reuse it for other motions.

Check serial ownership before connecting. Leave DYNAMIXEL Wizard and unrelated
processes running; if they own the port, stop the hardware inspection and report
the owner. Close the port in a finally block, including on errors and interrupts.

Use `config/arm.toml` for the stable device path, baudrate and expected IDs.
Physical joint roles are proposed; do not infer verified physical order from ping.
Save time-stamped JSON and Markdown in `reports/` and work notes in `diary/`.

Before hardware execution after code changes, run the offline tests that check
outgoing protocol instructions. No hardware access is needed for `uv run pytest`.

Keep SDK transport in `bus.py`/`reader.py`; acquisition depends on the `Reader`
protocol. Use immutable typed records, not ad hoc dictionaries, for domain data.
JSON/TOML and schema generation may use dictionaries at serialization boundaries.
Missing values are None, never stale values or assumed zero. The JSONL exchange
contract is schema version 2; regenerate fixtures with `scripts/export_contract.py`
and test the Rust consumer when changing exchanged fields.

Use finite `watch` runs for agent checks. Report achieved rate and missed deadlines;
this is best-effort monitoring, not hard real-time control. Do not tune motor
return delays, indirect addresses, firmware, or host USB settings without a separate
request. Default watch is 20 Hz and ten seconds; metadata refresh is thirty seconds.

Quality gates: `uv run pytest`, `uv run ruff check src tests scripts`,
`uv run ty check`, `uv run scripts/check_quality.py`, and Cargo tests/Clippy in
`rust/arm-observer-contract`. Prefix shell commands with `rtk proxy`.
