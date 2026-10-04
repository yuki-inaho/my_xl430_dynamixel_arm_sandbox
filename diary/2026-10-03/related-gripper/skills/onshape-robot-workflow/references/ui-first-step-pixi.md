# UI-first robot validation and local STEP conversion

Observed on 2026-09-26 using a public Onshape Free document, headless Playwright CLI, D405 camera and closed-loop parallel gripper. Recheck current UI names and package availability for a new task. Case values below are evidence, not universal design limits.

## Scope and API budget

Classify a requested operation as: UI available, UI route not yet verified, UI cumbersome, or UI plus local computation available. Do not call the latter three “API required” without investigation. This study completed all Onshape operations with zero direct REST calls. Do not replace REST with `page.evaluate(fetch(...))` against internal endpoints.

The tested official Free API policy listed 2,500 API calls per user per year and excluded normal browser calls. Check the current official limits before advising a future user. A local helper counter is not the account-wide annual usage; retain its starting value and report only the measured delta.

Cache immutable STEP files by source document/version/hash, plus joint settings, parsed placements and screenshots. Browser HTTP cache and authentication state are separate. Do not publish profile/state/cookies. Do not apply a cached result to changed geometry.

## Reliable browser operations

Use an existing authorized signed-in session or a dedicated headless persistent profile. Verify actual WebGL geometry, title, version and instance count. A successful launch, DOM tree or Loading screenshot alone is not rendering evidence.

Serialize all mutations to a shared page. A yielded command is still running; do not start another edit until it exits. Before selecting parts, verify the trimmed feature-dialog title matches the intended group. After each selection, wait for its exact name to appear; after confirmation, reopen/read the stored state.

Use a fresh DOM snapshot and role/name/parent context rather than old element IDs. The `.os-td` cell can receive editing events where the underlying nonediting input is covered. Discover row data IDs in the current document. Do not send name changes and angle changes without waiting for the previous value to persist.

## Import updates and hidden membership errors

Copy workspace → Create public document can preserve a useful mate structure while producing an independent improvement study. This is a copy/update workflow, not a rebuild from zero. Keep the source unchanged and state the distinction.

Part Studio → Import feature context menu → Update accepts a replacement STEP. Confirm translation and inspect all downstream composites. In the observed update, moved camera bodies became unassigned and required explicit reselection. Final Parts 0 / Composite parts 12 was necessary but insufficient.

Identical left/right pads silently exchanged group ownership. Neutral geometry still looked correct. At the open pose, within-group member placement differed by 32.908 mm. Repair both jaw composites by removing the old union token and selecting their exact 12 part names. Repairing one side temporarily caused overlap with the old other-side union. Recheck both sides and all poses before success.

Never derive an entire rigid group's pose from only one representative until every member has been shown to share it. Save wrong exports as negative controls rather than overwriting the evidence. Names may repeat within a group; preserve occurrence count and index, not a name-keyed dictionary that merges duplicates.

## Native poses and validation

Named positions → Add named position → Driving mate selector → enable Z rotation on all five active mates. Enter zero for axes that must stay still, then apply through the row's name-cell context menu. Capture actual state with Update named position and compare all axes.

Shoulder 10° failed as one jump but succeeded via 1° increments. A wrist limit could be reached using Apply limit position → Max Z angle limit, but the solver moved the gripper to -19.022°. Reset the other axis to zero, apply again and recapture. A missing Apply entry can mean the row already equals the current pose. Solver failure and menu absence are different observations.

Mate context Animate reached the requested endpoint but restored the initial pose on close. Save endpoint poses separately. Slow headless animation can continue after a command yield; check Current value, not just elapsed timeout.

Interference detection: select all intended instances and record the exact scope. Inspect each highlighted result. In the study, six inter-instance overlaps corresponded to screw engagement. Rounded bounding-box dimensions were not overlap volume. Closed composites can conceal internal part intersections; inspect source bodies locally too. Neither one pose nor finite samples prove continuous whole-arm clearance.

## Version and UI exports

Create version only after restoring the intended baseline. Wait until version name, model and URL are stable, then capture the final screenshot. A loading screenshot is not an acceptable final image.

Assembly tab context → Export → STEP, AP242, custom units Millimeter, preprocessing None, Y-up off, individual-parts export off, include hidden instances as required by the declared inventory. Record these settings and inspect units, solids/sheets, names and placements after download.

Important observed pitfall: applying a named pose while viewing a read-only Version changed the display, but STEP export still contained its saved neutral pose. Two STEP DATA sections were identical. Return to Main, apply neutral then target pose, and export each pose there. Separately export the immutable final Version's neutral STEP. Confirm actual movement from the file, not the notification or screenshot alone.

The tested Free UI also offered URDF with STL/GLTF/GLB/OBJ. A reference STL URDF ZIP had 19 links, 18 joints, 261 visuals for 262 bodies, no collision elements and unresolved loop artifacts. Do not claim all native URDF exports have those issues; inspect the current model's output. Keep a reference export distinct from a separately validated converter result.

## Pixi and current OCCT

For `yuki-inaho/urdf_from_step`, the tested `codex/pixi-occt8` implementation locks Python 3.12, pythonocc-core 8.0.1 and OCCT 8.0.1 on linux-64. Official stable OCCT V8.0.1 commit was `b8f597c677811d1f9f4d8a97f5ae2825c0353a42`. Conda-forge supplies the compiled kernel; `pixi run build` builds the converter wheel, not OCCT source. Verify current official stable and actual package metadata for future work; search snippets can lag.

From the converter checkout: `pixi install --locked`, `pixi run versions`, `pixi run test`, `pixi run build`. Use `pixi run convert model.step --config config.json --output new-empty-directory`. The manifest option alone does not change the caller's working directory for arbitrary relative command paths. Check loaded `libTKernel` and test the installed wheel outside the source PYTHONPATH too.

Explicit config supplies joint semantics, occurrence membership, frames and limits; a STEP alone does not reliably provide them. Normalize STEP units to mm once, then mesh/URDF to m. Keep repeated names and same-position occurrences. Validate proper rotation matrices, one rooted tree, finite unit axes, explicit limits and exactly one assignment per nonmetadata body. Test mm/inch, nested placements, repeated bodies and multiple solids with real small STEP fixtures.

OCCT 8 SWIG color lookup required the class form `XCAFDoc_ColorTool.GetColor(label, type, color)` in the tested binding. Instance dispatch selected the wrong overload. Keep the failing regression and rerun after correction. A version pin without execution is not compatibility evidence.

Closed loops need cut frames and external nonlinear coupling, not an invented linear mimic. Compare closure over the agreed sample set, and compare FK against actual UI STEP poses with separately unit-labelled translation and rotation errors. In this study 441 states and 11 poses passed; these counts/tolerances are project-specific. Include reversed-axis, wrong-scale and actual membership-error controls. A zero translation multiplied by 1000 is not a valid unit-error control; assert the fixture perturbation is nonzero.

Missing inertia, zero effort/velocity placeholders, surface-only collision meshes and uncalibrated camera optical frames remain explicit limitations. Numerical FK agreement does not establish physical precision, strength, fatigue, friction, dynamics or ROS launch compatibility.

## Deliverable and skill checks

Document the benefit and its cost: the 30°/+20 mm candidate lowered the camera by 12.40 mm, but increased the compared 250 g moment by 9.45% and lost 18° total wrist travel. A shorter holder does not necessarily reduce the whole system's moment.

Human manuals should label actual screenshots, show precise menu/field sequences, and distinguish old diagnostics from the current accepted version. Check image readiness, print overflow, links, PDF page count and a rendered sample.

When the user asks to commit skills, save SKILL.md and every referenced file under repository `skills/`, not only in the machine's global skill directory or a study archive. Preserve source/provenance and verify all paths are tracked, hashes match, and remote HEAD includes them. Keep unrelated preexisting skills and user changes intact.

Official references:
- https://cad.onshape.com/help/Content/Document/document_menu.htm
- https://cad.onshape.com/help/Content/Document/working_with_imported_cad.htm
- https://cad.onshape.com/help/Content/Assembly/named_positions.htm
- https://cad.onshape.com/help/Content/Assembly/mates.htm
- https://cad.onshape.com/help/Content/File/exporting_files.htm
- https://onshape-public.github.io/docs/auth/limits/
- https://github.com/Open-Cascade-SAS/OCCT/releases/tag/V8.0.1
- https://github.com/yuki-inaho/urdf_from_step
