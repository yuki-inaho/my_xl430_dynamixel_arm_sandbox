# Findings, tips and struggles (ID3 elbow opening, 2026-10-03/04)

Concrete evidence lives in `diary/2026-10-04_id3-open-10deg.md` and
`temp/workdoc_Oct03-2026_id3_open_10deg.md`.

## Findings on hardware (5x XL430-W250, FW 42/43, 1 Mbps, E148 hub)

- The elbow opened in the CAD-predicted direction (counts increase). Holding the opened pose
  needed about 100-120 PWM (11-14 %); returning needed almost none, so gravity pulls toward the
  fold. Load behaviour is useful direction evidence when nobody can watch.
- Default gains (P 640, I 0) left a 19-count (1.7 deg) sag on the first run. One goal offset of
  +20 counts brought it to -4 counts. Gains were not changed.
- Breaking away from the folded rest briefly reached the 350 Goal PWM limit (static friction).
- Isolated SYNC_READ "no status packet" frames occur (about 0.5 %, up to 2 % after motion);
  the achieved rate fell from 19.9 to 15.9 Hz in one read-only run. Treat unknown samples as
  unknown and allow an isolated retry.

## Defects found by adversarial review before the first write

Each was reproduced offline, fixed test-first, and is now covered by tests.

- The SDK sets `is_using` in txPacket and clears it only at the end of rxPacket. An exception
  inside a transaction (guard refusal, KeyboardInterrupt, serial error) left it set, so every
  release write returned "port busy" and torque stayed on while the tool said it was off.
- Logging before sending meant a disk-full log error skipped Torque=0.
- Release restored PWM and profile limits to "unlimited" even when Torque=0 had not been
  confirmed, and the outcome did not report the failure.
- SIGTERM/SIGHUP skipped release entirely. A later design that raised KeyboardInterrupt from
  handlers still had windows at function entry and while restoring handlers; record-only
  handlers that the CLI never restores closed them.
- Pacing advanced the deadline twice (10 Hz instead of 20 Hz).
- Evidence parsing accepted a sign inconsistent with the recorded counts, bool signs, other
  sessions, and hand-written CAD records with unverifiable source hashes.
- After the verdict: a log close re-raised ENOSPC (exit 1), an unflushed stdout made the
  interpreter exit 120, and a signal right after handler restoration printed "interrupted
  before any write".

## Tips

- Fakes must model time-based profiles: a blocked joint ends its trajectory after its
  duration, it does not stay "profile ongoing" forever. Otherwise convergence tests lie.
- Shorten the guard window to what the code writes (fold side: jump tolerance; opening side:
  target plus correction budget), and judge overshoot against the true target even when the
  goal is offset.
- Strengthen negative tests with `match=` per gate and run mutants (remove a gate, check that
  a test fails); a new threshold can silently make old negative cases pass for the wrong reason.
- `rtk curl` reformats JSON; use `rtk proxy curl` when piping to a parser.
- Viewer HTML may be read per request, but server-side Python changes need a restart; check
  the port owner and that no user session is mid-operation before restarting.
- Unattended runs: record that the power-off stop is not available, keep the run finite, read
  back torque state with the monitor afterwards, and report exactly what was not observed.
