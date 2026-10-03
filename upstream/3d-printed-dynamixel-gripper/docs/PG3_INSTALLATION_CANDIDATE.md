# PG3 C9 + P05 camera installation candidate

2026-09-23. Repository: project root (`3d-printed-dynamixel-gripper`).
Execution record: `temp/workdoc_Sep23-2026_pg3_installable.md`.
**Installation DoD remains open. This is a locally modified assembly, not merely a relocated camera renderer.**

For the concise acceptance matrix and missing inputs, see
[Installation readiness](INSTALLATION_READINESS.md). Diagnostic PASS is not release approval.

## 2026-09-24 Requirements Change

The user no longer requires roll, superseding the earlier +/-30 degree request.
ID5-only jaw actuation with no additional motor is now user-confirmed.
See [current design](PG3_ID5_ONLY_DESIGN.md). The physical CAD mapping remains
unobserved. The r5 layout below is
historical evidence, not a completed implementation of this new architecture.
Camera purchase is pending; retain the reference 28x28 mm four-hole interface.
The object is a cube, with size/mass unspecified. P05 local cable-relief candidate
design and a reprint proposal are authorized, preserving source STEP, existing
bores, fastening/contact faces and support function. No printing or power approval.
OEM M2.6x5 tapping screws are absent or possession is unknown.
The permission resolves the former P05 authorization gate, not geometry, strength
or real harness fit. Do not cut the old M05 route into a new layout blindly.

## Current Acceptance Boundary

The active entrypoint is `specs/project.yaml` -> `specs/gripper_variants.yaml`
-> `installation_candidate`. Top-level PG3 catalog fields describe the original
intake diagnostic; they are retained as history, not the current modified assembly.
Current frozen geometry is r5; r4/r3 and their supplemental audits remain history. No partial audit
rewrites the original whole-assembly collision report into a PASS.

The preferred **candidate for further assembly validation** is now bench fastening
of the four pivots, followed by held linkage/spacer insertion and horn fastening.
This can avoid the in-situ temporary-screw exchange, but handling, fastener loading
and the installation gates below are still unresolved. See "Bench-Preassembled
Linkage Alternative"; this is not a released assembly instruction.

| Remaining gate | Next evidence required | Dependency |
|---|---|---|
| Saved-assembly contact classification | Resolve each pair with controlled Booleans or complete-material bounds; distinguish nominal seats from positive clearance and retain unclassified pairs | Agent CAD work; not waiting on camera purchase |
| Motion and assembly paths | Fixed-mid G1-G7 nominal body paths are covered below; complete nut/fastener loading and remaining whole-arm motion checks | Agent CAD work; required physical arm range remains unknown |
| M05 cable egress | An accepted route with actual cable envelope/bend limits, including a separate second cable exit | Cable specification; P05 local-relief permission if that solution is adopted |
| Camera observation and support | Required grasp ROI across required roll range; actual optical model, mass and PLA support assessment | Camera/operating requirements; a reference proxy is not acceptance |
| Fasteners and tools | Exact screw head/thread/lead, full-form engagement, bottom clearance and actual tool access | Hardware identification; nominal geometry alone is insufficient |
| Printed installation | Version-matched fabrication package, fit and nonpowered assembly observations | Prior gates and user physical trial; not performed by CAD scripts |

The unchanged P05 and unresolved cable routing prevent installation release.
The first two rows are independently actionable; external unknowns do not justify
stopping all CAD work. Do not treat unproven strength, friction or preload as
results of the kinematic MuJoCo demonstration.

Latest full repository regression at section42: **392 passed**, 8 existing
CadQuery deprecation warnings, 712.85 seconds. This includes the crank representation
and installed-assembly mesh-source regression tests. The381-test result belongs
to section40; 356 to section36; 310 to G7. None is physical
installation evidence. A dedicated headless Chili3D import of the frozen r5 mid
STEP matches all 309 named occurrences in DOM; whole-arm and terminal screenshots
and input/artifact hashes are in `outputs/pg3-r5-browser-r1/`. Console: 0 errors,
11 warnings. This checks viewer identity, not browser-kernel geometric equivalence.

### r5 Integration Checkpoint

`outputs/pg3-installable-candidate-r5/` integrates the same-dimension crank
representation repair from section41. Its replacement map exports a native
manufacturing STEP/STL and supplies the installed occurrence. Controlled native
material comparison against the supplied07_crank gives zero directional residuals
and2.046e-12 mm3 common-volume error, with passing operand identity checks.

The simulation exporter previously meshed PG3 parts from cached `model.neutral`
while using the installation factory only for the other parts. Consequently the
r4 simulation did not contain the locally relieved frame. Section42 corrects
that selection: every PG3 mesh comes from the installed mid assembly, inverse-
transformed into the mechanism frame. Missing/extra PG3 occurrences are rejected.
Replacement-geometry and inventory regression tests failed before this change.
The saved-STEP reconstruction in section41 already avoided the stale-source path.
Historical camera diagnostics retain their original scene hashes and are not
automatically promoted to r5 evidence.

All three r5 saved poses retain309 occurrences and the same24795 pair inventory:
24741 PASS,44 ERROR,10 UNKNOWN. Exactly six statuses per pose change from ERROR
to PASS: crank against two drive nuts and four horn screws. All other statuses
are unchanged. Raw errors are retained; this is not installation approval.
All413 recorded output hashes and19 captured source files match their files.
The seven changed-part meshes are single-component and watertight.

The refreshed6-DOF/two-loop simulation gives closure error6.641e-12 mm and pad-gap
error4.168e-12 mm. Its nine camera samples pass framing/nonzero-visibility only;
partial finger/pad occlusion remains visible. Gravity, force, real optics, actual
fasteners and PLA fit are not validated. X/Y/Z terminal views and the closed/+30
roll reference image were inspected. No fabrication or powered-operation flag
has been enabled. Camera ROI, cable egress and the remaining acceptance gates
above are still open.

### r5 Saved Interfaces And Candidate BOM

Section43 reruns the following against the saved r5 STEP files, not inherited
r4 status. Evidence directory: `outputs/pg3-installable-candidate-r5-audit/`.

| Report | Verified scope | Remaining boundary |
|---|---|---|
| `components_r1.json` | All54 raw unresolved pairs in each of3 poses;5 camera pairs clear by all-solid decomposition |49 remain UNKNOWN under this method; non-solid material was not discarded |
| `mating_regions_{open,mid,closed}_r1.json` | Support/M05 and spacer/horn covers clear;8 support screws stay within receiver regions |Actual threads, full-form engagement, preload and strength |
| `drive_receivers_{open,mid,closed}_r1.json` |6 PG3 mounting screws align/seat; horn insertion2.5 mm, bottom margin1.0; case insertion2.65, margin1.35 |Actual OEM head/lead/recess/tool matching |
| `bench_cluster_r1.json` |18 moved parts versus240 stationary parts,4320 translation pairs; bound2.003730515e-9 mm3;144 bench and2096 final horn tool pairs PASS |Handling an articulated cluster/spacer, actual tools, loading, tolerances, wires and other arm poses |
| `bom_r2.json` |95 terminal CAD occurrences covered once,94 physical items; input STEP SHA pinned |Not an upstream-arm BOM or purchasing/fabrication approval |

These disjoint supplements cover seven raw pairs with nonpenetration evidence
and fourteen with conditional receiver geometry. At section43,33 still lacked a
new r5 classification. Section44 below adds the fixed/horn display-partition bound;
32 supplier-internal reference pairs remain unaccepted. The raw44 ERROR/10 UNKNOWN
report is unchanged, and a nominal bound is not physical motor approval.

The previous `BOM_DRAFT.md` still mixed the rack concept with camera items and
omitted the PG3 hardware inventory. It now describes this candidate only, with
`specs/pg3_candidate_bom.yaml` as its machine-readable quantity source. The
checker rejects missing/extra terminal occurrences, duplicate selectors, wrong
quantities, altered scope, and a STEP from another revision. Only the explicitly
named fixed/horn motor display partition maps two occurrences to one physical
motor. Camera and pivot screws with the same nominal M2 length remain separate
because their modeled head heights differ. Cable and supplier hardware unknowns
remain explicit; the94-item count does not make the installation BOM complete.

```bash
rtk proxy uv run python -m scripts.check_pg3_bom \
  outputs/pg3-installable-candidate-r5 --out outputs/UNUSED-pg3-bom.json
rtk proxy uv run python -m scripts.review_pg3_bench_cluster \
  outputs/pg3-installable-candidate-r5 --out outputs/UNUSED-bench-cluster.json
```

The inventory command exits0 only for quantity reconciliation; the bench command
exits2 to retain the installation boundary. No CAD geometry was changed in section43.

### r5 Motion And Supplier Representation

Section44 adds the following r5-audit reports without geometry or tolerance changes:

- `motor_partition_r1.json`: all266 fixed-side faces accounted for in each saved
  pose; horn/contact-volume upper bound6.665831370284378e-5 mm3 against the existing
  1e-4 criterion. Rearward0.2 mm and added-material controls are rejected.
  This is a nominal display partition under declared rotation, not a physical bearing design.
- `continuous_opening_r1.json`: fixed-upstream opening25..135 degrees gives11073
  PROVEN_CLEAR,11 UNPROVEN and187 RIGID_RELATION_UNCHANGED. The36315 stationary
  pairs are not reassessed by this motion checker; all47586 pair identities remain accounted for.
- `pivot_motion_r1.json` and `horn_sweep_r1.json`: whole-host/link proofs resolve4
  pairs and complete supplier-spacer/rotor envelopes resolve2. Combined11079 clear,
  5 unproven and187 unchanged rigid relationships. The input/base-proof hashes are linked.
- `washer_contacts_r1.json`: all3 saved poses and both drive washers satisfy the
  nominal spin-invariant contact proof, with6 rejected displacement controls per
  pose. These4 contact pairs and the display partition account for the5 remaining
  non-rigid pairs. They are not relabeled positive clearance. Axial float, deformation,
  actual preload, all-arm motion, cables and physical motor internals remain outside this proof.

`supplier_inventory_r1.json` records why the remaining32 internal pairs cannot
be classified just by source leaf number. The official and R3 STEP each have35
leaves, but22 indices exchange positions, notably solids and surface details.
Under the single reviewed Ry90/T(-0.2,234.9,164.6) frame, a unique bounds/material-kind
correspondence has maximum bbox error4.3268e-7 mm. A naive ordinal pairing instead
has maximum bbox error24.6424 mm. The35 R3 leaves contain23 one-solid entries,
11 surface-only entries and one two-solid body. The official body's345 faces
versus R3's292 are recorded rather than silently healed.

All34 retained M06 occurrences match the original R3 finite signatures. Each
unresolved internal pair links that signature, the R3 manifest row and the
official envelope correspondence candidate. These are source-tracing facts only:
matching outer bounds can conceal different material, as a negative fixture
demonstrates. Neither those32 raw pairs nor actual motor construction is approved.

```bash
rtk proxy uv run python -m scripts.review_pg3_supplier_inventory \
  outputs/pg3-installable-candidate-r5 --out outputs/UNUSED-supplier-inventory.json
```

The checker is read-only, rejects ambiguous/missing/mismatched material-kind
inventories, records source hashes, and deliberately exits2. It does not infer
physical IDs from M-labels or authorize fabrication.

### Removable Bench Support Candidate

Section37 adds `gripper_design/pg3_bench_support.py` and the corresponding
`scripts.review_pg3_bench_support` checker. Saved artifacts are under
`outputs/pg3-bench-support-r1/`; this does not replace or modify frozen r4.
The48x60x3 mm base has four annular posts, outer radius1.9 / tip bore radius1.2 mm,
at the saved nut axes. Drive posts are1.2 mm high; carriage posts3.55 mm high.
Print +Z maps to source-world +X through a right-handed rigid transformation.

Reimported STEP matches the generated solid; STL is watertight, consistently
wound and one component. Jig against all17 linkage parts passes, as do four
opposed nut seats (6.81725605829 mm2 each) and144 tool/body combinations.
Lifting the fixed-mid linkage60 mm off the jig has aggregate continuous
intersection-volume upper bound0 mm3. This is contact-compatible nominal
geometry, not a positive-clearance or physical assembly certificate.

The horn spacer is separate and absent on this bench jig, not silently removed
from the eventual arm installation. The posts support nut backs but do not locate
loose nuts laterally. Practical loading/hand access, actual threads/torque,
0.7 mm wall printability/strength and height tolerances remain unverified.
No G-code, fabrication release or arm-installation approval is issued.
The checker exits2 and retains both approval flags asfalse even on nominal PASS.
The new eight tests plus six existing bench-cluster tests pass (14total,
65.31 seconds); the whole suite was not rerun after this isolated addition.
The frozen409-file checkpoint and81-file donor hashes remain unchanged.

Section38 separately checks individual nominal loading paths with
`scripts.review_pg3_bench_loading`: four nuts first, then crank, the two carriages,
the two links, followed by each pivot washer and bolt. Each of17 stages retains
every previously installed item, covering153 mover/obstacle pairs. All paths
start60 mm along source +X from the saved-mid orientation.
The initial generic report (`bench_loading_r1.json`) leaves seven stages unproven.
The supplemental report (`bench_loading_r2.json`, both in the r4-audit directory)
keeps those raw results and bounds four host/nut pairs by inverse relative nut
motion and eight bolt/receiver pairs by the existing whole-material axial bound.
All stage bounds meet1e-4 mm3; the largest is3.518587843e-6 mm3, not a measured
penetration. Two world-frame crank/nut enclosure checks remainERROR, with the
explicit common rigid-frame checks supplying the supplemental evidence instead.
No partner is removed and no tolerance or source shape is changed.
These paths do not establish loose-nut stability, actual threaded engagement or
tightening. Holding an articulated linkage and the separate spacer during the
subsequent arm insertion remains a physical task, not a rigid-body assumption.
The five focused files (bench loading/support/cluster, nut loading and screw
exchange) pass47 tests in151.04 seconds. Full-suite status remains the older
section36 checkpoint; section38 records both raw/supplemental source archives.

To regenerate the candidate headlessly, choose a **new, unused** output path:

```bash
rtk proxy uv run python -m scripts.review_pg3_installation --out outputs/pg3-install-next
```

This command generates diagnostic evidence, not installation approval. Read the
report statuses and supplemental checks; success of the process is not a release gate.

### Boolean Input Diagnostics

`r3-audit/boolean_arguments_r1.json` narrows, but does not fix, the crank failure.
`scripts/probe_pg3_saved_boolean.py` compares neutral/in-memory/saved crank solids
and explicitly enables four OCP argument checks (self-interference, small edges,
face rebuilding checks and curve-on-surface checks). All crank inputs have no
reported faults and classify the infinite point as OUT. Nevertheless, the saved
world solids return zero common volume with their independent copies, instead of
approximately1240.16165 mm3. The common rigid re-expression restores that identity
for saved mid/closed, but not open. In-memory world geometry also fails, so this
is not isolated to serialization. Argument validity is not Boolean reliability.

A4 mm box supplies a valid control; two overlapping4 mm solids produce explicit
self-interference faults despite topological validity. Neither control permits
accepting the failed crank operations. No healing, tolerance change or geometry
replacement was applied. The script deliberately exits2 and records
`installation_approved=false`; all unresolved assembly contacts remain unresolved.

## Continuous Opening Check Method

`scripts/review_pg3_motion_clearance.py` checks the25..135 degree PG3 relative
mechanism interval while the upstream arm/wrist stays fixed. It uses saved checkpoint
mid geometry and the existing analytic group transforms, not a new approximate
mechanism or a three-frame collision sample.

The checker first tests separation along an analytically invariant axis. Every
branch of the reviewed `pg3.group_transform` consists solely of construction-Rz
rotation and XY translation, so every material point retains its construction Z.
The fixed `to_arm` Ry90 transform makes world X equal to construction Z minus0.2.
Consequently a positive gap between the complete shapes' world-X bounding intervals
is a lower bound on separation throughout the opening interval. Curved extrema
are included by B-rep bounding boxes; surface-only enclosures retain their existing
1e-5 mm expansion on both sides. Gaps must exceed the unchanged distance epsilon.
An overlapping projection is inconclusive, not a collision result.

This proof is tied to the reviewed whole `pg3.py` SHA256
`ac2da0e35e6665c5526ed03f02f1881c4edd8c69c1679c58add1810814b1b775`.
The checker verifies it before and after running. A source change fails closed
until the formulas, all motion groups and placement have been re-reviewed; do not
refresh the hash merely to make a failing check pass. A mutation adding axial
translation is a rejected test control. Sampled poses corroborate but do not prove
the invariant. Upstream arm/wrist motion is outside this fixed-arm certificate.
Pairs without this axis certificate proceed to the point-speed method below;
invalid inputs and unchanged rigid relationships retain their separate statuses.

For each moving part, the checker bounds the speed of every material point in
mm per mechanism radian. With crank radius14 and link length24, the slider bound
is `14 + 196/(2*sqrt(380))`; the moving pin bound is14; a link bound is
`14 + (14/sqrt(380))*rho`, where rho conservatively bounds all material relative
to its pin using the neutral AABB. A drive-group point's speed is bounded by its
maximum XY radius. For a pair, the sum of these speeds bounds how rapidly its
distance can decrease.

A midpoint distance exceeding that sum times the interval half-width plus
the existing numerical distance epsilon proves separation throughout the
interval. Otherwise the interval is subdivided. At most256 evaluations per
pair and a minimum0.5 degree interval are computation limits: reaching either
without proof is **UNPROVEN**, never a PASS. A zero distance can be intended
contact, penetration or a numerical issue; this checker does not classify it.

Non-solid occurrences are conservatively enclosed by their full AABB, never
discarded. Same-rigid-group pairs are recorded as unchanged relationships,
**not accepted contacts**. Fully stationary pairs remain covered by the separate
static report. A proven nominal gap is not a print-tolerance allowance, minimum
engineering clearance, strength assessment, cable clearance or full-arm motion
approval. This supplemental check cannot authorize installation on its own.

Run with a new output filename; the checkpoint is never regenerated or overwritten:

```bash
rtk proxy uv run python -m scripts.review_pg3_motion_clearance \
  outputs/pg3-installable-candidate-r4 \
  --out outputs/pg3-installable-candidate-r4-audit/continuous_opening_next.json
```

The historical r3 r1 run accounts for all47586 pairs:36315 fully stationary pairs and11271
moving-context pairs. Of the latter,11067 are PROVEN_CLEAR,187 have unchanged
rigid relationships, and17 remain UNPROVEN. The source snapshot
`r3-audit/continuous_opening_r1_checker.py` matches the report's checker hash;
the working script was subsequently line-formatted with identical AST.

**r3 print-fit concern:** both carriages have zero nominal clearance against
the frame's end lands at25 and31.875 degrees. Controlled Booleans find zero
intersection volume at those inspected poses, but boundary-distance witnesses
confirm contact, not a positive running gap. At38.75/90/135 degrees the distance
is0.3 mm. In construction coordinates the end lands start atY=+/-18.5, exactly
matching the carriage bridge's side faces. This is not grounds for increasing
motor force or approving printed sliding fit.

r4 implements the local frame relief recorded in workdoc step26, limited to four
end-land strips and retaining the original archive. The inspected saved-part
poses now have0.3 mm gaps and a continuous positive-separation test passes.
Physical print fit remains unverified; historical r3 retains zero clearance.
The completed r4 saved-assembly run is
`r4-audit/continuous_opening_r1.json`:11069 PROVEN_CLEAR,15 UNPROVEN and187
RIGID_RELATION_UNCHANGED, using19862 distance evaluations. Coverage is the same
11271 moving-context pairs plus36315 separately recorded stationary pairs.
Exactly two pair statuses changed from r3: each carriage against the frame.
Each required127 evaluations and64 certified intervals. Its minimum evaluated
distance lower bound is approximately0.3 mm, not an exact global-minimum result.
Assembly/checker/dependency hashes and pair coverage were independently checked.
The newer `r4-audit/continuous_opening_r2.json` adds the source-guarded axial proof:
11073 PROVEN_CLEAR,11 UNPROVEN and187 unchanged rigid relationships. All11271
moving-context pair identities are identical to r1. Exactly four statuses change:
each left/right link against its carriage and drive washer. Their nominal axial
separation lower bound is0.3 mm throughout the opening interval. The geometry and
distance epsilon are unchanged. Axis projection proves10069 pairs;1015 proceed
to the point-speed method, which performs5523 distance evaluations.

The remaining11 comprise six computation-limit cases and five zero-distance
contact candidates, not11 proven physical interferences. See workdoc section21.1.
The static50ERROR/10UNKNOWN and187 rigid relationships are not accepted by this
supplemental result. The r1 checker snapshot is retained alongside its report.
The donor's fixed/horn split is made by a cylindrical cut for rotation display
(`reference/C7/source/design.py:187`), not a supplier-validated contact model;
zero distance at that partition is not evidence of real bearing or press-fit quality.

### Whole-Host Pivot Clearance

`r4-audit/pivot_motion_r1.json` supplements exactly four previously unresolved
pairs: each link against its crank and carriage. It does not exclude those hosts
or accept their entire bodies merely because the pin fits its hole.

`axial_ray_cover` extends conservative projections of **every** host face back to
the host's axial minimum. Any material point in a finite closed solid has a
positive-axis ray that exits through one of those faces, so this covers interior
material too. Full curved extrema are bounded, with1e-7 mm outward padding.
Surface-only, invalid and inverted/unbounded solids are rejected. The actual
crank has41 faces and each carriage62; all206 face entries across the four pairs
were independently checked for complete coverage.

The actual link's two R2.7 through-bores are verified as empty cylinders spanning
its entire axial range, using controlled Booleans. A0.3 mm displaced cylinder
must detect penetration. The corresponding R2.5 shoulder trajectory is matched
to the link endpoint analytically: `P=s*(14*cos(t),14*sin(t))`,
`Q=s*(x(t),0)` and `|Q-P|=24`. The reviewed link transform maps both neutral
endpoints to these points. Rigid transforms do not amplify the measured neutral
centre offsets, whose sum is deducted from the radius gap. This proof uses the
same guarded kinematics source as the opening checker.

Only cover cylinders that fit wholly inside that proven void use this radial
certificate. All other covers require invariant-axis separation or the original
continuous Lipschitz test. Thus the opposite crank pin and raised finger-mount
material remain included. The pin-region nominal gap lower bound is approximately
0.1999999 mm; this is **not** a claim that the complete pair's minimum gap is0.2 mm.
The other covers have separately certified positive separation.

All four saved-r4 pairs passed. Four off-axis fixtures and one extra-material
fixture were rejected; a plugged bore and unbounded solid are also unit controls.
Combining these proofs with the unchanged base certificate yields11077 clear,
7 unproven and187 unchanged rigid relationships. Static contact errors, actual
printed fit, clamping load and strength are not accepted by this result.

```bash
rtk proxy uv run python -m scripts.review_pg3_pivot_motion \
  outputs/pg3-installable-candidate-r4 \
  --base-motion outputs/pg3-installable-candidate-r4-audit/continuous_opening_r2.json \
  --out outputs/UNUSED-pivot-motion.json
```

The command validates the base assembly/code/dependency hashes and full moving
pair inventory. It exits2 because installation remains unapproved, even when all
four pair certificates and their negative controls succeed. Do not overwrite
historical reports or promote unrelated inherited contacts to accepted status.

### Horn Rotation Envelope

`r4-audit/horn_sweep_r1.json` resolves the two complete supplier spacers
`ARM_M06_ref27/28` against the horn. Their source names are
`DC11_A01_SPACER_DUMMY:1/:2`; neither solid is excluded.
The horn's Boolean self-controls fail, so Boolean subtraction is not used to
prove its enclosure. All19 boundary faces are bounded analytically. Trimmed
circle bounds include in-range stationary extrema, not just vertices or samples.
Finite-solid boundary coverage then encloses the complete material.

The rotation-invariant cylinder has radius10.3 mm, transverse centre
`(Y,Z)=(234.9,164.6)` and X span15.2999999..20.7000001 mm. Maximum required
radius is10.250000100000253 mm. Its distance to each complete spacer is
approximately0.05147051 mm. The certificate covers the declared25..135 degree
opening interval with the upstream arm fixed, not arbitrary whole-arm motion.
Horn B-rep face/edge/vertex tolerances are1e-7 mm; the spacers' maximum stored
tolerance is1.45348e-6 mm. These are CAD tolerances, not manufacturing allowances.

Moving each spacer0.2 mm toward the axis produces approximately0.21274581 mm3
intersection with the conservative cylinder; both controlled negative fixtures
fail. This is **envelope** intersection volume, not actual horn penetration volume.
Together with the prior pivot proof, counts are now11079 PROVEN_CLEAR,
5 UNPROVEN and187 RIGID_RELATION_UNCHANGED. The remaining five are the motor's
visualization partition, two crank/washer and two bolt/washer contact candidates.
They require contact-specific evidence, not an invented positive clearance.
Static50 ERROR/10 UNKNOWN results and physical acceptance remain unchanged.

```bash
rtk proxy uv run python -m scripts.review_pg3_horn_sweep \
  outputs/pg3-installable-candidate-r4 \
  --motion outputs/pg3-installable-candidate-r4-audit/continuous_opening_r2.json \
  --pivots outputs/pg3-installable-candidate-r4-audit/pivot_motion_r1.json \
  --out outputs/UNUSED-horn-sweep.json
```

Exit2 is intentional. Input hashes, prior proof dependencies and the full pair
inventory are checked; an existing output is refused. The report retains
`installation_approved=false` and `physical_motor_interface_approved=false`.

### Drive Washer Seating And Retained Link Play

`r4-audit/washer_contacts_r3.json` classifies the two crank/washer and two
bolt/washer pairs as **NOMINAL_CONTACT**, not positive-clearance pairs.
Each saved open/mid/closed assembly passes both sides. All18 displaced fixtures
are rejected on geometric conditions; an evaluation ERROR cannot count as a
successful negative control. The earlier r1 report predates that distinction;
r2 adds it, and current r3 additionally rejects nonfinite Boolean volumes.

The complete washer is checked against an OD7/ID2.2/t0.5 annular solid with
controlled, bidirectional Booleans. Its verified round shape and centre
trajectory make its pin-only translation nominally equivalent to drive rotation
as a material set. This allows the contact relation to persist throughout the
guarded25..135 degree opening interval, with the upstream arm fixed. This is
numerical equivalence under declared tolerances, not exact set identity.
A missing sector, off-axis washer or extra bolt material must not inherit it.

The whole crank is at or behind X29.6; the washer occupies X29.6..30.1.
The complete bolt lies inside its measured shank/head cover. Its R1 shank fits
the washer R1.1 through-bore with nominal radial gap0.1 mm; its head begins at
X30.1. Both seating pairs have opposed outward normals. Common areas are
15.48019780 mm2 at the shoulder and7.53982237 mm2 at the screw head.
No failed crank Boolean is used as proof of whole-body nonpenetration.

The separate saved-r4 `pivot_stacks_{open,mid,closed}_r1.json` reports remeasure
all four link pivots in each pose: front/rear axial play0.3 mm each, radial
play0.2 mm, retaining overlap0.8 mm. These are nominal unloaded dimensions.
**The clamping path is screw head -> washer -> shoulder -> host/nut, not through
the moving link.** Actual shoulder compression, washer bending and printing
error can still consume this play. No tightening torque, strength or physical
free-motion approval follows from these CAD values.

The two0.3 mm gaps describe the modeled centred position; they are not two
independently guaranteed physical clearances. A3.2 mm link inside a3.8 mm
shoulder span has nominal **total axial play0.6 mm** and may move to either
seat. During a non-powered trial, measure the actual seat-to-retainer span and
link thickness, account for tightening deformation, then check free articulation
and retention throughout the required travel without forced spreading.
Touching a retaining face is not the same as clamping the link. Conversely,
positive unloaded play does not establish freedom after preload. The nominal
motion certificates do not include this axial float or manufacturing variation.

```bash
rtk proxy uv run python -m scripts.review_pg3_washer_contacts \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-washer-contacts.json
rtk proxy uv run python -m scripts.review_pg3_pivot_stacks \
  outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step \
  --out outputs/UNUSED-pivot-stack.json
```

Both commands deliberately exit2. Old continuous-clearance counts remain
11079 clear /5 unproven /187 unchanged rigid relationships; the new report
provides nominal seating evidence for four of the five, not four new positive
gaps. The visualization-only fixed/horn partition and broader installation
requirements remain unresolved. No CAD geometry was changed in this review.

### Refreshed r4 Assembly Evidence

The saved r4 assembly was rechecked with the existing attachment, receiver,
component, tool-stage and insertion checkers. These are new r4 measurements,
not inherited r3 approvals. All files below are in
`outputs/pg3-installable-candidate-r4-audit/`.

| Evidence | Scope and current result | Not established |
|---|---|---|
| `components_r1.json` | All60 raw unresolved pairs, all three saved poses; five camera pairs clear by complete solid decomposition | Remaining55 pairs are UNKNOWN under this method; no surfaces were discarded |
| `attachments_mid_r1.json` | Saved P06 holes, seats, candidate depth and hardware/support geometry pass at mid | Actual parts, strength and full-arm motion |
| `mating_regions_{open,mid,closed}_r1.json` | P06/M05 and spacer/horn conservative-cover checks pass; eight new screws remain within bounded receiving regions | Actual threads, preload and thread-forming compatibility |
| `drive_receivers_{open,mid,closed}_r1.json` | Six PG3 mounting screws pass nominal receiver/seating checks per pose | Actual OEM head/tip/thread form or holding strength |
| `mechanism_lkey_stages_mid_r1.json` | 12932 tool/stage pairs pass under declared straight-tool/L-key envelopes and assembly order | Actual tools, bit fit, hand motion, cable-present service |
| `continuous_insertion_mid_r1.json` | Camera cluster4608 pairs and front jaw304 pairs pass the specified +Z60-to0 translation-volume check | Positive fitting clearance, alternative paths, moving arm, hands/cables |

Pair-by-pair reconciliation of each pose's original60 unresolved pairs yields:
**7 with supplemental nonpenetration evidence,14 with bounded receiver geometry
only,39 unresolved**. The39 consist of32 supplier-internal reference pairs,
the fixed/horn display partition, and six crank/screw-or-nut pairs. Origin in a
supplier assembly alone does not make those32 safe contacts. The14 receiving
regions likewise remain conditional until real fastener evidence is available.
The raw50 ERROR/10 UNKNOWN reports have not been changed, and no physical
installation approval follows from this reconciliation.

Re-run the current frozen input with new output paths. For receiver and mating
checks, repeat with `open`, `mid` and `closed`; stage/insertion checks below are
deliberately mid-only:

```bash
rtk proxy uv run python -m scripts.review_pg3_components outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-components.json
rtk proxy uv run python -m scripts.verify_pg3_attachment_export outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step --out outputs/UNUSED-attachment.json
rtk proxy uv run python -m scripts.review_pg3_mating_regions outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step --out outputs/UNUSED-mating.json
rtk proxy uv run python -m scripts.review_pg3_drive_fasteners outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step --out outputs/UNUSED-receivers.json
rtk proxy uv run python -m scripts.verify_pg3_service_stages outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step --mechanism --horn-l-key --out outputs/UNUSED-tools.json
rtk proxy uv run python -m scripts.certify_pg3_insertion outputs/pg3-installable-candidate-r4/arm_camera_mid_CANDIDATE.step --out outputs/UNUSED-insertion.json
```

Several checkers exit2 by design while installation remains unapproved. Inspect
their structured results rather than interpreting the exit code alone as a
geometric failure or success. The focused checker regression rerun passed22
tests; no implementation changed, and the preceding full254-test run was not
rerun during this evidence refresh.
The ten reports are preserved in `installation_refresh_r1_evidence.tar.gz`.
All116 files in the existing `washer_contacts_r3_sources.tar.gz` still match
the current implementation byte-for-byte. Workdoc section25.4 records both
archive hashes. These bundles require the separate frozen r4 CAD input and
do not constitute a manufacturing release.

### Display Motor Partition Boundary

`motor_partition_r2.json` in the r4 audit directory checks all266 fixed-body
faces against the complete horn rotation envelope in each saved pose. Whole-
solid self-Booleans failed for this imported split, so they are not used as
zero-intersection evidence. One straddling face needs a controlled partition at
X15.3: area conservation, both residual directions, self-controls and side
bounds are checked. Its forward portion is11.055013945414 mm from the axis,
outside the declared horn envelope radius10.3 mm.

The possible boundary slab is counted, not discarded. Its volume upper bound
is6.665831370284378e-5 mm3, below the unchanged1e-4 mm3 threshold. The result is
**BOUNDED_PARTITION_CONTACT**, not exact zero or a positive fitting clearance.
It applies to the donor's displayed fixed/horn split under the declared axis;
it does not qualify the actual motor's bearing, preload or rotating interface.

All three poses reject both the backward-shifted horn and extra fixed material
within its conservative sweep. Rejection must beUNPROVEN, not a kernelERROR.
Nine new tests include known synthetic penetration, missing partition material,
extra solids, oversized contact slabs, failed evaluation, NaN and inverted
solids. The earlier r1 report has failed negative controls and is not accepted.

```bash
rtk proxy uv run python -m scripts.review_pg3_motor_partition \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-motor-partition.json
```

Exit2 retains the unapproved installation status. Report, checker, dependency
and assembly hashes are recorded in workdoc section26. The original raw60-pair
and continuous11079/5/187 ledgers remain unchanged. This supplements one display
partition question among the39 unresolved static pairs, not a physical release.

### Mechanism Body Insertion, Not Only Tool Access

`scripts/review_pg3_mechanism_insertion.py` checks saved r4 mid geometry against
the explicit G1/G2 assembly sequence. Tool withdrawal alone did not establish
that these bodies could reach their final positions. Both proposed body paths
retain orientation and translate from world+X60 mm to zero, before the camera
is installed. Nuts are assumed temporarily retained with their respective body;
loading and retaining those nuts is not established by this path check.

| Stage | Rigidly moved cluster | Already present | Full pair count | Total swept-intersection volume upper bound |
|---|---|---:|---:|---:|
| G1 | Frame and four cap nuts | 233 occurrences | 1165 | 2.2919888890343488e-10 mm3 |
| G2 | Crank, horn spacer and two drive nuts | 240 occurrences | 960 | 2.0037305148434825e-9 mm3 |

Two case screws follow G1 insertion; four horn screws follow G2 insertion.
No already installed obstacle is omitted. The report records full Cartesian
pair coverage and these later-installed screws separately. The acceptance budget
is1e-4 mm3 for the **sum across each stage**, not an allowance multiplied by
its number of pairs. This permits nominal contact; it is not a positive-clearance
or printed-fit certificate.

Independent proofs include full swept AABB overlap, conservative all-boundary
translation cover, and continuous occupied-distance bounds using the exact
translation speed60 mm per unit offset fraction. The spacer/horn proof encloses
all19 horn faces by a body and boss; all8 spacer faces exclude all spacer material
from the boss cylinder by a finite-solid exit-ray argument. Axial translation
preserves that radial exclusion. Its0.29999989999998 mm radial bound is local to
the boss, not the whole assembly's minimum clearance. Surface-only obstacles are
expanded AABB reservations; invalid or inverted material cannot take a bbox shortcut.
Earlier kernel errors and loose-cover results remain visible, not relabelled PASS.

```bash
rtk proxy uv run python -m scripts.review_pg3_mechanism_insertion \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-mechanism-insertion.json
```

Current report: `outputs/pg3-installable-candidate-r4-audit/mechanism_insertion_r5.json`.
Workdoc section28 records the source archive, hashes and34 focused passing tests.
The prior275-test full run was not repeated for this isolated new checker.
The command still exits2 because installation is not approved. G3 and later body
paths, nut loading/retention, hands, cables, actual fasteners, other arm poses and
physical assembly remain separate gates. Neither CAD geometry nor print release
was changed by this check.

### Sequential Slider And Link Body Insertion

The next six stages were checked against the same saved r4 mid STEP, using
`scripts/review_pg3_slider_link_insertion.py`. Each candidate body path retains
orientation and translates from world+X60 mm to zero. Caps, fingers and camera
are not yet installed. Carriages carry their three preloaded nuts as a rigid
cluster; this assumes temporary retention, not a validated nut-loading operation.

| Stage | Moved bodies | Previously installed obstacles | Full pair count |
|---|---:|---:|---:|
| G3_R carriage and nuts | 4 | 248 | 992 |
| G3_L carriage and nuts | 4 | 252 | 1008 |
| G4_R link | 1 | 256 | 256 |
| G4_R washers | 2 | 257 | 514 |
| G4_L link | 1 | 261 | 261 |
| G4_L washers | 2 | 262 | 524 |

The two right-side pivot bolts are added after the right washers, before the
left link. They remain obstacles for subsequent operations. The left bolts
follow the left washers. Final occurrence identities and shape instances match
all266 occurrences of the previously reviewed G4 tool stage, not only its count.
All3555 mover/obstacle pairs are accounted for without duplicates or omissions.
Each stage's total continuous-volume upper bound is0.0 mm3 under the declared
nominal CAD and methods; the unchanged acceptance threshold is1e-4 mm3 per stage.
Washer seating includes contact, so this is not a positive-clearance claim.

```bash
rtk proxy uv run python -m scripts.review_pg3_slider_link_insertion \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-slider-link-insertion.json
```

Evidence: `outputs/pg3-installable-candidate-r4-audit/slider_link_insertion_r1.json`.
Workdoc section29 records hashes, source archive and18 focused passing tests
(the five new tests were also rerun after a lint-only loop cleanup).
No shared checker or CAD geometry was changed. The prior full275-test result
is not a new full-suite run. Exit2 and `installation_approved=false` remain.
G5/G6 body paths are covered separately below. Nut loading/retention, internal
cluster fit, actual screw insertion/threads, hands, cables, physical printed fit
and other arm poses are not approved by these six path checks.

### Sequential Cap And Finger Body Insertion

`scripts/review_pg3_cap_finger_insertion.py` continues from the266-part G4 stage.
Upper cap, its two washers, lower cap, its two washers, right finger, its two
washers, left finger and its two washers each enter from world+X60 mm to zero,
at fixed orientation in the saved r4 mid pose. Two corresponding bolts are
installed after each washer stage and remain obstacles for all later stages.
All earlier parts remain present; pads and camera are installed later.

The eight stages contain266/534/271/544/276/554/281/564 mover-obstacle pairs,
3290 total. Every stage has a0.0 mm3 summed nominal continuous-overlap upper
bound, against the unchanged1e-4 mm3 per-stage threshold. The final286 occurrence
names and shape instances match the G6 tool-stage inventory. Cap hardware side
assignment is also tested against saved world-Y coordinates, not names alone.
Seat contacts retain UNPROVEN distance certificates alongside successful whole
boundary translation-cover certificates. This does not establish positive
clearance, low assembly force, preload or printed fit.

An actual saved upper cap displaced0.5 mm into the frame is rejected: the
continuous upper bound is414.0 mm3, and the final-pose Boolean diagnostic finds
277.6907304 mm3 intersection. The negative control is a test copy, not a CAD edit.

```bash
rtk proxy uv run python -m scripts.review_pg3_cap_finger_insertion \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-cap-finger-insertion.json
rtk proxy uv run pytest -q tests/test_pg3_cap_finger_insertion.py
```

Evidence: `outputs/pg3-installable-candidate-r4-audit/cap_finger_insertion_r1.json`.
Workdoc section30 contains input/source hashes and archive verification.
The focused related run had24 passing tests; after adding the saved-geometry
negative control, all7 new tests passed. No new full-suite or simulation run is
claimed. Exit2 and `installation_approved=false` are intentional. Pad insertion,
nut loading/retention, actual fasteners, hands, cables, physical tolerances and
other arm poses remain separate gates; actual installation DoD remains open.

### Pad Placement Without Sliding The Bond Face

The donor specifies two28x20 mm sheet pads, **1 mm total thickness including
adhesive**, centred vertically and ending1 mm behind each finger tip. The saved
r4 pads retain that envelope. A1 mm sheet plus an additional glue layer is not
automatically equivalent; changed cured thickness requires rechecking opening,
closed-end contact, grasp position, backing and assembly paths.

`scripts/review_pg3_pad_insertion.py` continues after the286-part G6 stage. In
the saved fixed mid pose, move the right pad through these world offsets from
its final location: `(60,0,3)` -> `(0,0,3)` -> `(0,0,0)` mm. The left pad uses
negative Z offsets instead, with the installed right pad retained as an obstacle.
This keeps the bonding face3 mm from its finger during the forward insertion,
then approaches normally. It does not drag an exposed adhesive face along the
finger. The3 mm offset is a checked part path, not a hand/tool clearance claim.

All four continuous segments account for1146 mover/obstacle pairs. Each segment
has a0.0 mm3 nominal summed overlap upper bound. Normal seating includes contact:
the distance certificates remainUNPROVEN while the complete-material translation
covers establish the volume bound. The final288 identities and shape instances
match every non-camera occurrence. A direct60 mm normal approach is a rejected
control because it crosses the opposite finger; a saved-pad copy at the18 mm
intermediate offset has more than100 mm3 measured intersection with that finger.

```bash
rtk proxy uv run python -m scripts.review_pg3_pad_insertion \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-pad-insertion.json
rtk proxy uv run python -m scripts.render_pg3_pad_insertion \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-pad-insertion-views
```

Evidence is in `outputs/pg3-installable-candidate-r4-audit/pad_insertion_r1.json`
and `pad_insertion_views_r1/manifest.json`; workdoc section31 records provenance.
At the G7 checkpoint, the12 new tests and37 related tests passed; its full
repository run was310 passed. The current full regression is listed above.
All six headless VTK waypoint images were visually inspected and checked for
nonblank moving-pad pixels. Green is the pad being installed, black is a previously
installed pad, orange the fingers. The-Y view is intentionally cropped; the
numerical check, not that crop, covers all installed obstacles. Camera installation
follows this stage and is not shown in these views.

The pad material, adhesive, release liner, positioning/pressure tooling, PLA
bond compatibility, cured strength and gripping friction remain unconfirmed.
These path checks do not approve bonding or physical assembly. They do not alter
the frozen CAD, resolve the P05 cable exit, or promote the installation DoD.

Across the saved G1/G2, G3/G4, G5/G6 and G7 reports,20 body-path segments contain
10116 mover/obstacle pair checks. This is a count across segments, not10116 unique
physical contacts or a whole-arm motion certificate. Every nominal segment has
its own accepted volume bound under its stated assumptions; all four reports
retain `installation_approved=false`. Preloaded nuts and later bolts still need
their own loading/retention/thread evidence. The separate camera-body path check
is not included in this count, and actual bonding is not closed by G7.

### Nut Loading Is Not Nut Retention

`scripts/review_pg3_nut_loading.py` checks the12 PG3 nuts before their hosts are
installed on the arm. Four separate bench clusters match the existing G1/G2/G3
body inventories: frame+four cap nuts, crank/spacer+two drive nuts, and each
carriage+two finger nuts+one pivot nut. Nuts enter sequentially along world-X30 mm
to zero. Previously loaded nuts remain obstacles within each cluster. The27 full
pair checks cover these bench clusters, not hands, fixtures or an installed arm.

The original rectangular swept cover and distance methods leave all12 paths
UNPROVEN. The supplement constructs a hexagonal prismatic enclosure using six
whole-B-rep support bounds. Rotated B-rep extrema include curved bulges between
vertices; each support and axial endpoint is padded outward1e-7 mm. A bounded,
consistent convex polygon and extended X interval enclose the entire source
throughout translation. The nut centre hole is conservatively filled in this
enclosure only; no source geometry is healed or altered.

Both world-space and an explicit common rigid coordinate re-expression are
checked. The world check retains25PASS/2ERROR; the re-expressed check has27PASS.
The original crank self-Boolean errors remain visible. All12 supplemented
nominal paths have a0.0 mm3 summed intersection upper bound, against the unchanged
1e-4 mm3 per-stage limit. Four mounting families displaced0.2 mm into their seats
are rejected. An adversarial curved bulge is enclosed even though its maximum
extent is not a topological vertex.

Evidence: `outputs/pg3-installable-candidate-r4-audit/nut_loading_r2.json`.
The earlier r1 result and both source snapshots remain available; workdoc
section32 lists hashes. At the nine-test checkpoint,28 related tests passed.
After extending the seat-intrusion controls to four families, all12 new tests
passed. The full run then remained the earlier310-test checkpoint; the current
full regression above now includes these tests.

```bash
rtk proxy uv run python -m scripts.review_pg3_nut_loading \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-nut-loading.json
```

The reverse of each accepted nominal path is available in the same bench state.
A hex pocket can prevent rotation without providing axial retention. This does
not predict friction or falling under gravity, and it does not prove access after
mounting the host. Temporary retention during transport/body insertion must still
be specified and checked. Press-fit friction, tape, glue and an unmodelled fixture
are not accepted by assumption. Additional thickness, thread contamination and
removal access must be checked if a holding method is selected. Camera nuts are
outside this PG3 check. No static whole-assembly or full-motion gate is silently
closed by this fixed-mid bench result; installation remains unapproved.

### Loading Nuts Immediately Before Fastening

`scripts/review_pg3_nut_late_loading.py` tests an alternative to transporting
hosts with loose, preloaded nuts. At the saved mid pose, the earliest-host context
checks2955 pairs. The stricter `fastening_envelope` context keeps every non-camera
occurrence except the target nut and its bolt:286 obstacles per nut,3432 pairs.
This is an access bound over a same-pose superset, not proof that the entire
assembly can already be fastened in that order. The camera is installed later.

Both contexts supplementally clear9 nominal -X30-to0 nut paths with zero volume
upper bound: the4 cap nuts,4 finger nuts and left carriage pivot nut. Raw Boolean
errors remain recorded. Actual nut tolerance, hand/holding/driver access and
fastener engagement are still separate gates.

Three paths are not approved:

- Both drive nuts: an actual nut displaced-X1.3 intersects the frame by
  1.07148138 mm3. The five coarse path samples alone miss this narrow obstruction.
  The left path also retains motor/surface ERROR/UNKNOWN results.
- Right carriage pivot nut: the actual nut at-X7.5 intersects P06 by
  1.86915691 mm3, increasing to3.14805374 mm3 at the sampled-X15/-X22.5/-X30
  positions. Case fastener envelopes also obstruct portions of the path.

These are failures of a specific straight path, not proof that every assembly
sequence or lateral route is impossible. Conservative total overlap bounds in
the reports are not measured material penetration volumes.

For the drive nuts, using the existing screw temporarily without the large washer
is a candidate only. The saved screw head is3.8 mm against a5.4 mm link bore;
seating it temporarily requires-X0.5 mm from its final position. These dimensions
do not prove insertion, thread engagement, capture during washer exchange or
tool access. No temporary screw arrangement has been adopted in the frozen CAD.
The right carriage nut needs its own alternative procedure.

Evidence: `outputs/pg3-installable-candidate-r4-audit/nut_late_loading_r2.json`
(r1 is the earlier-host context). Workdoc section33 records the hashes, negative
controls and next checks. Related nut-loading tests:20 passed, including8 new
tests. That check preceded the current full-suite rerun listed above.

```bash
rtk proxy uv run python -m scripts.review_pg3_nut_late_loading \
  outputs/pg3-installable-candidate-r4 --context fastening_envelope \
  --out outputs/UNUSED-nut-late-loading.json
```

The command deliberately exits2: installation is still unapproved.

### Existing Drive Screws As Temporary Nut Holders

The candidate in `scripts/review_pg3_temporary_drive_screws.py` keeps both existing
drive screws, but temporarily removes their large washers and seats the screw
heads directly on the printed shoulders. The only geometry change in this check
is a rigid-X0.5 mm displacement of each saved screw; frozen CAD is unchanged.

Measured at saved mid: head seating area7.186393195 mm2, smooth nut-span overlap
1.6 mm, tip protrusion0.9 mm beyond the nut, tip at worldX19.6 mm and head seat at
X29.6 mm. Both heads clear the link bores by0.8 mm radially. This is nominal
geometry, not evidence of actual thread engagement or permitted tightening torque.

Keeping the temporary screws throughout, the checked order is:

1. Insert the crank/spacer/drive-nut cluster with both temporary screws, then
   install the four horn screws.
2. Insert the right and left carriage clusters.
3. Insert the right and left links, **before adding any pivot-retainer washers**.

All5 +X60-to0 body paths pass the existing1e-4 mm3 volume-bound criterion over3973
mover/obstacle pairs. G2 has a2.003730515e-9 mm3 conservative upper bound; the
other4 have zero bounds. No arm/motor/previous temporary screw is deleted.
The9 internal temporary-screw contacts yield7PASS/2ERROR in world coordinates;
the explicit common rigid re-expression gives9PASS. Raw errors remain recorded.

Negative controls detect real frame penetration with a0.5 mm longer tip and
blocked link insertion with a washer-sized head. Seven new tests pass; the latest
related20-test run passed in54.66 seconds.

This is **not an approved complete assembly instruction**. Material paths for
initial screw insertion and final washer exchange now have supplemental evidence
below. Actual threads/PLA loading, nut retention during exchange, hands/tools,
and the right carriage nut still need checks. Canonical carriage
clusters retain preloaded nuts as occupancy; their physical holding is not proved
by moving the cluster mathematically. Large washers remain mandatory in the
final assembly. Do not operate the gripper in this temporary state.

Evidence: `outputs/pg3-installable-candidate-r4-audit/temporary_drive_screws_r1.json`.
Workdoc section34 records source/input hashes and the next unresolved steps.

```bash
rtk proxy uv run python -m scripts.review_pg3_temporary_drive_screws \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-temporary-drive.json
```

Exit2 is deliberate because installation remains unapproved.

### Temporary Screw Loading And Final Washer Exchange

`scripts/review_pg3_drive_screw_exchange.py` adds8 fixed-mid paths: bench loading
of each temporary screw, followed (after the separately checked body stages) by
right screw removal, right washer insertion, right final screw insertion, then
the same three left operations. The right final screw stays installed during the
left exchange. Both links, the arm, motors and the opposite screw remain obstacles.
Final drive bolts/washers are the exact saved shapes, not the temporary placements.

All1568 physical mover/obstacle pairs are checked in world coordinates and an
explicit common rigid frame. A two-cylinder material bound supplements12 close
bolt/receiver pairs: it verifies whole-bolt containment, examines every obstacle
boundary face and retains numerical padding and containment residuals. It does
not infer a through hole merely from a cylindrical face or discard a blind floor.
The bound is uniform over all translation parameters, not a proof about the
union swept by containment residuals. All selected pair bounds are summed before
applying the existing1e-4 mm3 criterion.

Both bench loading paths and temporary screw removal paths have upper bounds
about3.447899e-6 mm3; final screw insertion about3.518585e-6 mm3; washer paths zero.
All8 paths pass this **nominal material-intersection bound**. This is not exact
zero intersection or positive running clearance. Raw UNPROVEN/ERROR results
remain alongside the supplemental proof.

Thirteen focused tests reject head intrusion, axis misalignment, blind bores,
uncovered material, missing arm obstacles, invalid travel and aggregate tolerance
overruns. A diagnostic penetration vetoes acceptance even if another proof claims
a clear bound. The latest related run is20 passed in43.83 seconds.

**Retention remains a prerequisite, not a result:** the nuts and links are fixed
at their saved positions in this check. Physical nut capture while a screw is
absent, hand support, actual thread engagement and driver rotation/access still
need verification. Reversing a smooth proxy translation does not simulate
unscrewing a real threaded fastener. Installation is not approved.

Evidence: `outputs/pg3-installable-candidate-r4-audit/drive_screw_exchange_r1.json`;
source snapshot and hashes are recorded in workdoc section35.

```bash
rtk proxy uv run python -m scripts.review_pg3_drive_screw_exchange \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-drive-exchange.json
```

The command exits2 deliberately; never overwrite a previous evidence file.

### Bench-Preassembled Linkage Alternative

Before designing extra in-situ nut keepers, a different order was checked with
`scripts/review_pg3_bench_cluster.py`. Bench-fasten the crank, two carriages and
two links with all four final pivot bolt/washer/nut sets:17 components. Hold that
articulated mechanism and the separate horn spacer at the saved mid geometry,
translate the18 parts into the already-mounted frame, then install the4 horn screws.
The4 finger nuts are loaded later using the separately checked access paths.
G1 cap nuts remain conservative stationary obstacles in the insertion check.

The18-by240 insertion scan covers4320 pairs with a2.003730515e-9 mm3 total bound
(below the existing1e-4 criterion, not exact zero). All144 bench pivot-tool pairs
and2096 final horn-tool pairs pass. Both access and withdrawal envelopes are kept;
final washers are already installed rather than removed to simplify the path.
Six focused tests reject an omitted frame, moved link, missing last-screw tool
and a wrong-side approach with actual frame penetration.

Compared with the temporary-screw sequence, this moves all four pivot nuts,
including the obstructed right carriage nut, to an exposed bench operation.
It can eliminate both drive screw exchanges. The tradeoff is holding an articulated
mechanism at its insertion pose and supporting the **uncaptured separate spacer**.
The checker does not prove that the mechanism is rigid, that hands/fixtures can
hold it, or that the bench fasteners can be loaded/held and tightened in practice.
The four horn screw insertion/thread interfaces remain separate from tool access.
Previous intra-cluster contact and actual hardware/print gates are not waived.

Bench support also needs attention: drive nut rear faces are at worldX20.5 mm,
carriage nut rear faces atX22.85 mm. A single flat surface does not support them
equally. Their screw tips are atX20.1 andX22.1 respectively, so support must leave
tip clearance. These are measured saved-CAD values, not a validated fixture design.

Evidence: `outputs/pg3-installable-candidate-r4-audit/bench_cluster_r1.json`.
Four headless views in `bench_cluster_views_r1/` show the held18-part state,
not a complete arm or a physical holding method. Workdoc section36 records hashes,
visual inspection and the comparison with the former sequence.

```bash
rtk proxy uv run python -m scripts.review_pg3_bench_cluster \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-bench-cluster.json
```

Exit2 remains deliberate: neither this path/tool result nor a short assembly
sequence satisfies the actual-installation DoD by itself.

## Design Contract

PG3 C92 J28 C9 source archive is unchanged. The candidate frame has only the four
local reliefs specified below; mechanism, fingers, motor alignment and the
25-135 degree *relative mechanism* interval are retained. This
interval is not an absolute servo command range. Physical ID5 remains reserved
for wrist roll; the gripper's bus ID has not been assigned by this CAD work.
No hardware is energized or commanded.

### Local PG3 Frame Relief In r4

In **PG3 construction coordinates**, remove only the four combinations of
X[-46,-44]/[44,46], Y[-18.8,-18.5]/[18.5,18.8], Z[19.5,24.1] mm.
Total removed material is11.04 mm3; addition and removed material outside that
mask are both0. Frame volume12645.914126 ->12634.874126 mm3. The result is one
valid solid with a watertight, connected STL. Motor/cap bores and their seating
regions, main rails and outer envelope are retained. Each end land retains
2 x3.2 x4.6 mm material, not a strength qualification.

The replacement is `changed_parts_CANDIDATE/PG3_frame_guide_relief.{step,stl}`.
Do not use the copied original `01_frame` for this candidate. `review.json`
contains the explicit replacement map; original PG3 copies are reference-only.
The replacement part uses construction coordinates; its assembly placement is
Ry(+90deg), then translation(-0.2,234.9,164.6) mm, identical to the original.
`r4-audit/guide_relief/guide_relief.json` verifies all three saved assemblies
contain this exact saved replacement using controlled bidirectional differences.
Its eight separate before/after PNGs show the four end lands without overlay.

P05 and upstream arm links are unchanged. P06 is retained as a motor support;
removing it entirely is prohibited. The candidate is derived by subtraction from
the original B-rep, not a newly guessed outline. In R3 world coordinates (mm):

| Local P06 change | Purpose | Preserved |
|---|---|---|
| Remove Y >= 240.9 | Delete obsolete distal fixed finger | Motor support and mounting-hole zone |
| Trim X >= 16.3 | Leave 0.5 mm nominal gap to PG3 frame | Upstream horn seat and bottom screw load paths |
| Four bottom bores 2.4 -> 2.8 mm | Clear M2.6 case tapping screws | Centres, support thickness and seating plane |
| Lower horn rear counterbore, diameter4.8, Y187.9..192.0 | Open the original blind lower bore and seat a spacer | Front seat Y183.9, centre(-0.2,156.6) in XZ, diameter2.4 through 4 mm wall |

No addition outside the original part. Hole centres are (-6.2 or 5.8, 206.9 or
230.9), axes +Z. Case seating plane Z150.35; support underside Z146.35.
Original frame intersection: 240.5625 mm3. Revised intersection: 0; gap: 0.5 mm.
The final P06 volume is 9089.691818072772 mm3, one valid solid. Earlier volumes
9122.1193 and9148.2573 precede the rear counterbore and case-bore corrections.
All changes lie inside the four explicitly declared change masks. The rear
counterbore is a local fastening repair, not permission to remodel the link.

The side camera carrier origin is (52,53,164.6), with +Y-facing reference camera.
The bracket joins the existing P05 clamp and a replaceable 28 x 28 mm carrier.
Only the left cable-tie ear is removed because it occupied the right M3 clamp
screw region. The right tie anchor remains. The camera model, cable, actual
optical origin/FOV and mass still need confirmation against the purchased part.
The current bridge spans Y49..140.4 (91.4 mm), X26..58, Z193.6..199.6.
This is a longer rear-set cantilever, not the earlier short bracket. Its stiffness,
PLA creep and vibration are unverified; better framing is not mechanical approval.

In candidate r3, a broad root roof spans X[-23.2,58], Y[130.4,144.15],
Z[196.6,202.6]. The old bridge joined the saddle over only60.9 mm3.
The new saddle volume is27191.15443 mm3 (previous22452.65443). This local
fixture addition preserves P05, camera pose and clamp seats. It increases the
load-path section but is not a calculated strength or PLA-creep approval.

### Wiring Blocker And Corrected Exit Interpretation

The nominal9.5 x3.8 mm EHR-3 plug access cross-section, swept40 mm straight
backward from M05's rear plane, intersects original P05 by144.4 mm3 per port.
It also intersects the camera saddle by37.905 and front jaw by27.075 mm3 per
port. A long straight approach encounters M04 hardware too. These are blocked
**access corridors**, not claims that the installed connector penetrates P05.
The source header geometry is used to locate each corridor; another arm/header
pose is rejected rather than reusing these fixed rear planes.

**Correction:** that straight corridor is not the normal assembled cable exit.
The official XL430 assembly figure removes the rear cover to route wires via
the side outlet or hollow idler shaft, then reinstalls the cover. See
`references/robotis-xl430-cabling/SOURCE.md` and the pinned supplier images.
The3.5 mm rear gap therefore does not define every possible cable route. Do not
justify cutting P05 solely by the hypothetical straight-corridor failure.

The [official XL430 product page](https://en.robotis.com/shop_en/item.php?it_id=902-0135-000)
also limits the hollow-case route to one cable (checked2026-09-23). A future
central P05 relief must not be used to justify passing both daisy-chain cables
through that route. The second harness needs a separately validated side exit.

The corrected first-lateral-leg diagnostic uses six separate1.9 mm wire envelopes
and assumed1.2 mm centreline bends. It avoids wire-to-wire overlap but intersects
P05 at both side outlets:5.52881 mm3 per wire, X14.05..16 or-16.4..-14.45,
Y149.65..151.55. The nominal motor/host lateral gap starts at only0.1 mm.
It also overlaps rear-cover corners by0.11463..0.12584 mm3 per wire; the assumed
route is rejected, not squeezed into a fit. There are1851PASS/6UNKNOWN/12FAIL
in `r3-audit/wire_side_outlet_r1/routes.json`.

The hollow-axis alternative is also obstructed by the unchanged P05 back plate:
a diagnostic radius3 cylinder along the rear axis(-0.2,Y,164.6), Y137..147,
intersects113.09734 mm3, equal to a full4 mm wall. Thus the candidate host needs
further wiring design even with the standard preassembly sequence. This does
not prove all possible free-form routes impossible. No actual cable bend limit
has been established. P05 has NOT been cut; permission for a minimal local
relief/reprint was requested again with this corrected evidence.

The public JST drawing, dimensions, source links and hash are recorded in
`references/jst-eh/SOURCE.md`; actual cable dimensions and bend radius are unknown.

## Fastening Candidates

The following are explicit procurement/fit candidates, not claims of purchased
or measured fasteners. Full release requires the actual head, washer, thread
form and tool to satisfy these envelopes and the assembly test.

| Joint | Candidate and quantity | Stack / verification |
|---|---|---|
| P06 -> M06 case side | 4 x ROBOTIS S14 PHS M2.6x8 TAP K, 4 x washer ID2.8/OD7/t0.5 | 4 mm PLA + 0.5 washer; penetration3.5, max4, bottom margin0.5 mm |
| Camera -> carrier | 4 x M2x10 + M2 nuts | Candidate grip6.5, nut1.6, tail1.9 mm |
| Carrier -> bracket | 2 x M2x10 + captive M2 nuts | Candidate grip7, nut1.6, tail1.4 mm |
| P05 clamp | 2 x M3x16 + M3 nuts | Candidate grip10, nut2.4, tail3.6 mm |
| P06 -> M05 horn | 4 x M2x8 socket head (max diameter3.8/height2), 4 x metal spacer ID2.2/t1 | PLA4 + spacer1 -> engagement3, bottom margin0.5 mm. Three spacers OD5; lower spacer OD4.3 |
| PG3 mechanism | Original C9 fasteners retained | See source assembly instructions; integration scan does not certify thread preload |

**Do not replace side-hole tapping screws with the M2.5 case assembly screws.**
The original 2.4 mm P06 bores obstruct the 2.6 mm shank (3.14159 mm3 per bore).
Revised 2.8 mm bores give 0.1 mm nominal radial clearance before printing effects.

Sources: [ROBOTIS XL430 drawing](https://www.robotis.com/service/download.php?no=772),
[side-hole screw package specification](https://en.robotis.com/shop_en/item.php?it_id=902-0135-000),
[S14 dimensions/name](https://www.robotis.com/shop/item.php?it_id=903-0183-000).
The S14 product listing establishes nominal screw designation, not measured head
dimensions or load capacity in this assembly. Official PDF/STEP and SHA256 are
retained in `references/robotis-xl430-new-20180324/`.

Actual M06 concave bore axes are independently extracted from the mating CAD.
Their cylindrical spans are Z150.55..154.35; the first 0.2 mm is the entry region.
`case_attachment_report` rejects a 1 mm misplaced motor and M2.6x5/M2.6x10
with the declared stack. Minimum3 mm engagement is a candidate design target,
not a validated pull-out or creep limit.

The upstream horn actual seat is Y183.9 (source face186); the case actual seat
is Z150.35 (face98). These are planar-face measurements, not inferred from bore
length. Axial seat-gap negative controls reject a motor shifted along its bore.
The lower original horn bore was blind: a cylindrical span ending atY189.9 did
not mean the material ended there. The rejected M2x10/spacer arrangement collided
with the original rear material. The local counterbore gives a common4 mm grip
for four M2x8 screws. All bolt/spacer vs revised P06 intersections are zero.
The lower spacer's full material-supported annulus is9.99812 mm2, excluding the
larger support bore, not merely the spacer's smaller ID. No pull-out or clamp-load
allowable is inferred from this area.

### PG3 Pivot Retention

The four original C9 printed-shoulder pivots were remeasured independently in
the saved r3 open/mid/closed assemblies. `r3-audit/pivot_contacts_*.json` records
actual concave/convex cylindrical interfaces and planar face intersections:

| Nominal property | Measured at all four pivots |
|---|---|
| Rear/front axial link gap |0.3 /0.3 mm|
| Radial link-to-shoulder gap |0.2 mm per side|
| Retainer overlap beyond link bore |0.8 mm radial|
| Nut/printed-seat contact |9.70165 mm2|
| Retainer/shoulder contact |15.48020 mm2|
| Bolt-head/retainer contact |7.53982 mm2|
| Bolt tail past nut |0.4 mm drive;0.75 mm carriage|

The clamp path is head -> large retainer -> printed shoulder -> captive nut,
not through the rotating link. These are nominal CAD measurements, not actual
preload, washer bending, print-tolerance, creep or free-motion approval. The
retainers remain OD7/ID2.2/t0.5; smaller general washers are not interchangeable.
The checker rejects displaced links/washers/bolts, a nut0.2 mm inside its seat,
and a headless pin. The latter two incorrectly passed the initial axial-span-only
checker; planar contact and head-geometry checks fixed that false acceptance.
`pivot_stacks_*.json` is the superseded initial local audit; use `pivot_contacts_*`.
No PG3 source geometry or fastener position was changed by this audit.

## Assembly and Service Order

This is a partially verified mechanical sequence, **not yet an executable full
installation instruction**. Resolve M05 wiring access and wire egress first;
do not assemble the link and discover afterward that the plugs cannot be fitted.

1. With power disconnected, support the arm and remove obsolete P07/P06 only
   as needed for replacement. Do not force-turn a geared motor or use torque to
   overcome a tight printed fit.
2. Mount revised P06 to the M05 horn **before installing M06**. Final upstream
   screw candidates are M2x8 with the spacers above. Their nominal straight tool
   corridors are checked; actual tools, hand clearance and insertion remain open.
3. Place M06 on the P06 seat. Fit the four case-side screws/washer candidates
   from below. Stop if a screw bottoms before clamping or deforms the PLA seat.
4. Use the immutable PG3 C9 bench order as the baseline for the frame, horn spacer,
   crank, sliders, links, pivot retainers, caps and fingers. The installed-arm
   refinements above remain partial candidates, not an approved replacement order.
   Prioritize bench fastening of all four pivots, then held mechanism insertion
   and horn fastening, before caps/fingers/pads. Validate bench support and handling
   before adopting it. The temporary-drive-screw sequence is retained as an
   alternative, not a mandatory exchange operation. Keep all large pivot-retainer
   washers in the final assembly; they are functional, not optional cosmetics.
5. Bench stage A: insert the two captive carrier nuts, then attach the camera and
   spacer to the carrier with four M2 screw/nut pairs **before attaching the
   bracket**. Stage B: attach that subassembly to the saddle using two accessible
   M2 screws. A coarse all-M2-after-bracket sequence failed2 tool pairs and is
   retained as a rejected sequence, not silently erased.
6. Seat the camera saddle and front jaw on P05 without squeezing the motor
   cheeks. Tighten the M3 clamp using the validated **nominal short-driver
   envelope**: shaft radius2.5 x exposed25, handle diameter20 x length25 mm.
   A 75 mm shaft plus 30 mm handle intersects the PG3 mechanism.
   The right M3 nut socket additionally requires an exposed100 mm shaft,
   diameter9, with diameter20 x length30 handle. Its former75 mm shaft caused
   441.05 mm3 handle/bracket intersection. These envelopes are procurement
   constraints, not claims that such tools are already on hand.
   At the saved mid arm pose, lower the preassembled16-part camera/saddle cluster
   from60 mm above its final position, then lower the front jaw from above, before
   inserting either M3 screw. The unpowered rigid translation and its reverse have
   a conservative continuous occupied-volume clearance proof. This assumes a
   fixed arm with no cables or hands in the path; it does not certify hand space.
7. For camera service, release the M3 clamp and remove the complete camera
   subassembly upward; undo stage B, then service stage A. The M3 screws must be
   removed first. Other insertion/tool paths, fingers around the handle, and cable
   slack remain to be checked.
8. Route the actual camera cable through the retained tie anchor with strain
   relief, leaving connector access and a measured bend radius. No unverified
   cable envelope has been called PASS.

## Evidence and Reproduction

Historical section27 checkpoint: `outputs/pg3-installable-candidate-r4/`.
For current r5 counts, source selection and images, see "r5 Integration Checkpoint".
Three saved/reloaded assemblies each contain309 occurrences and24795 changed-
context pairs:24735 PASS,50 ERROR,10 UNKNOWN,0 reported FAIL. The ERROR/UNKNOWN
results mean this is **not** an all-clear collision result. Six changed-part
meshes are watertight, consistently wound, connected single components.
Independent r4 artifact checks verified409 hashed files,39 nonblank PNGs and47
GIF frames. Per-channel spatial pixel standard deviation exceeds16.88 for every
PNG; visual inspection also covered the whole assembly and XYZ terminal views.
The section27 checkpoint full regression passed275 tests (364.17s), including finite-cylinder
crank fastener checks and explicit retention of an unproven screw, controlled
motor partition boundaries, nominal washer seating and invalid-evidence guards,
trimmed-arc horn enclosures, whole-host pivot
clearance, source-guarded axial separation, local-relief, saved-part continuous-
clearance, root-roof, mating-region, cable and pivot tests (eight existing
Assembly.save warnings).
Lint passed. The displaced-header guard has a
RED-to-GREEN record; route tests include an explicit wire-to-wire collision.
These are software checks, not a physical installation certificate.
The latest full-suite checkpoint is section42 (392passed); section38 has47
focused regression tests. The section36 result (356passed) and historical
275-test paragraph are not the latest implementation-wide status.

The r4 supplemental directory is `outputs/pg3-installable-candidate-r4-audit/`:
`guide_relief/` verifies the saved local change and all three installed frames;
`occlusion.json` repeats the nine-pose visibility diagnostic with the historical
r4 scene; it predates the installed-frame mesh-source correction in section42.
`continuous_opening_r2.json` records the current fixed-arm opening certificate;
both continuous-checker snapshots match their own r1/r2 report hashes.
`pivot_motion_r1.json` supplements four whole-host/link pairs with negative controls.
Its `pivot_motion_r1_sources.tar.gz` preserves111 code/test/lock files; archived
checker/dependency bytes match the report. This is a source backup, not a complete
CAD input bundle or a manufacturing release. See workdoc section22.2 for its hash.
`horn_sweep_r1.json` adds two complete-spacer rotation certificates.
`horn_sweep_r1_sources.tar.gz` preserves its code/test/lock snapshot; checker and
all eight dependency hashes match. See workdoc section23 for the evidence and hash.
`washer_contacts_r3.json` adds nominal seating evidence, while
`pivot_stacks_{open,mid,closed}_r1.json` remeasure all four pivots in r4.
The124-entry `washer_contacts_r3_sources.tar.gz` includes the matching checker,
all seven dependencies, tests and lock file; workdoc section24 records its hash.
At+/-30 degrees roll the less-visible pad fractions remain89.24% open,
13.08% mid and5.23% closed; these are pad silhouettes, not a grasped-object ROI
or actual-camera calibration. A nonzero silhouette is not useful-image approval.

### Occluding Parts Identified

`outputs/pg3-occluders-r1/review.json` attributes the isolated pad silhouette
pixels to the nearest rendered geometry at the same optics and pose. It verifies
the frozen scene and309 mesh hashes, uses integer segmentation without MSAA,
and reproduces all18 existing visible/reference pixel counts at nine poses.
There are no unclassified pixels. No camera, holder or other CAD was moved.

At opening135/roll+30, the left pad has73 visible pixels out of1396; all1323
hidden pixels are blocked by `PG3_finger_L`. The right pad has546/1476 visible;
`PG3_finger_L` blocks860 and `PG3_pad_L` blocks70. At opening90/roll+30, the
left finger blocks917 of1055 left-pad pixels. Roll-30 mirrors the sides.
At roll0 both pad silhouettes are fully visible at all three sampled openings.

Thus the measured **pad-region** occlusion is due to the fingers/pads, not the
P05/P06 support or camera holder. This does not prove those structures never
occlude another object or ROI. Removing bracket material alone cannot cure this
particular occlusion. Viewpoint selection needs a defined grasped-object ROI,
object dimensions and required roll range; full visibility of both entire pad
silhouettes was never a confirmed user requirement. Actual lens/optics remain
unknown, so this diagnosis neither releases the present mount nor authorizes an
unrelated redesign. RGB and classified masks are saved beside the report.

The following supplemental measurements belong to **historical r3** in
`outputs/pg3-installable-candidate-r3-audit/`. Unless explicitly labeled r4,
do not promote them to validation of the entire current assembly.
Saved r3 attachment geometry passes. Both straight camera insertion paths retain
their conservative continuous-clearance proofs. The nine-pose occlusion audit is
unchanged from r2: roof reinforcement did not improve or worsen the measured pad
silhouette fractions. `mating_regions_mid.json` proves P06 versus an all-face
M05 material cover and PG3 spacer versus a horn cover clear. It also proves eight
nominal screw envelopes clear outside their explicitly bounded mating regions.
The M2.6 forming region is intentionally larger than the pilot; this is NOT
zero thread/material contact or proof of thread strength. Unsupported protruding
face types, displaced joints and over-deep screws fail closed.
The original50ERROR/10UNKNOWN per pose is retained, not overwritten by these
local supplemental proofs. `connector_access_pose_checked.json` records the
remaining wiring obstacle; its result is1220PASS/2ERROR/6UNKNOWN/8FAIL.

Historical supplemental audits remain in `outputs/pg3-installable-candidate-r2-audit/`:
`attachments.json` checks actual axes, seat gaps, fastener/P06 overlap and bearing
areas, and confirmed exported modified parts matched that historical run's geometry.
`service_stages.json`: A104/B32/C1236/D756/E1236 tool pairs PASS. A/B are the
separate bench stages; C is camera clamp on arm; D is horn before M06; E is case.
These reports do not claim hand clearance or continuous insertion proof.
The frozen r2 coarse bench report retains208 PASS/2 FAIL; the explicit A/B
sequence supersedes that sequence, not its recorded measurements.
Kinematic closure error6.641e-12 mm; pad-gap error4.168e-12 mm.

The old r1 camera cropped pads at roll. The revised physical mount was checked
at299 opening/roll samples (opening25..135 and roll-30..30, both5 degree steps).
Minimum projected pad margin42.9884 px in640x480; minimum visible pad area73 px.
Old r1 had166 failed pad observations and minimum margin-137.17 px. The new
framing/nonzero-visibility benchmark passes, **not the actual imaging DoD**:
partial occlusion remains visible and73 pixels can be inadequate for useful
grasp observation. The required roll range and actual optics are unresolved.
`camera_grid/camera_range.json` binds the scene XML and all309 mesh hashes;
XML equality alone cannot prove identical geometry. Segmentation uses explicit
offsamples=0 after MSAA edge IDs caused a renderer exception. No IDs were clamped.

The frozen r2 provenance predates stronger axial seat-gap checks and the explicit
A/B tool-stage helper. Nominal geometry did not change. Supplemental audits
document this distinction; neither historical report nor snapshot was overwritten.

### Supplemental Contact and Insertion Review

The same audit directory contains the following later reports, tied to saved r2
assembly hashes. They do not overwrite the original collision report:

- `contact_triage.json`: each pose's60 unresolved pairs comprise32 supplier-
  internal/partitioned-motor pairs,14 inherited PG3 joints,1 modified P06/motor,
  4 new horn screw/thread,4 new case tapper/pilot,5 camera/mount pairs. The46
  inherited pairs match source signatures, not a proof of harmless contact.
- `components.json`: split operands into **all** existing solids, without healing
  or discarding shells, and test their complete Cartesian product. The5 camera
  pairs are clear with aggregate intersection upper bound0 mm3. Each pose still
  has55 unresolved pairs. The original50ERROR/10UNKNOWN remains intact; five of
  its errors now have independent component-level clearance evidence.
- `occlusion.json`:9 poses, identical optics and meshes with/without occluders.
  At roll30, the less-visible pad silhouette is89.24% at opening25 degrees,
  13.08% at90, and5.23% at135. Zero roll gives100% of both silhouettes. These are
  whole-pad silhouettes, **not contact-face or grasped-object visibility**.
  Do not redesign solely to maximize this proxy; actual objects/optics matter.
- `insertion.json`:61 points on each camera/clamper +Z60-to0 insertion path.
- `continuous_insertion.json`: the original solid plus swept AABBs of every
  boundary face conservatively covers its continuous translation. Camera cluster:
  4607 continuously separated pairs and1 near pair; front jaw after cluster:
  303 separated pairs and1 near pair. Both near pairs have0 mm3 overlap upper
  bound (13 and9 controlled cover checks). Exact zero-volume swept boundary
  boxes are recorded; small positive widths are never discarded. The method
  permits touching, not a guaranteed positive fit margin, and does not cover rotation.

Negative controls include a displaced inherited part, penetration in only one
compound solid, mixed solid/surface input, multiplied per-component tolerances,
full/partial occlusion, and a thin obstacle between otherwise-clear sampled poses.
After these supplemental checks:140 tests passed (95.53s), lint and changed-file
format checks passed. Physical installation remains unverified.

```bash
rtk proxy uv run pytest -q
rtk proxy uv run ruff check .
rtk proxy env MUJOCO_GL=egl uv run python -m scripts.review_pg3_installation \
  --out outputs/pg3-installable-candidate-NEXT
```

Use an unused output directory. The command exits2 while installation acceptance
is incomplete. It exports changed STEP/STL, unchanged PG3 donor STEP/print-STL,
the full assembly at three openings, strict changed-context collision reports,
staged tool reports, headless XYZ/isometric images and MuJoCo kinematics.
Changed-part STL remain in assembly coordinates; they are not an approved
slicer orientation or a G-code job. No SD card was modified.

The simulation checks slider-crank closure and image visibility with real CAD
meshes, but uses dummy inertias, zero gravity and no physical contacts. It does
not validate holding torque, friction, PLA strength or contact dynamics.
The camera FOV50 and sensor position (52,85,164.6) are explicit proxies.

## PG3 Tool-Stage Candidate

`scripts/verify_pg3_service_stages.py --mechanism` supplements the original
50 mm shaft-only access check. Stages G1/G2/G4/G5/G6 retain the complete arm
and every previously installed PG3 occurrence. They check all18 screws, including
the target screw as an obstacle. Camera installation C follows these stages;
camera A/B are separate subassembly operations. Pads follow G6.

The generic tool reservation uses a diameter3 x75 mm shaft, diameter20 x30 mm
handle and diameter80 x100 mm grip volume. Each cylindrical segment is extended
by100 mm to cover continuous +X withdrawal, not merely endpoints. These are
declared design envelopes, not measured tools or validated human hand sizes.
The model begins0.05 mm above the screw head and does not prove bit engagement.

`mechanism_tool_stages.json` retains four ERROR results: the static and swept
tools at horn bolts0/1 touch the crank (distance0); its Boolean self-control
fails. This is not a proven positive penetration volume and is not accepted.
With `--horn-l-key`, a separate candidate replaces only the four horn tools.
[PB210.1,5 supplier specifications](https://www.pbswisstools.com/en/tools/quality-hand-tools/precisionbits/product/pb-210)
give1.5 mm AF and14/50 mm inner arm lengths. The candidate additionally requires
at least35 mm straight shank before the elbow/grip region. That requirement is
**not** a published supplier dimension. Its circular shaft cover has radius
1.5/sqrt(3); the elbow turning reservation is radius15 and the grip radius40.
Actual bend geometry, socket engagement, torque rating and human access must
fit these envelopes before adopting this tool.

At the saved r3 mid pose, the L-key candidate's two limiting crank clearances
are0.633975 mm; the other two are2.069575 mm. The candidate run clears all five
PG3 stages (960/1984/2128/2208/2288 tool-obstacle checks respectively).
This is **conditional outer-tool access**, not complete boltability, bolt/nut
insertion, all arm poses or actual assembly approval. Case tapper drive recesses
are not represented in the source CAD and require an actual screw/tool choice.

Latest dimension-labelled report:
`outputs/pg3-installable-candidate-r3-audit/mechanism_lkey_stages_r2.json`.
The earlier report lacks the explicit distinction between inner and overall
arm lengths; geometry is identical, but its checker hash remains historical.

```bash
rtk proxy uv run python -m scripts.verify_pg3_service_stages \
  outputs/pg3-installable-candidate-r3/arm_camera_mid_CANDIDATE.step \
  --mechanism --horn-l-key --out outputs/UNUSED-tool-report.json
```

Exit0 means only the specified nominal tool stages passed. Installation remains
unaccepted regardless of that exit code. Do not overwrite previous reports.

## Supplemental Rigid-Frame Contact Audit

`scripts/review_pg3_local_contacts.py` applies the same inverse arm placement
and inverse drive rotation to both operands. It changes neither relative pose
nor donor geometry, Boolean tolerances or partner inventory. It checks all14
raw unresolved PG3-to-PG3 pairs in each saved assembly, leaving the other46
raw unresolved pairs explicitly outside this supplemental scope.

The first saved-artifact run found six clear pairs at mid and closed: crank
against four horn screws and two captive drive nuts. Independent-copy self-cut
and self-common controls pass in those coordinate representations. Deliberately
moving a horn screw0.5 mm inward produces3.593197 mm3 penetration; moving a
drive nut0.2 mm into its seat produces1.940330 mm3. The eight other PG3 pairs
remain ERROR, not approved threaded contacts.

At the saved open pose, all14 pairs and both negative controls remain ERROR.
The equivalent in-memory generation passed its unit fixtures; that difference
is exactly why the saved artifact is checked separately. No result at mid or
closed is inherited by open, nor does this prove continuous mechanism motion.
`local_contacts_r2.json` in the r3 audit directory records accepted clear pairs
only when that pose's negative controls detect actual penetration. It retains
`all_selected_contacts_clear=false` and `installation_approved=false`.

```bash
rtk proxy uv run python -m scripts.review_pg3_local_contacts \
  outputs/pg3-installable-candidate-r3 --out outputs/UNUSED-local-contacts.json
```

Exit2 is intentional: supplemental pair clearance cannot approve installation.
The original raw collision reports are not rewritten.

### Current r4 Crank Fastener Evidence

The same rigid-frame checker was rerun on frozen r4, producing
`local_contacts_r1.json` under `outputs/pg3-installable-candidate-r4-audit/`.
Mid/closed each retain six controlled clear pairs; open remains14 ERROR.
These are current saved-artifact results, not inherited r3 approvals.

`scripts/review_pg3_crank_fasteners.py` adds a separate whole-material check:
the actual complete screw must lie inside its measured shank/head cylinder
union with zero outside residual. Every crank face is checked over each finite
cylinder's axial span. After excluding all boundary from the connected cylinder
core, an OUT point classification excludes complete containment. The point alone
is insufficient. Controlled face partitions retain all axial surface material;
end slabs consume a summed volume budget, never an implicit zero allowance.
Opposing head/seat normals and common area are checked separately.

Saved open/mid/closed all yield bounded nominal contact for screws1,2,3:
the maximum summed contact-volume upper bound is2.896549482513e-6 mm3,
below the unchanged1e-4 mm3 threshold. Their18 displaced controls are UNPROVEN.
**Screw0 remains ERROR in all three poses**, including its six negative controls,
because crank face5 fails self-control during a required partition. A common
rigid coordinate rotation did not fix it. The whole four-screw report therefore
retains `accepted=false` for every pose. No collision-free assembly claim follows.
The six nuts/bolts accepted at mid by the other method do not clear saved open.

```bash
rtk proxy uv run python -m scripts.review_pg3_crank_fasteners \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-crank-fasteners.json
```

Current report: `outputs/pg3-installable-candidate-r4-audit/crank_fasteners_r1.json`.
Exit2 preserves installation nonapproval. Twelve unit checks include a distinct
fail-closed regression for screw0; their success is not four-screw acceptance.
Neither this bound nor a smooth screw model proves thread engagement, tightening,
PLA bearing strength, nut capture, printed fit or cable clearance. The two drive
nuts remain outside this cylinder method's scope. No geometry was altered.

## PG3 Receiver And Head Seating Audit

### Source-Equivalent Crank Repair Candidate

Workdoc section41 adds `outputs/pg3-crank-representation-r2/`, with three whole-arm
STEP assemblies. The supplied C7 `crank()` construction and dimensions are reused
under a source hash guard, deferring intermediate `clean()` calls until the end.
No hole or outline is redesigned. Controlled comparison of the reimported native
candidate against the original manufacturing STEP gives zero material in both
directional differences (common-volume error 2.046e-12 mm3); both operands pass
independent-copy identity. This is stronger than a volume or vertex-only match.

All three saved installed cranks also pass identity. Each is checked against all
308 other saved occurrences, giving 924 PASS pairs across the three static poses.
All four horn screws have bounded nominal seating; all24 displaced controls are
UNPROVEN, not ERROR. The maximum contact-volume upper bound remains
2.896549482513e-6 mm3 against the unchanged1e-4 threshold. There are no partner
exclusions. These are static crank-partner checks, not whole-arm motion approval.

The earlier r4 ERROR report and original files remain intact. At section41 this
candidate was not yet the installation entrypoint; section42 integrates it into
r5 without granting fabrication release. Current reference
camera, cable-egress, physical fastener and PLA load gates remain unresolved.
The intermediate-clean hypothesis is supported by the construction experiment;
it is not a complete explanation of the kernel's internal defect. Translation,
OBB/non-destructive flags, circular seam rotation, and an isolated2.8.0/7.9.3.1.1
environment did not fix the original input. No dependency update was adopted.

```bash
rtk proxy uv run python -m scripts.review_pg3_crank_representation \
  outputs/pg3-installable-candidate-r4 --out outputs/UNUSED-crank-representation
rtk proxy env MUJOCO_GL=egl uv run python -m scripts.simulate_pg3_saved \
  outputs/pg3-crank-representation-r2 --out outputs/UNUSED-crank-simulation
```

Both commands retain exit2 while installation is unapproved. The simulation reads
the SHA-verified saved poses, not a new source-only build, and checks the kinematic
mapping before rendering. Neither kinematic motion nor nominal contacts prove
thread engagement, assembly preload, strength or camera task visibility.

The saved-candidate simulation completed221 samples with maximum closure residual
6.641072494313e-12 mm and pad-gap error4.168221323653e-12 mm. Evidence is under
`outputs/pg3-crank-representation-simulation-r1/`. All328 output hashes were checked;
terminal and camera-proxy frames were inspected. The candidate/old-checker/frame
regression run has32 passing tests. This does not supersede the section40 full-suite
checkpoint or validate forces and camera visibility.

### Receiver Audit Scope

`scripts/review_pg3_drive_fasteners.py` reads the actual receiver and screw
faces from each saved assembly. Horn material is conservatively covered by its
complete boundary-derived body/boss cover; both case solids remain inside the
case AABB. Potential overlap is allowed only inside receiver-derived cylindrical
regions, not inside an entire motor exclusion. These regions stay fixed when
testing displaced screws.

| Interface | Count | Insertion from seat | Tip/depth-limit gap | Cylindrical-span overlap |
|---|---:|---:|---:|---:|
| Horn M2x6 model | 4 | 2.50 mm | 1.00 mm | 2.30 mm |
| Front case M2.6x5 countersunk model | 2 | 2.65 mm | 1.35 mm | 2.45 mm |

The cylinder-span overlap excludes the0.2 mm entry chamfer, but is **not a
measurement of actual threaded engagement**. Depth ceilings are3.5/4.0 mm from
the pinned ROBOTIS drawing. Minimum remaining bottom margin0.5 mm is a design
check, not a supplier strength qualification. Head/crank planar contact measures
7.186393 mm2 per horn screw. Each case countersink has20.692727 mm2 nominal
contact with opposing outward normals. Equal conical faces on two overlapping
male parts must fail; common area alone was insufficient and was corrected.

The saved open/mid/closed assemblies pass these six **receiver-region and seating**
checks. Reports: `drive_receivers_{open,mid,closed}_r2.json` in the r3 audit
directory. Earlier reports lack the opposing-normal gate and remain historical.
This does not clear the complete crank at open or other motor-internal contacts.

```bash
rtk proxy uv run python -m scripts.review_pg3_drive_fasteners \
  outputs/pg3-installable-candidate-r3/arm_camera_mid_CANDIDATE.step \
  --out outputs/UNUSED-drive-receivers.json
```

The command exits2 because installation remains unapproved. Actual screws,
drive recess, strength, thread form, tolerances and tightening torque still need
their own evidence. The supplier's package list states M2.6x5 tapping screws;
that listing alone does **not** confirm the modeled countersunk head dimensions.
Do not substitute an8 mm internal case screw for this5 mm mounting model.

## Case Screw Procurement Gate

Checked2026-09-23. A nominal diameter/length match is not an approved replacement.

| Candidate | Confirmed fact | Decision / missing evidence |
|---|---|---|
| [ROBOTIS XL430 package screw](https://en.robotis.com/shop_en/item.php?it_id=902-0135-000) | M2.6x5 TAP listed | Preferred compatibility reference; actual head, tip, thread pitch and existing formed-hole condition unknown. Ask for package-screw photos/drawing before adapting the seat. |
| [Supplier item210001010026005001](https://www.tsurugacorp.co.jp/shop/g/g210001010026005001/) | B0 countersunk2.6x5 is listed; listed thread series28 TPI | Availability of a size is not XL430 approval. Lead taper and receiver compatibility unresolved; do not order as a drop-in. |
| [WILCO UF-2606-B1](https://wilco.jp/products/U/UF-B1.html) | Listed2.6x6, head diameter5.2/height1.5 mm, PH1 | Not5 mm; B1 is not automatically interchangeable with the OEM thread. Do not extend the current screw solely to gain engagement. |

[Yahata's tapping-screw explanation](https://yht.co.jp/column/240514_tapping-screw/)
describes a2..2.5-turn tapered lead for B0. As a **conditional screening example**,
retain the current CAD seating/insertion2.65 mm, assume28 TPI (pitch25.4/28 mm),
entry relief0.2 mm, and no other unthreaded neck/bottom relief. Then full-form
axial overlap is only0.182143..0.635714 mm, not2.65 mm. This is an inference
under declared assumptions, not a measurement of an OEM screw or its strength.
It fails an illustrative1 mm full-form screening target; that target itself is
not an approved load/strength criterion. A different head profile changes seating
and invalidates even this conditional estimate.

`gripper_design.serviceability.check_fastener_stack` now distinguishes tip
insertion from full-form overlap. Four incomplete-thread dimensions must be
provided explicitly; unknown values remainUNKNOWN rather than becoming zero.
It intersects the screw's full-form interval with the receiver's usable interval,
checks bottom clearance separately, and rejects NaN dimensions. AnyPASS from
this function still leaves thread strength unverified. The older raw CAD
receiver reports remain geometric evidence only, not procurement approval.

No screw, motor pilot hole, countersink or print geometry was changed based on
these unconfirmed commercial candidates. The required next evidence is OEM
thread/head/tip identification or supplier confirmation, then seat/envelope and
full-form checks using that exact product and its tolerances.

## Remaining Acceptance

- Close the remaining imported-B-rep contact errors without widening tolerances
  or excluding inconvenient partners. Supplier internal overlaps and deliberate
  threaded contacts need separate, evidence-backed classification.
- Confirm actual upstream hardware, all insertion/removal/tool sweeps and cabling.
- Confirm physical camera and motor/link mapping, expected load/working poses.
- Resolve the desired camera-visible roll range and useful grasped-object view,
  addressing unacceptable cropping/occlusion with the same physical holder/camera placement.
- Establish printing orientation/tolerances, then non-powered assembly evidence:
  all screws clamp before bottoming, no forced spreading, no slider binding,
  no cable pinch, camera sees the actual grasp region.

Partial CAD passes cannot close the user's installation DoD. Old diagnostic
completion claims do not supersede this acceptance boundary.
