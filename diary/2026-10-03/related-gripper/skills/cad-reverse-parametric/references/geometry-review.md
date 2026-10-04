# Reviewing geometry with executable evidence

Use this when reviewing a reconstruction or diagnosing a discrepancy between
passing tests and a browser view. Start from the source STEP, its generated
candidate, the part driver, and its intent file. Keep source files unchanged and
put review exports in a separate output directory so old artifacts do not become
evidence for new code.

## Surface geometry is not design intent

`cadre.cli inspect part.step` reports:

- `surface_sense`: concave, convex, or unknown, comparing the oriented material
  normal with the radial direction on an outward-oriented solid. Convex cylinders include external bosses and rounded
  plate tops; concave cylinders are candidate bores or concave fillets.
- `axial_range_mm`: endpoints projected onto the sign-normalized cylinder axis
  through the global origin. Compare these to find separated coaxial features.
- `angular_span_deg`: extent of the trimmed surface; a partial cylindrical
  outside profile is not automatically a circular hole.
- `bore_families` and `outer_cylinder_families`: sense-separated summaries.
- `hole_families`: the older, unclassified summary, retained for compatibility.
  A matching result here does not prove that either model contains the same holes.

The cylinder's `axis_pt` may be far from the actual face. Family `centers` are
projected onto a perpendicular plane, intentionally discarding axial position.
Never use either as evidence of pocket depth or of a bore's entry face. Two faces
on one axis can be split faces, separate tabs, blind bores, or outside profiles.
Likewise a diameter-band label such as `M2-tap` is not evidence of a thread.

When independently classifying a generated/extruded cylindrical face, do not
interpret `FORWARD`/`REVERSED` alone as bore/outer wall. Check the oriented surface
normal against its radial direction at a point on the trimmed face, and confirm
the solid's material side. Parametric surface direction can change while the
physical bore remains the same.
Use `cadre.probes.cylinder_surface_sense` for this comparison. Its regression
fixtures cover native generated shapes with positive/negative extrusion along
multiple axes as well as STEP round trips. Export/import may normalize a surface
parameterization and hide a native-shape defect, so both stages matter.

Do not use rounded probe/family summaries for tighter numerical acceptance.
Extract full-precision axes from the B-rep, retain the trimmed axial spans, and
use a one-to-one pattern assignment. Independent nearest-neighbour matches may
silently assign several expected fasteners to the same actual hole. Keep hole
count/axis matching, opposing seat normals, axial seat offsets and trimmed-face
contact as separate gates; missing geometry is unknown, not a zero-error match.

## Check an actual opening

For a proposed blind recess, verify all three against the B-rep:

1. A point just inside the stated entry face is void.
2. Points through the intended depth remain void.
3. Points behind the intended floor are material, with the required remaining wall.

Use cross-sections or rays for more complex shapes. Checking only a cylindrical
face's length can accept a completely buried cavity. For through features, checking
only the two endpoints can miss an intervening plug; inspect the complete path.

CadQuery's named `XZ` plane has normal **-Y**. Positive extrusion follows this
normal, not global +Y. When a helper accepts a world-axis direction, translate
that sign to the workplane normal. Test both directions on X, Y and Z with a
simple known solid before using the helper in a part.
Source: [CadQuery plane definitions](https://cadquery.readthedocs.io/en/latest/_modules/cadquery/occ_impl/geom.html).

## Browser verification

Use the dedicated Playwright session and local Chili3D workflow in
`chili3d_viewing.md`. Load the source, previous candidate and revised candidate
separately. Fit the content after setting a consistent viewport; compare the same
axis directions as well as an oblique view. Wait for the model tree entry and
canvases, not merely the page title or the end of a fixed sleep.

The DOM confirms loading and controls, not solid geometry. Inspect rendered views
and cross-check any claimed holes or seats against the numerical STEP evidence.
Treat smooth rendering, closed meshes, and zero browser errors as separate from
shape preservation, fit, and fabrication acceptance.

## Stop a false success

Before using Boolean differences as a preservation oracle on imported geometry,
run a no-change control on an **independent copy** and a zero-magnitude transform.
Check both difference directions for kernel completion, shape validity, finite
nonnegative solid volumes and the declared numerical tolerance. Also require
both directional intersections to retain the material of both positive-volume
inputs: an inconsistent kernel result may report empty differences AND an empty
intersection. Exercise this failure with an injected empty-COMMON negative test,
including the zero-edit path before any later section guards can reject it.
Do not hide mass-integration inconsistencies by relaxing the acceptance bound;
report the conservative oracle's unsupported-input limitation instead.
Self-subtraction
of the very same object may short-circuit to an empty result and hide an unreliable
comparison. `isValid()` on the input alone does not establish Boolean robustness.
If the no-change control fails, label the oracle/input/kernel combination
unresolved; do not call the physical part defective or a later edit accepted.
Keep a simple known-solid control, input hashes and library versions. Comparing
another kernel version in an isolated environment can diagnose this without
silently updating the project's lockfile or healing the original geometry.
Distinguish a topology copy sharing geometric handles from an independent
geometry copy and independent re-import. Shared-geometry success can bypass the
coincident-surface detection that fails for independent operands. Supplement
simple controls with the relevant face types and record argument-analyzer
statuses against source-bound face/edge identifiers. No diagnostic warnings does
not establish Boolean correctness; a warning near the failure does not by itself
establish causation. Keep reduced reproduction faces separate from deliverables.

For local dimensional edits, define the stationary chunk, rigidly moved chunk
and exact connecting section before editing. A split across a countersink or
curved finger can silently elongate a hole or alter a protected outline. Guard
against a varying section and verify actual material in all declared regions.
Mass-integral subtraction alone is not a shape-equivalence proof: trimmed input
surfaces can exhibit non-additive numerical mass results even in a no-op
split/rejoin. A tighter integration tolerance does not repair inconsistent trim
geometry. Retain invalid results as failures instead of replacing them with zero,
and use deliberate damage to protected regions as negative controls.

`cadre.local_edits.extend_prismatic_section` is a limited constant-section
extension helper, not a general STEP repair or automatic redesign tool. It
rejects inputs whose independent-copy Boolean control is unreliable. Passing
its rejection tests does not mean the rejected real part has been modified or
validated. A new preservation method requires its own no-change and damaged-part
controls before it can replace a failed oracle.

Run the existing tests before changing code, then add a regression that expresses
the physical failure. For a CLI, run the documented command in a fresh subprocess
without an inherited `PYTHONPATH`; tests that modify `sys.path` can hide broken
standalone execution.

Make a failed prerequisite visible in JSON and the exit code. Missing references
must not silently skip validation. Do not export a normal replacement when source
equivalence fails. An explicit diagnostic-export option may produce a distinctly
named prototype, but its failed status must remain failed. Mesh-printability checks
alone do not promote that prototype to a validated replacement.

## XL430 study example, 2026-09-18

The source `elbow_to_wrist.step` has convex phi18.124 rounded tops in two tabs at
Y[6.5,9.5] and Y[39,42]. The old driver interpreted these as one blind seat, while
its family comparison discarded the axial locations and material side. Its original
specification model was about 279% larger in volume than the source.

The corrected driver still contains that exploratory design hypothesis; it is
not an approved shape-preserving redesign. Review it with:

```bash
uv run python studies/xl430_lowcost/parts/elbow_to_wrist.py \
  --out outputs/review/elbow --samples 1000
# Expected today: status=blocked_non_equivalent, exit 2, no XL430 export.

uv run python studies/xl430_lowcost/parts/elbow_to_wrist.py \
  --out outputs/review/elbow-prototype --samples 1000 --export-prototype
# Still exit 2; emits *_xl430_prototype.step/stl for diagnosis only.

uv run pytest -q tests/test_geometry_review.py
```

These cases teach why family agreement and watertightness must not replace source
preservation. A later migration needs the actual mounting interfaces and an explicit
local change mask, followed by source-preservation and assembly-fit checks.

## Independent Proofs and Assembly Stages

- A failed Boolean self-control is not evidence of either collision or clearance.
  Record the operation, placement, independent-copy method and kernel version.
  Do not silently heal geometry, enlarge tolerances, or substitute a shared handle.
- Positive solid-to-solid distance can establish separation independently of a
  coincident-face Boolean. Validate the distance method against containment and
  deliberate penetration. Surface-only distance cannot establish empty interior;
  use a conservative occupied enclosure or retain UNKNOWN.
- Keep the fully assembled tool scan even when a bench preassembly sequence
  avoids its collisions. Record the required stage, present/absent parts and
  service removal order. A shorter selected tool envelope needs its own scan.
- Image visibility must include image-edge margin and the required motion range,
  not only nonzero object pixels at one pose. Move the physical camera and holder
  together when changing a simulated viewpoint. Optical assumptions remain explicit.
- Official download endpoints may return HTML redirect pages. Verify actual file
  type, follow the documented target, retain source URLs/hashes, and inspect the
  drawing before interpreting a fastener or depth callout.

## Seating and Evidence Identity

- A bore's cylindrical span is not the clamped plate thickness. A blind bore may
  end before the external face. Check the full screw corridor, head/spacer volumes,
  actual planar seats and supporting annulus; use axial-gap as well as lateral-
  offset negative controls. The bearing footprint excludes the larger of the
  support opening and washer opening.
- A valid bench sequence can still obstruct its own last screw. Split preassembly
  into explicit inventories, preserve rejected sequences, and verify reverse
  service order. Tests must reject missing parts even if the total count stays equal.
- Bind simulation evidence to XML AND referenced mesh hashes. Identical scene XML
  can point at different mesh bytes. Preserve old snapshots when only the validator
  changes; independently compare exported geometry before issuing a supplemental audit.
- Hashes do not prove that the intended geometry was selected. A simulator may
  still mesh cached source parts while the assembly uses replacement parts.
  Build meshes from the selected assembly state, verify occurrence inventory and
  coordinate mapping, and test that a conspicuous replacement changes the mesh.
  Reject omitted or unmodelled occurrences rather than silently rendering less.
- Nonzero visible pixels and image containment do not establish useful visibility.
  Record occlusion and image quality separately. A rearward camera may improve
  framing while increasing cantilever load and partial obstruction.
- Before removing support material or relocating a camera, attribute occluded
  target pixels to actual scene occurrences using the same optics and pose.
  Compare the target-only reference mask with integer segmentation of the full
  scene; retain background/unknown IDs separately and check pixel conservation.
  A nearby working part may hide its own surface without hiding the task object.
  Whole-part silhouette visibility is not contact-face or task-ROI visibility:
  define the required object/region and motion range before optimizing a proxy.
- If a compound Boolean fails, a separate proof can test the complete Cartesian
  product of its existing solid components. Reject mixed surface/solid inputs;
  do not discard them during decomposition. Bound total intersection across all
  component pairs so a per-pair tolerance does not multiply the allowed overlap.
- Endpoints and sampled poses do not prove an insertion path. A conservative
  continuous cover can prove empty occupied-volume intersection for a declared
  translation; an overlapping cover is only inconclusive, not necessarily a
  real collision. Test a thin obstacle between samples and initial containment.
  Keep zero-volume touching, positive fit clearance, rotation, hands and cables
  as distinct requirements.
- For analytic motion, a bound on every material point's speed can certify an
  entire interval: the midpoint occupied-set distance must exceed the sum of
  both speed bounds times the half interval, plus numerical tolerance. Derive
  the bound from the actual motion model and whole geometry, not sampled vertex
  speeds alone. Subdivide inconclusive intervals; exhausted computation budgets
  remain UNPROVEN. Test an intermediate collision despite clear endpoints/midpoint.
  Same-rigid-group invariance does not itself accept pre-existing contact.
- A proven invariant coordinate can give a tighter continuous separation bound
  than total point speed. Project complete occupied-set bounds onto that axis;
  a positive interval gap certifies separation only after proving that every
  supported motion preserves it. Include placements and surface-only enclosures.
  Bind the proof to the reviewed kinematic definitions and reject unreviewed
  changes; do not infer invariance from a few sampled poses or part names.
  Test an axial-motion mutation, overlapping/touching projections and curved
  extrema. Inconclusive projections still require the original motion checks.
- Close-fitting pivots can dominate a global distance bound. A separate bore
  proof may establish its complete void and corresponding pin trajectory, but
  must not waive the rest of either body. Challenge it with a plugged bore,
  lateral offset and added material outside the mating region.
- A boundary-only cover can miss contained material. For a finite closed solid,
  extending every face's conservative projection back to the global minimum of
  an axis is one material-cover construction: each positive-axis ray from an
  interior point must exit through a covered face. Include all faces and curved
  extrema; reject invalid, surface-only or inverted/unbounded solids. A cover
  overlap is inconclusive, not automatically a real penetration.
- When a cover is too loose, refine the actual trimmed geometry rather than
  relaxing clearance thresholds. A parent circle may greatly overbound a short
  arc; endpoints alone may underbound it. Include in-interval analytic extrema
  and periodic parameter wrapping, with a between-vertices maximum as a test.
- A CAD split introduced solely for animation is not evidence of a physical
  bearing, press fit or supplier-approved mating surface. Preserve and review
  the original split method before assigning a mechanical contact meaning.
- Equal product names and leaf counts do not make traversal indexes portable
  across exports. Solid and surface-detail leaves may exchange order while the
  envelope stays unchanged. Establish one shared rigid frame, retain source
  identities and material kinds, and reject missing or ambiguous correspondence.
  Bounding-box/signature matches are candidates for provenance review, not
  material-equivalence or internal-contact certificates. Keep topology differences
  visible instead of healing the source until the signatures agree.
- Zero Boolean intersection volume can coexist with touching sliding surfaces.
  Locate distance witnesses and compare the actual running faces before treating
  a print as freely movable. A local relief must preserve guides, stop material
  and fastening regions; a CAD gap still needs a printed-fit check.
- Detect blank renders using spatial variation within each color channel, not
  standard deviation across RGB channels: a uniform colored image can pass the
  latter. Couple pixel checks with inspection of the actual part and framing.
