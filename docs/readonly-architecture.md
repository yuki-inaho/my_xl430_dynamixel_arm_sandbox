# Typed Read-Only Observation

The Python package lives in `src/arm_observer` and is imported as `arm_observer`.
The workspace/distribution name and `arm-status` command are unchanged.

## Boundaries

`models.py` owns immutable records. `Reader Protocol` exposes only identity,
registers, and telemetry. `SdkReader` adapts the official SDK. `observer.py`
depends on this interface, not Linux, serial details, or SDK classes. The CLI
owns the port lifetime; acquisition services do not claim to close a port.
Diagnostics are pure functions, and output serializes records at the boundary.
No generic command bus, plugin framework, or write-capable control interface is
introduced before there is a concrete need for it.

Frozen dataclasses map naturally to Rust structs; NamedTuple represents small
read results. Optional values map to Rust Option and JSON null. Units are explicit:
encoder counts, signed velocity/PWM/estimated load raw values, voltage in tenths
of a volt. Numerical conversions require calibrated zeros, directions and ratios.
Do not treat a converted encoder angle as a verified physical joint angle.

## Transport and Failure

The guard permits only PING, scalar READ, and ordinary SYNC_READ for two fixed
blocks: 64..70 and 120..146. Writes, setup, reboot/reset, Fast/Bulk operations,
and arbitrary ranges are rejected before serial transmission. There is no
indirect-address configuration or firmware upgrade in this workflow.

Each cycle resets the SDK GroupSyncRead validity flag and receipt cache. The
SDK's per-motor error byte is retained by ReceiptPacket. Failed or truncated
responses become explicit faults and unknown values, not zero or reused data.
On a group transport failure all values of that block are treated as unknown,
even when some replies arrived. Status Alert is retained separately from invalid
lower error bits and hardware error masks.

Port ownership is checked with fuser, then pyserial exclusive/TIOCEXCL is set.
This is a cooperative single-owner mechanism, not a security boundary against
privileged programs or another already-open descriptor. The context manager
closes the serial device on normal completion, exceptions and interrupts.
Existing Wizard sessions are never killed. Read-only traffic can still refresh
an enabled Bus Watchdog; it is not an emergency-stop mechanism.

## Cadence and Stream

Monotonic deadlines schedule observations; overruns skip missed slots rather
than produce catch-up bursts. Wall-clock strings make logs readable; monotonic
nanoseconds, duration and sequence make timing analysis reproducible. The reported
rate is calculated from frame-start intervals. It is not a hard real-time promise.
Duration bounds stop the scheduling of new frames, not an in-progress serial read.
Metadata retrieval and callback/file-output latency can cause additional delays.

Metadata is cached and optionally refreshed at a slower rate than telemetry.
The default is essential metadata, while snapshots read all firmware-supported
registers. Two block reads per frame do not establish simultaneous measurements.
Consumer code should inspect faults, Alert and hardware error as well as nulls;
a complete frame means data was received, not that motion is safe.

JSONL records are emitted and flushed one at a time. The watcher keeps no full
history in memory. Every record includes kind and schema_version=2. EndEvent
has port_closed=True only after the bus context has closed. On output failures
or interrupted initial metadata acquisition a stream may end without EndEvent.
Do not confuse an existing log file with a successfully completed inspection.

## Portability and Quality

`contracts.py` reflects Python records to JSON Schema and sets integer bounds
matching the Rust widths. Generated signed/null fixtures are tested in both
languages. Rust Serde structs implement the exchange contract; the example reads
stdin without hardware access. The Rust decoder rejects unknown schema versions
and fields but is not a full JSON Schema validator. Calibration and configuration
validation remain separate from structural decoding.

beartype checks record/service runtime types; it is not a substitute for value
validation and does not exhaustively check every container member. Configuration
IDs and polling options have explicit validation. jaxtyping checks dtype/shape at
numerical boundaries. ty checks maintained source/scripts; pytest tests transport
guards, signed values, missing values, stale-cache prevention and schema fixtures.
Radon enforces maximum complexity 10 in maintained src; imported upstream code
is isolated and not declared to pass these gates. Cargo tests and Clippy cover
the Rust consumer. Follow the commands in README after changing the contract.

## Primary Sources

- [ROBOTIS Sync Read tutorial](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/sync_read_write_tutorial/sync_read_write_tutorial_python/): GroupSyncRead is the existing SDK mechanism used here. Do not execute its write examples in this project.
- [ROBOTIS Protocol 2.0](https://emanual.robotis.com/docs/en/dxl/protocol2/#sync-read-0x82): ordinary Sync Read reads a common address/length across IDs. Fast Sync Read requires X430/540 firmware 45+, so the observed 42/43 motors use ordinary Sync Read.
- [XL430 control table](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/): addresses, units, firmware-gated registers and the distinction between estimated load and measured current.
- [beartype decorators](https://beartype.readthedocs.io/en/latest/api_decor/): runtime checks; the class decorator is outside dataclass so generated methods are available to it.
- [jaxtyping runtime checks](https://docs.kidger.site/jaxtyping/api/runtime-type-checking/): jaxtyped(typechecker=beartype) enforces shared dimension bindings. The numerical module keeps runtime-visible annotations.
- [ty type checking](https://docs.astral.sh/ty/type-checking/): static checks complement runtime checks.
- [Radon API](https://radon.readthedocs.io/en/stable/api.html): cc_visit/cc_rank and mi_visit drive the local complexity report.
- [Serde JSON](https://serde.rs/json.html): derived Serialize/Deserialize for Rust structs and enums.

The module boundaries, two-block strategy, error handling and 20 Hz default are
local engineering choices, informed by these sources and the measurements below;
they are not claimed to be vendor-required architecture.
