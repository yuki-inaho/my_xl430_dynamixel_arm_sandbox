# Random XY cap-grasp study — 2026-10-05/06

This extension uses the existing nominal R3 arm / C7 jaw / D405 holder model,
preserved scan-fit source shapes, collision proxies and acceptance contract.
It performs offline dynamics only. Its common experimental standby (four arm
coordinates zero, jaw 50°) is not a calibrated real-robot standby.

## Recorded result

`results/qualification-002/index.json`: 100/100 successes, unsafe 0, invalid 0.
`evidence/independent-qualification-002.json`: independent audit PASS over all
100 full traces, selection order and 1,386 frozen inputs/source files.
Each trial lasts 23 simulated seconds at 1 ms: 2,300,100 saved samples in total.
Wall time: 1,186.24 s with four workers. Seed: 91021261008.
335 XY proposals yielded the first 100 pre-screened candidates; 235 endpoint-IK
rejections remain in the selection record. Wilson 95% interval: [0.9630065, 1].
This describes the selected batch under the fixed model/screen, not a general
physical success rate or confirmatory coverage after development.

The earlier `qualification-001` remains INCOMPLETE: 96 successes, one actual
NO_GRIP failure and three invalid interrupted traces, all in the 100-target
denominator. Those three were not replaced. Its saved pre-change source snapshot
is historical evidence; comparing it to today's changed runtime should fail.
The original supplier's 100 qualification raw traces were not in the received
report ZIP; supplier results remain unverified and separate from these fresh runs.

**Descent limitation:** 97/100 new trials lose simultaneous finger contact during
lowering; 89 do so before first box contact. Maximum pre-box cap-center speed is
0.69846 m/s. The longest absence is 2.169 s including time after landing, not an
airborne-duration measurement. Passing grasp/hold and final placement does not
establish continuous retention or gentle placement during descent.

## Reproduce / inspect

Run from this directory. Use Python 3.12 and the bundled `uv.lock`. Runtime pins
are in `pyproject.toml`; the freeze records actual interpreter/library versions.
External tools: zstd for lossless contact logs; ffmpeg for evidence videos.
No serial device, physical camera or motor command is used.

This GitHub snapshot includes the runtime, tests, technical review, trial/proposal
CSVs and three representative synthetic images. The base repository supplies the
model, input assets and locked environment. Full saved states, contact logs,
source freezes and the full interactive report remain in a separately verified
local integration bundle (SHA256 in PUBLICATION.md); they are not included here.
Consequently the recorded audit cannot be rerun from this reduced snapshot alone.
PUBLICATION_SHA256SUMS lists only the files actually added/updated for publication.
Use `sha256sum -c PUBLICATION_SHA256SUMS` from this directory to verify them.
The older nominal SHA256SUMS is refreshed for the contact-reader merge.

For a fresh qualification, choose a new output name and declared seed. Existing
outputs are intentionally preserved. Freeze first, then execute exactly that name
and seed; keep rejected proposals and all selected targets regardless of result.

```bash
uv run --no-sync python random_study.py --mode freeze \
  --name qualification-replay --seed 91021261008
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  timeout --signal=INT --kill-after=20s 1800s \
  uv run --no-sync python random_study.py --mode qualification \
    --name qualification-replay --seed 91021261008 --workers 4
uv run --no-sync python random_study.py --mode audit-batch \
  --name qualification-replay --workers 4 \
  --output evidence/independent-qualification-replay.json
```

Native-library/platform changes can prevent bit-identical replay. Do not widen
thresholds to hide differences. Inspect actual physics and independent audit.
The current implementation produces bit-identical representative states/contacts
to the prior loop in the recorded environment and to its repeat. Its one-forward
implicitfast pipeline also matches standard `mj_step` bit-for-bit in a separate
200-step contact-bearing control. It never substitutes `mj_step2`/Euler.

After a fresh run, `random_report.py --name qualification-replay` renders saved
qpos and creates the full HTML report. Rendering is not a physics rerun. For the
recorded technical summary and selected images, open PUBLIC_REVIEW.html through
a local HTTP server. CSVs retain all 100 selected trials and all 335 proposals.
Raw contact readers support exactly one plain/gzip/zstd representation and check
lossless restoration metadata; no raw traces are distributed in this snapshot.

Some inherited development/diagnostic entry points refer to the supplier's
unbundled `development-002` or `dev-center-v2`. They are not evidence for this
qualification. Use the explicit audit-batch and saved new results above.

## Fixed assumptions

- Uniform proposed XY in ±300 mm; fixed cap center z=57.5 mm and pitch −50°.
  The original 64 mm support box translates with each target. Axisymmetric cap
  yaw is fixed; this is not arbitrary-orientation coverage.
- Cap radius 14 mm, height 15 mm, mass 1.5 g, friction 0.7. Newton/elliptic,
  implicitfast, 1 ms. No physical material calibration is claimed.
- Analytic IK plus finite sampled paths before dynamics. Static acceptance is
  not dynamic feasibility or a proof of continuous collision avoidance.
- Four arm coordinates and one jaw actuator. Free cap with no hidden support,
  no runtime cap pose overwrite and no external-force assistance.
- Hold gate: lift ≥20 mm, duration ≥2 s, bilateral contact ≥80%, drift ≤5 mm;
  safety policy over the recorded cycle plus final release/placement/standby.
  Full return conditions and ≥95/100, unsafe 0 are in `protocol.json`.
- Setdown uses perfect simulated cap pose/contact feedback to latch descent;
  this is not a deployed real-camera estimator. Whole-body collision exemptions,
  uncalibrated proxies, cables and material uncertainty limit physical conclusions.

No archives, real photos, conversation logs or machine-specific absolute paths
are part of this technical report. Input originals and corrupt interruption
diagnostics stay local. Publication scope and integration history are recorded in PUBLICATION.md.
