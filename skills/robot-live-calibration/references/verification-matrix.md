# Reproducible verification matrix

| Area | Positive control | Negative control / evidence |
|---|---|---|
| Passive startup | status without port open | constructor/GET have zero transport calls |
| Read lifecycle | finite session logs metadata/frame/end | busy owner preserved, cancel pending not closed, finally close |
| Contract | real exported record conforms to schema | unsupported version, bool/string count, duplicate ID, missing motor |
| Pose conversion | known counts/signs on compiled model | wrong sign, mismatched baseline, wrap boundary, revision mismatch |
| Calibration | explicit physical confirmation | unchecked flags, import from other model, synthetic into hardware |
| Context | stable session/firmware/mode/offset/torque | each coordinate-system change invalidates, reconnect requires rebind |
| Freshness | timestamp with timezone within threshold | ended stream, old/future frame, stale metadata, faults/alerts |
| UI | raw counts before calibration; actual pose after | no pose update with missing input, manual slider disabled in live mode |
| Browser | decoded image and increasing frame_seq | console failures, disabled/invalid calibration, stop/stale status |
| Direction observation | known synthetic delta records one evidence file and consumes the baseline | unconfirmed start/change, torque on, session/metadata change, jitter-sized or half-turn delta, reused baseline, failed re-capture, partial or existing file |
| Bounded motion guard | listed writes to the one motor reach the recording port | other motor, broadcast, unlisted register/width/value, multi-motor/reboot/reset instructions, no envelope; torque-off still transmits after a refusal |
| Bounded motion run | fake servo converges, holds, returns, torque off, settings restored | precondition failure sends nothing; torque-on jump, wrong direction, stall timeout, other joint moving, fault, failed write and interrupt all end with torque off |

Distinguish independently observed real hardware values from known synthetic inputs. A synthetic conversion test proves adapter/model behavior, not the actual physical axis order or zero point.
Do not reuse saved logs as live input for acceptance. Data from a completed finite run remains useful for diagnostics and must be marked ended.
An HTTP bridge endpoint may use a new lifecycle envelope while retaining a versioned JSONL exchange contract; test both boundaries without adding fields to the old contract accidentally.
The sample project uses XL430 4096counts/turn and mode3 shortest wrap versus mode4 linear. These are model-specific adapter rules; read the target's official specification before adopting them elsewhere.

