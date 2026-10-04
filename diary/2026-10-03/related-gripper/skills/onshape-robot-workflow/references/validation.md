# Native validation and evidence

1. Import errors: inspect import feature status, missing bodies, solids versus sheets, coordinate orientation and scale. Save a reference version before editing.
   Wait for the translation request to reach DONE. A Part Studio can appear while translation is ACTIVE and more source tabs can still be created. Select the integrated studio by body inventory, not its temporary name alone.
   After asynchronous import/API edits, tree readiness is not graphics readiness. In the rebuild, a forearm body was absent visually although present in exported geometry; reloading restored it. Wait for geometry before Zoom to fit and final screenshots.
2. Rigid-body membership: assign all bodies exactly once. A closed composite improves manageability, but can hide internal part intersections from inter-instance checks.
3. Mate errors: all mates must resolve. Ground only the intended base. Check type, axis, owners, limits and suppression. An all-OK static assembly may still be immobile or have wrong pose.
4. Pose: compare occurrence transform matrices with the imported reference. A constrained occurrence transform API call can return successfully without restoring pose. Native mate context-menu **Reset** restored the reference in the initial experiment; verify numerically afterward.
5. Motion: use mate context menu **Animate…**, a bounded start/end and steps. Verify the Current value actually changes. A blank value plus “Unable to compute any steps ... Instance(s) may be constrained” is failure, even if all mate statuses say OK. Verify achieved endpoint/midpoint poses numerically from UI-exported STEP placements when possible. If a justified API path is used, inspect achieved matevalues; HTTP 200 alone is insufficient. Animate may restore the initial pose when closed.
6. Interference: open the bottom-right analysis menu → **Interference detection…**. Select the intended instances (first tree item, Shift+last for a contiguous range). Record selection scope, pose, result count, instance pairs and screenshots. Hover/click each result to inspect the highlighted overlap. Thread engagement and press fits require interpretation; do not remove expected material merely to obtain zero results.
7. Export: validate URDF topology, mesh references, SI scale, zero-pose agreement, axes and limits. A closed loop flattened to a tree needs external joint-state coupling; coincident frames at zero do not prove it closes across motion.

Onshape API matevalues describes the first connector relative to the second. In the tested same-direction connector assembly, a native/URDF positive coordinate drove the child opposite the CAD positive axis. Derive and test the sign with a small positive motion; do not copy limits without conversion.

Diagnostic evidence has scope. Three gripper poses do not establish a collision-free continuous sweep of the whole arm. Displayed meshes are not necessarily suitable simulation collision geometry. Source motor models may combine the rotating horn and fixed case; grouping them as one coarse visual must be disclosed.

The independent rebuild showed two additional reproducibility issues. When requesting a gripper pose, explicitly include the desired positions of other free arm mates; otherwise solver motion can slightly change their pose. Reimported STL bytes can differ solely by triangle ordering: compare geometry (bidirectional vertex distances, triangle count and area), not only file hashes. Compare rotations as matrices rather than literal RPY strings, because +/-pi and export rounding can produce different text.

Official references:
- https://cad.onshape.com/help/Content/View/interference_detection.htm
- https://cad.onshape.com/help/Content/Assembly/mates.htm
- https://cad.onshape.com/help/Content/Home/error_indicators.htm
- https://www.onshape.com/en/resource-center/tech-tips/precisely-position-mates
