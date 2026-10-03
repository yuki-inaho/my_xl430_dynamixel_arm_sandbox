# REST and export lessons (observed 2026-09-26)

These are historical API-path observations. A later low-profile study completed document creation, import update, grouping, mates, validation, version/STEP/URDF export and local FK checks with **zero direct Onshape API calls**. Prefer [the UI-first route](ui-first-step-pixi.md) when conserving API quota. Native URDF export exists in the tested Free UI; inspect the actual result rather than assuming either absence or correctness.

Use https://cad.onshape.com/api/openapi and the official Developer API documentation to check current schemas. Cache large featureSpecs locally instead of repeatedly downloading or dumping them. Observe the account's API quota; helper-call counts exclude exporter calls and are not the official usage total.

For browser file upload, use either the CLI upload workflow or a Playwright filechooser/setFiles workflow once. Mixing them can create duplicate import dialogs. For robot STEP, “Combine to a single Part Studio”, preserved orientation and no automatic composite provided a manageable import to classify into links.

REST write calls using an ordinary browser session returned 401 in this experiment; a dedicated official read/write API key worked. Keep credentials in a protected local file or environment, separate from public deliverables. Never include keys in generated scripts, URLs, screenshots or logs. A task-specific key did not need delete, purchase, sharing or profile permission.

API v17 features use btType; legacy featureSpecs may use type/typeName/message. Converting legacy defaults requires converting `{"type":0}` to null. Do not indiscriminately reuse every default parameter.

For matched same-direction explicit mate connectors, `primaryAxisAlignment=false` preserved orientation; true flipped the second axis. Verify the resulting assembly transforms, as the appropriate value depends on connector orientation.

Critical limit finding: with v17 BTMMate and BTMParameterNullableQuantity, setting only `expression` while leaving `value=0` and empty `units` showed the desired text but motion was blocked. Supplying consistent expression, numeric value and units restored motion: e.g. expression `65 deg`, value `65`, units `degree`; or expression `16.45398 mm`, value `16.45398`, units `millimeter`. Supply only relevant limit parameters. Always verify movement and achieved matevalues after writing limits. Treat this as observed behavior for this API path, not a guarantee for other quantity types.

Instance insertion can return a null body on success. Refetch the assembly to obtain IDs and verify instance counts before retrying. Version creation needs documentId and workspaceId in the body, not just did in the URL. Use ledgers and readback to prevent duplicate feature creation after ambiguous outcomes.

onshape-to-robot 1.8.3:
- Tree mates named `dof_<joint>` define export joints; explicit connectors determine axes and origins. Named fixed tree mates preserve desired camera links.
- `closing_<name>` point closures export paired frames; ordinary URDF cannot impose the nonlinear closed-loop constraint. Supply a tested joint-state mapping or simulator equality model separately.
- No density in the source yielded hasMass=false. `no_dynamics=true` exports zero inertial values; this is a kinematic model, not calibrated dynamics. Preserve raw export, then make a clearly identified portable kinematic URDF with unresolved mesh paths fixed and invalid zero inertials omitted.
- Default `package://assets/...` lacks a ROS package name. Choose an explicit package or create a portable relative-path variant and verify files resolve.
- Compare against the actual exporter output and keep raw provenance. Do not silently substitute an older robot URDF.

Official references:
- https://onshape-public.github.io/docs/
- https://www.onshape.com/en/products/free
- https://www.onshape.com/en/resource-center/tech-tips/import-options-use-cases
- https://onshape-to-robot.readthedocs.io/en/latest/design.html
- https://onshape-to-robot.readthedocs.io/en/latest/kinematic_loops.html
