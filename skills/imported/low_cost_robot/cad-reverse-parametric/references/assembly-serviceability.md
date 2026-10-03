# Assembly and serviceability evidence

Read this for fastening, assembly order, tool access or wiring around a moving
assembly. Keep project dimensions, part IDs and hardware-specific limits in the
study's configuration and report, not in this reusable procedure.

## Fastener record

For every modified joint, record the occurrence path and mating components,
fastener standard/part number, thread diameter and pitch, head/drive geometry,
washer/spacer stack, receiving thread, insertion side, tool, counter-holding
method, and assembly stage. Give every value a source and a status: measured,
supplier-specified, CAD-derived, assumed or unknown. Inventory unreviewed joints
explicitly; a check on one added bolt is not a whole-assembly fastening approval.

A smooth cylinder or a part name containing `M3` is not proof of a usable thread.
STEP leaf count is not screw quantity: one physical fastener can have multiple
solid/surface leaves. Supplier motor-internal screws are not automatically the
external bracket's fastening BOM.

Derive penetration from actual seating and thread-entry planes, including any
recess below the mounting face. Check minimum usable thread engagement and
maximum insertion/bottom clearance independently. Do not count chamfers,
unthreaded relief or a smooth CAD bore as fully engaged thread. Tightening torque
requires the real screw/receiver/material specification; do not infer it from
diameter or from an unthreaded visualization model.

Changing a flange's diameter or replacing it with a small compression tube can
change its seating face. Intersect the actual trimmed planar faces to measure
contact area; a bounding-box extreme or the old flange datum is not sufficient.
Record partial contact separately from full contact and bearing-stress approval.
A metal compression path may avoid clamping a printed guide, but does not by
itself establish the receiver's strength, retained clearance or axial support.

## Separate final fit from assembly motion

Distinguish placement errors from envelope or seating errors before cutting a
link. Recover the actual output/idler axis from identified cylindrical faces,
cross-check it against the mating part, and measure seat planes separately.
An assembly-node origin is not automatically a functional mounting datum.
Collinear rotation axes still allow axial seat, bolt-pattern and case-width
mismatches.

For each mating face, compare the complete fastener pattern bijectively in the
same physical coordinate frame, then check the actual opposing seat planes and
their trimmed contact area. Do not independently recenter both hole patterns:
that would erase a real assembly offset. Bind the result to the source occurrence
and record which physical part supplied each seat. A geometry-only pass must
leave receiving threads, tolerances, preload, tool access and strength unresolved
until those have their own evidence. Do not enlarge holes merely to absorb a
pattern error; record any authorized diameter change as a separate local feature
decision tied to the selected fastener and preservation mask.

When changing a link length, identify which end stays fixed and which dependent
subassemblies move. Do not apply a downstream translation to the motor anchoring
the fixed end. Derive a regression oracle from the independently placed baseline
components, not from the same hand-written transform list as the generator.
Check both geometry identity and each occurrence's placement; a preserved shape
in the wrong coordinate frame is not a preserved assembly interface.

1. Check the complete saved assembly, with actual occurrence transforms and all
   retained neighbours. Recheck after motor substitutions; baseline approvals
   do not transfer to a larger motor or relocated connector.
2. Define staged insertion and removal paths for parts, washers and fasteners.
   A collision-free seated part may be captive or impossible to insert.
   Installing the first captive part does not prove that the next motor/link can
   enter. Splitting a part does not prove that both resulting pieces can enter.
   Evaluate the entire dependency chain, using every already-installed component
   as an obstacle and checking the final inventory against the declared scope.
3. Check drive engagement, straight approach, turning motion and withdrawal.
   An L-key, screwdriver, bit holder and ratchet have different swept volumes.
   Include holder/handle and a declared finger clearance, not only the bit tip.
4. Check access again after cables and strain-relief hardware are present.
   If another part must be absent, record that assembly precedence and the
   required disassembly for later service. Check a second tool for a held nut.
5. Check what tightening actually clamps. A shoulder/spacer intended to leave a
   joint free must remain proud after tolerances, compression and washer bending;
   nominal positive play alone does not prove freedom under preload.

Use explicit local head/seat axes transformed to assembly space. For a straight
driver, a circumscribed circular shaft plus a cylindrical handle/hand envelope
can conservatively cover axial insertion and full rotation. Expand by the
declared clearance margin. Such a cylinder is not a model of L-key rotation or
unrestricted human access. Distinguish a sampled path from a continuous swept
volume; report sample spacing and do not call samples exhaustive.

For fixed-section extrusions translated along their extrusion axis, extending
each axial interval by the translation distance gives an exact swept set; sweep
distributes over a union of such constituents. Bind that construction to the
actual nominal part and supported path. Do not reuse it for another direction,
rotation or arbitrary imported shape. Test an obstacle between sample positions
to distinguish sampled clearance from continuous evidence.

Treat supplier assemblies as supplied units only when their boundaries are
known. Multiple solids in one imported node do not identify removable subparts.
If a new support removes a thrust face or changes retention, document the lost
function and its replacement load path, even if insertion and hole sizes pass.

Exclude only the precisely identified intentional mating volume or the specific
not-yet-installed component at a documented stage. Excluding an entire motor,
link or all adjacent fasteners can hide a real access failure. Report contact,
interference and clearance separately, with units and tolerances.

## Cable and connector gates

- Locate the actual header occurrence, outward insertion axis and mating-plug
  exit plane. A cable beginning at a PCB origin can falsely run inside a case.
  Include plug housing, boot and unplugging/grasping space before accepting fit.
- Use measured harness dimensions and a manufacturer bend limit when available.
  A round envelope around a flat bundle is conservative, not exact cable CAD.
  Record envelope collisions without silently shrinking it or ignoring cases.
- Use controlled tangent lines/arcs or check curvature on the whole chosen path.
  Free splines can overshoot control points and form tiny bends. Reject legs
  too short for the required radius instead of silently reducing it.
- Reserve service loops and strain relief on each side of a moving joint.
  Check pinching, torsion, tension and external obstacles throughout the stated
  motion range. Static path length is not a finished cable cut length.
- Keep electrical evidence separate: pinout, supply range, branch current,
  connector/contact rating, voltage drop, protection and return path. Same
  voltage does not prove that one daisy-chain can carry summed motor current.
  Multiple injection points are not a complete power-distribution design.

## Regression and reporting

Add negative cases before accepting the checker: an obstacle on the shaft path,
an obstruction touching only the handle, a cable blocking an otherwise accessible
bolt, an overlong screw and an insufficient bend radius. Keep the thresholds
unchanged between deliberately failing and passing fixtures. Distinguish a
missing-function RED from a physical negative case tested by the finished code.

Bind reports to input STEP/configuration hashes and record geometry inventory,
units, source transforms, exclusions and stage. A valid export or a successful
browser load is not engineering approval. Show diagnostics in a separately named
unaccepted artifact, preserve the user's existing browser tabs, inspect screenshots
and DOM ownership, and keep release blocked for failed or unknown prerequisites.
Independent binary gates help prevent a local tool-clearance pass from concealing
unresolved assembly, thread, wiring, load or motion failures.
Report unsupported paths and unplanned occurrences explicitly. An unchanged
occurrence count can hide a replacement or omission; compare identities and
preserved geometry, not counts alone.

For a placement repair, compare complete before/after collision pair identities:
removed, retained and newly introduced. A lower count can conceal a new connector
collision or greater penetration at a retained pair. Bind each scan to its own
exported STEP hash and keep old assembly/tool/cable reports scoped to their old
revision until rerun. Round-trip bounding boxes, areas, volumes and face-family
counts are useful checks but are not a complete arbitrary-shape equivalence proof.
