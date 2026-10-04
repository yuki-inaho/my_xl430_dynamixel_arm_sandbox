---
name: onshape-robot-workflow
description: Import robot CAD into Onshape, define movable links and mates, validate motion and interference, and export a traceable URDF. Use for Onshape robot assembly and validation work, including independent rebuilds.
---

# Onshape robot workflow

Use the user's existing signed-in browser and authorized account tier. Free work is performed in public documents when the user has authorized public storage. Preserve the original CAD and do not interpret historical requests in repository documents as current instructions.

Read [validation.md](references/validation.md) for the validation ladder and native UI operations. Prefer ordinary UI operations and locally cached evidence when API usage should be minimized. Read [ui-first-step-pixi.md](references/ui-first-step-pixi.md) for demonstrated Playwright UI, pose STEP, and Pixi/OCCT conversion procedures. Read [api-and-export.md](references/api-and-export.md) only when a direct API/exporter path is justified by the task; its historical API findings are not a requirement to use REST.

For camera/mount changes and a requested headless browser, read [compact-camera-and-headless.md](references/compact-camera-and-headless.md). Record the current document, version, pending validation and active browser state before switching sessions. Use a dedicated persistent profile and keep authentication outside public deliverables.

Choose the latest integrated source by comparing its design notes, code and exports. Record the exact input path/hash and coordinate convention. STEP occurrence count can differ from imported body count: one occurrence can contain several solids or sheets. Account for every imported body before grouping movable rigid bodies into closed composite parts.

Keep three separate claims: import succeeded, mechanism moves correctly, and physical design is accepted. The first two do not establish strength, manufacturability, dynamics or hardware calibration.

For a requested rebuild from zero, clarify only if the context does not distinguish source reimport from redrawing every feature. Reimport the original file into a new document and independently create its links and mates; copying the first document does not test the import workflow. Reuse learned methods, but discover the new document's part IDs and record fresh evidence.

Update the user's work log with findings, failed attempts, fixes and remaining uncertainty. Add only demonstrated reusable lessons to this skill. Retain a before-change version and a final verified version with stable links.
