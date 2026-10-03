# Lessons: building & using this skill (struggles / findings / tips / improvements)

Captured from the first real run (XL330→XL430 impact on low_cost_robot) so the
skill keeps improving itself.

## Struggles (what bit us)

1. **Python/OCP wheels.** CadQuery's OCP has no cp3.13 wheels; the host project
   env was 3.13. Fix: pin this skill to `>=3.11,<3.13` (`.python-version` 3.12).
   Lesson: a portable CAD skill must pin Python, not inherit the caller's.
2. **Hidden runtime dep.** `trimesh.nearest.on_surface` needs `rtree`, not pulled
   in by `trimesh` core — equivalence crashed only at call time. Declare it.
3. **B-rep grouping is deceptively hard.** First version grouped cylinders by
   `(radius, raw_axis_dir)` and reported face counts as hole counts. Wrong on two
   axes: (a) the B-rep axis sign is arbitrary → one bolt circle can split in two;
   (b) a through-hole becomes several collinear faces → counts inflate (verified:
   `elbow_to_wrist` d=2.0 → 8 faces but 4 axis lines). Adversarial review caught it.
4. **Spec drift.** Hard-coded values were off: XL330 stall torque 0.42 (correct
   0.52 N·m @5V), XL430 mount screw "M2.5" (case mounting is **M2**; M2.5 is the
   frame/horn kit), XL430 torque 1.5 (that's @12V; @11.1V nominal it's 1.4).
5. **Wrong metric for the shape.** "Does the servo fit *inside* the part bbox" is
   ~always False for open brackets and is NOT the swap criterion — confusing until
   reframed as an enclosure-only signal.
6. **Layering crept.** First cut mixed generic probing with servo specifics in
   flat scripts; had to refactor into `cadre` core + `studies/` after the
   generic-first instruction. Cheaper to separate from the start.

## Findings (what's true about this data)

- STEP is plain text: `PRODUCT(...)`, keyword hits and `CYLINDRICAL_SURFACE`
  radii are greppable with no CAD kernel. This alone confirmed the key fact —
  `follower/shoulder_to_elbow.step` PRODUCT name is literally
  `XL430 to XL330 new connector` — making it the unique **direct**-impact part.
- B-rep radii/axes/centers are exact and reproducible (re-run matched byte-for-byte).
  The trustworthy invariant is the **axis line**, not a "hole count".
- Same-named parts differ: follower vs leader `shoulder_to_elbow.step` are
  different geometries (44×132×26 "connector" vs 15.6×35×120 "Servo Connector
  redesign"). Never reason by filename alone — use path + PRODUCT + bbox.
- Envelope grows ×1.3–1.4/axis (+8…+12.5 mm); mass ×3.18; the height +12.5 mm is
  the tightest constraint on short links.

## Tips (what worked, reuse these)

- **3-tier triage**: text (free) → mesh (cheap) → B-rep (kernel). Classify
  hundreds of files by text first; only B-rep the suspects.
- **Equivalence on the mesh**, not exact B-rep equality: bbox + sampled surface
  distance + volume is robust to remeshing/tessellation and answers the real
  question (same space within print tolerance).
- **Inject the domain**: keyword policy + classifier + specs live in the study,
  never in `cadre`. Same primitives emit XL330 *or* XL430 by swapping a `Component`
  (proven: 29×54.5×39 vs 37.5×68.75×51.5).
- **Adversarially verify** your own extraction (independent re-run + skeptical
  reading). It found a real bug and three spec errors here — highest ROI step.

## Design-intent layer (added after the advisory review)

The robust methodology is **semi-automatic refactoring**, framed like an
autoencoder but with a *human-readable* latent: B-rep extraction → a YAML
design-intent graph (`cadre.intent.PartIntent`) → CadQuery reconstruction →
TDD diff/function checks (`cadre.checks`). LLMs label *intent* from a structured
descriptor (`cadre.descriptor`), never from raw STEP. See `research_context.md`
for the related work (DeepCAD, CAD-Recode, UV-Net, SolidGen, Vitruvion, …) and
why fully-automatic STEP→clean-parametric is still hard (intent isn't in the
geometry; constraints are hard; B-rep topology is unstable).

## Session 2 (browser viewing + placement verification)

Struggles → fixes that became skill features:
- **Canonical centers lose absolute position.** The M-1 perp-foot fix made
  `hole_families.centers` great for *matching* but unable to answer "is this bolt
  hole on the frame / where is it?" — I had to write a throwaway script. Fixed by
  adding `cylinder_faces()` + `cadre.cli inspect`: bbox min/max + every face's
  ABSOLUTE center + the family summary. Verified on the real connector
  (M2 cross at ±8 around the φ10 bore inside the φ26 horn seat, on the wall ring).
- **No B-rep integration test.** Added one: generate a holed plate → recover the
  4 holes' absolute centers. Closes the long-standing gap.
- **chili3d exposes no JS app handle** (`window` has no app/view) — 3D geometry is
  canvas/WASM, not DOM. So geometry questions must go through B-rep on the STEP,
  not the browser; the DOM only yields the part-name tree.
- **playwright-cli `eval` misparses `=>`** — wrap as `() => (...)`. Documented in
  `chili3d_viewing.md`.
- **playwright-cli sessions collide across projects** (a shared `default` picked up
  another project's `sam2-cvat` profile). Use a dedicated `-s=<name>` session.
- **Visual verification recipe that worked:** load the *isolated* part (not the
  assembly — neighbours occlude + wireframe see-through confuses), snap to an axis
  via the gizmo, screenshot, and cross-check the circles/holes against
  `cadre.cli inspect` numbers. A "counterbore that looks clipped" was just the
  φ26 seat spanning the full 26 mm thickness + Solid+Wireframe see-through — not a
  defect.

## Session 3 (agent-team workdoc execution: XL430 migration)

Run via start-work-audit-pattern (coordinator + persistent worker + auditor) against the
XL430 migration workdoc. Findings worth feeding back into the skills:
- **F-1 (`check_simulation.py --json`)**: numpy scalar comparisons (`x <= LIMIT`) yield
  `numpy.bool_`, which `json.dumps` rejects (`TypeError: ... bool not serializable`; the name
  reads as plain "bool" in numpy 2.x, misleading). FIX/RULE: any JSON-emitting tool must pass
  `json.dumps(..., default=lambda o: o.item() if hasattr(o,"item") else str(o))`. Consider
  baking this into a `cadre` JSON helper so new tools inherit it.
- **F-5 (intent vs reality drift)**: a `<part>.yaml` declared `motor_body_bore.through: true`
  while the implementation/`inspect` showed a blind 3 mm counterbore (φ26 = 2 wall faces, φ10
  single axis). The C-B8 through/blind *declaration* must be cross-checked against the built
  geometry — a declaration the part doesn't honour is worse than none. TIP: add an automated
  check that the YAML `through` flag matches the recovered axes/faces topology.
- **C-A2 is the right gate for organic parts; C-A1 is not.** Mesh-distance equivalence (C-A1)
  fails on Fusion-organic originals (surface max ~19 mm here) AND `volume_delta` is `None`
  because the shipped `hardware/follower/stl/*.stl` are **non-watertight**. Feature-level
  equivalence (C-A2: hole families, dia Δ, center NN) passed exactly (NN=0.0). RULE: gate on
  C-A2; document the C-A1 gap; don't trust volume on these STLs (repair or compare STEP).
- **C-A2 compares the in-plane pattern only** (families keyed by radius+axis-dir; axial
  position is NOT compared — that belongs to C-B5/C-B7). State this in any equivalence report
  so "NN=0" is not over-read as full 3D coincidence.
- **Counterbore modeling**: a φ26 seat tangent to a wall edge produces a degenerate
  (non-manifold) mesh; give the wall ≥ seat+6 mm. And a seat depth (3 mm) into a thin wall
  (4 mm) leaves 1 mm floor < typical 2.5 mm min-wall — counterbore depth must be checked
  against wall thickness (manufacturability).
- **Tip (agent team)**: persistent subagents are resumed by **agentId** (from the spawn
  result), not by the `name=` — SendMessage to the name fails once the task completes.
- **F-6 (silent no-op on resume)**: a SendMessage to a persistent auditor returned
  "resumed in background" but produced **no output** (its transcript stayed at the
  previous task). Before depending on a delegated result, **verify progress** (output
  file mtime / last event); on a silent no-op, do NOT wait implicitly — run the check
  directly and record the delegation failure explicitly. Coverage rule that worked:
  spend the auditor's independent eye on *substantive* artifacts (the 2 real swaps +
  the regression); peripheral NO-OP / not-applicable parts can be coordinator-verified
  (tests + md5 identity) when delegation is flaky.
- **Section measurement is a bug detector.** The cq `section()`/BREP ray measurement done
  "merely" to confirm the C-B4 floor (workdoc_Jun12 completion pass) exposed two REAL
  implementation bugs in `shoulder_to_elbow.py`: a sign error in the wall placement
  (`sx*wx - sx*wall_t/2` put the -X wall at x=-13.5 instead of the symmetric ±19, leaving
  its φ26 seat ~outside the material) and the counterbore being cut from a nominal plane
  rather than each wall's actual outer face. RULE: actually *measuring* a dimensional DoD
  (instead of trusting the parameter arithmetic, wall−depth=floor) is implementation
  verification, not box-ticking — budget for it on every min-wall / seat-depth claim.

## Session 4 (failure lesson: destructive local optimization)

The `elbow_to_wrist_extension` circular-flange iteration exposed a more important
process bug than any single CAD bug:

- **A local design hint is not a license to redesign the part.** The user noticed
  that four servo fastening holes looked too close to the edge and suggested a
  rounder/circular flange-like boundary. That idea was partly valid: local
  rounding or local reinforcement around the bolt pattern could improve edge
  distance and stress flow. The failure was turning that local hint into a large
  circular collar that replaced the original end profile.
- **The wrong DoD made a bad design look successful.** The tests proved
  min-wall, no assembly intersection, hole-family preservation, and pytest
  green. Those gates were necessary but incomplete. They did not prove that the
  original outline, asymmetry, fork/ear shape, partial reliefs, and neighboring
  clearances were preserved. Because "preserve original shape outside the change
  mask" was missing, agents reported "done" for a destructive local optimum.
- **Auditors can only audit the criteria they are given.** Worker/auditor prompts
  focused on circular collar clearance and edge distance. They did not require
  same-camera X/Y/Z screenshots of original vs candidate or a change-mask
  surface-difference gate. The audit therefore validated the wrong problem.
- **For historyless organic STEP, full re-CAD is the fallback of last resort, not
  the default.** If an equivalent Stage-1 reconstruction cannot preserve the
  original, switch to local B-rep editing or stop. Do not keep refining a clean
  parametric simplification until local tests pass.

Rule to reuse: before changing geometry, write the user's real objective, the
allowed change mask, and the preserve-by-default regions. Then make
original-shape preservation the first gate. A candidate that passes min-wall and
interference but changes the non-target outline is a failure.

## Session 5 (print packaging + fail-closed gates, 2026-09-19)

Two received ZIPs (mixed-servo follower revision, all-XL430 static replacement)
and the OrcaSlicer packaging work exposed gate design rules worth reusing:

- **A pass report from the wrong baseline is worse than no report.** The received
  all-XL430 ZIP carried "0 interference" evidence produced on the *mixed* baseline
  before the 4 motor substitutions. Re-importing the converted 217-leaf STEP found
  **54 external intersections** (largest ~9,608.8 mm³). Bind every verdict to the
  candidate revision (hash the exported STEP + manifest + all parts) and re-run the
  scan on the converted assembly itself.
- **Same-motor internal overlaps need a separate bucket, not an exclusion flag.**
  Reference motor shapes overlap themselves (168 pairs here). Classify by physical
  unit derived from the source assembly paths; only "same named supplier motor
  unit" is internal, and no caller flag may exclude an external pair.
- **Fail-closed gate checklist that worked** (reuse for future print gates):
  re-validate on every package command (never trust archived JSON); require
  `boolean_attempted_pairs == boolean_candidate_pairs`; require
  `external_collision_count == len(external_collisions)`; verify leaf count and
  motor occurrence count; require same-revision evidence (candidate hash) for
  every pending engineering check; no `--force`/skip switch; refuse an existing
  output path and any output inside the diagnostic quarantine.
- **Size the timeout to the measured scan, and keep timeout fail-closed.** The
  151-solid / 381-pair B-rep scan measured ~11 min; a 600 s worker timeout turned
  a nearly finished scan (350/381, 54 hits) into a blocking error. Fixed at 1800 s;
  a timeout still blocks the print. Measure heavy gates and encode the budget.
- **One gate, one implementation.** The study's `prepare_print_package.py` became
  a thin wrapper over `study.py print-package`; duplicated gate logic is where
  drift and bypasses appear.
- **Process-isolate OCP/CadQuery.** Generating + validating heavy XCAF studies in
  the pytest process segfaulted when another study loaded a second STEP; one
  worker subprocess per operation fixed it.
- **Testability without weakening production paths.** `study_run(root=...)` and
  `check_reference_hashes(manifest_path=..., reference_dir=...)` let tests exercise
  symlink/traversal/quarantine rules while production defaults stay fixed; reference
  resolution must reject paths escaping the reference dir.
- **Multi-plate slicing is the default for 7 parts.** Validate every
  `plate_N.gcode` (part counts, warnings, macros, `M191`), not just `plate_1`; a
  helper that only checked `plate_1` mislabeled a successful 2-plate slice as failed.

## Session 6 (Ender-3 Pro headless CLI slice, 2026-09-22)

The first non-BBL printer job (stock Creality Ender-3 Pro, microSD delivery)
showed that the OrcaSlicer CLI is not the GUI preset system:

- **`--load-settings`/`--load-filaments` do not resolve `inherits`.** Passing an
  extracted system preset slices with C++ defaults for every inherited key. The
  relative-E default is `true`, so the missing inherited `before_layer_change_gcode`
  failed validation with exit -51 (`Add "G92 E0" to layer_gcode`).
- **The CLI loader demands preset metadata.** A flat JSON without `from`
  (`system`/`User`/`user`) dies with `from unsupported` before slicing; `type`
  and `name` are read too. Keep them while dropping `inherits`/`setting_id`.
- **`compatible_printers` is a hard gate in the CLI.** The process preset list
  must contain the machine preset name, or slicing exits -17 ("selected printer
  is not compatible with the process preset").
- **Offscreen slicing needs no xvfb** for this job (`QT_QPA_PLATFORM=offscreen`);
  keep `xvfb-run` for flows that genuinely need a display.
- **Validate the destination medium, not just the file.** Compare `sha256sum` of
  source and SD copy, then sync before removal. Keep the card's old G-code and
  `EEPROM.DAT` untouched.
- Reusable resolver: `cadre.orca_presets` (`python -m cadre.orca_presets ...`)
  with `tests/test_orca_presets.py`; procedure documented in
  `references/orca-headless-cli.md`.

## Improvement backlog (next iterations)

- [x] Design-intent layer + functional checks + LLM descriptor (intent/checks/descriptor).
- [x] `make_connector(upstream, downstream)` — equivalent-shape then swap, one arg.
- [ ] Resolve through-hole vs coaxial-blind ambiguity by ray-casting the axis
      against solid walls (count boundary crossings) → true physical hole count.
- [ ] Independent 2D cross-check: reuse the sandbox `export_dxf` + `parse_dxf` to
      confirm hole centers from sections against the 3D B-rep families.
- [x] Visual inspection of STEP (reconstruction + original) in browser CAD chili3d,
      driven headlessly via playwright-cli — see `chili3d_viewing.md` (incl. the
      Node ≥20.11 gotcha and rotate/pan/zoom controls).
- [ ] Automated visual diff (overlay original vs reconstruction) for the gate.
- [ ] Change-mask preservation gate: compare original vs candidate and fail when
      unchanged regions drift (bbox/surface distance/key edge families + same
      camera X/Y/Z screenshots).
- [ ] `min_wall_thickness` check (medial-axis / ray sampling) — currently a named
      test in intent YAML but not yet implemented in `cadre.checks`.
- [ ] Replace the assembly size heuristic with a real check (count
      `NEXT_ASSEMBLY_USAGE_OCCURRENCE` / `PRODUCT` entities).
- [ ] Auto-compute hole pitch/spacing (we expose centers; derive pitch).
- [ ] Close the loop empirically: a full stage-1 reconstruction of one real part
      passing the equivalence gate (not just the interface primitive).
- [ ] Extract the fail-closed gate pattern (reasons list, quarantine root, fresh
      destination, same-revision evidence) into a reusable `cadre` module so
      studies stop re-implementing it.
- [ ] Automated report-provenance check: every validation report records the
      candidate hash, and any package command refuses an archived report even if
      a caller passes one explicitly.
