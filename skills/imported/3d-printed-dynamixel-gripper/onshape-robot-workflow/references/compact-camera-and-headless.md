# Camera trade studies and headless continuation

These lessons were demonstrated on the 2026-09-26 D405/XL430 study. Values are case evidence, not general design limits.

## Preserve state before switching browsers

Record the document/workspace/element IDs, saved version, exact CAD hash, validation completed and pending, active dialog and tab purpose. Leave pending checks unchecked. Do not close unrelated user tabs.

With Playwright CLI, a separately named session can run headless with `browser.launchOptions.headless: true`, a 1600×1000 viewport and a persistent `--profile`. Confirm `headed: false` using `list`, then verify the signed-in document title, instance count and a real 3D screenshot. A successful launch alone does not demonstrate WebGL rendering. Initial rendering and screenshots can take longer than the command tool's yield; wait for the actual exit status.

When authorized to reuse the login, save storage state inside a private directory, filter cookies and origins to exact Onshape domains/subdomains, and load that state in the dedicated context. Never print cookie values or copy unrelated site state. Use directory mode700 and authentication-file mode600. Keep profile/authentication out of deliverables, repositories and public ZIPs. Preserve the cache when requested. Reuse one profile in only one running browser; on ordinary restarts, keep the profile's current state instead of loading an older snapshot. Expired sessions require login again.

Persistent browser HTTP cache and content-addressed CAD/PDF cache serve different purposes. Record input hashes and cache manifests. Changed CAD requires new validation; stale cached results cannot establish correctness.

## Native validation findings

- To measure an edge, select the actual graphics-area edge, then open bottom-right **Show measure details** (`[`). Check the selected entity text and the length unit. Tree composite selection alone did not populate the tested Measure dialog. A 57 mm straight segment on a 63 mm filleted plate is not the overall plate width.
- All-fixed assemblies show **More than one part is fixed** warnings. Record the hover text. Such an assembly can support static measurement/interference inspection but is not a validated movable mechanism. Ground only the base when constructing motion.
- Six native interference results corresponded to inherited screw envelopes. Retain pair names, pose and selection scope; never delete material simply to obtain zero results. Independently check individual bodies when closed composites may hide internal intersections.
- STEP257 occurrences imported as207 solids and55 sheets. Inventory the262 bodies and assign all exactly once. The document REST field observed for public access was `public`, not `isPublic`.
- Save a version only after evidence is collected and confirm the version exists. A validation name is not itself evidence of strength or motion.

## Mechanical and optical claims

Keep payload, camera group and full-arm mass contributions separate. Sum `(r-r0)×F` in SI units; project onto the joint axis for drive torque. A vertical base drive may have zero gravity torque while its structure still carries bending. Stall torque is not a continuous rating.

Compare height, mass, center of mass, moment, object visibility and joint travel together. In the demonstrated candidate, height decreased9.49 mm and camera-group wrist gravity amplitude decreased6.8%, while mass increased0.18 g and one wrist limit lost4°. Preserve the rejected first candidate and explain the final tradeoff.

Test both eyes using target-object dimensions separately from payload mass. D405 MinZ depends on resolution: the2025-08 datasheet gives70 mm at848×480 and100 mm at1280×720. Marketing and datasheet FOV differ; record source revision and the chosen conservative model. Camera-origin envelope exclusions must be stated. Side-camera concepts rejected before mount design are not fabricated alternatives; a sampled failure does not prove all side placements impossible.

Treat surface-only bbox overlaps as unresolved, not collision-free because volume is zero. Finite joint samples do not prove continuous multi-joint clearance. Equal-section beam sensitivity is not bracket FEA, fatigue or creep certification. Preserve unverified materials, layer orientation, cable loads and hardware screw engagement.

When camera placement, shape or joint limits change, the previous URDF no longer matches. Update meshes, fixed transforms, axis signs, limits and closed-link coupling before claiming the new candidate is exported for motion.

Official references:

- https://cad.onshape.com/help/Content/View/measure_tool.htm
- https://cad.onshape.com/help/Content/View/interference_detection.htm
- https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/
- https://realsenseai.com/wp-content/uploads/dlm_uploads/2025/08/Intel-RealSense-D400-Series-Datasheet-August-2025.pdf


## Carry the final candidate through export

Audit scope after a static design study: an earlier robot URDF does not satisfy an import-to-URDF request for a changed final candidate. Create a separate motion assembly, retain the static evidence, ground only the base, verify all mates and actual movement, restore the baseline, then freeze a version and export that exact version. Preserve raw XML and current-version meshes before portability normalization. Include source/version and output hashes.

In the compact study, 12 composites, 26 connectors and 13 mates produced 16 URDF links/15 joints/12 mesh links. A native reference set of 11 actual poses agreed with URDF FK within 8.551e-6 matrix-element error; the unchanged 441-point gripper closure test stayed below 1e-6 m. Exporter rounding affects mixed rotation/translation matrix elements: never describe that entire error as a distance. Camera body frames are not automatically calibrated optical frames. Keep absent inertia and unknown effort/velocity explicit.

## Verify achieved motion, not just API success

A direct wrist-end-to-gripper-end jump returned HTTP success but missed the requested grip angle by 1.24 rad. Keeping the same acceptance tolerance, recovery reset all five active joints and used at most 10-degree waypoints with readback after every update. Eleven representative poses and 91 waypoints passed. This is an observed recovery method, not a guarantee for every solver or mechanism.

GET feature parameters displayed some limit numeric values as zero with empty units even when expressions and native runtime limits worked. Do not infer immobility from that serialization alone; compare definitions and test actual motion/endpoints. Earlier failed constraint cases still justify explicit quantities when creating features, but their cause must not be generalized to every later readback.

## Distinguish CAD preservation from mesh identity

Re-exporting a rewritten STEP can produce different tessellation. The compact study had eight unchanged links with identical vertex positions; forearm/wrist had vertex differences up to 9.28/18.77 micrometres and bidirectional vertex/triangle-centroid surface samples up to 0.35/0.71 micrometres. Strict old-mesh identity checks failed and remain recorded. Current meshes were not replaced with old ones; no identity tolerance was relaxed.

Establish provenance separately: inspect the construction that reuses source BReps, compare STEP occurrence membership and the existing roundtrip volume/bounds criteria, and verify current-version URDF/mesh hashes and changed origins/limits. Bounds and volume alone do not prove complete surface identity. Nearest-triangle computations on tiny triangles can be scale-sensitive; record method and units and do not turn a numerical diagnostic into a geometry assertion without controls.
