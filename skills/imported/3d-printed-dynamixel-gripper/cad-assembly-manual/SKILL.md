---
name: cad-assembly-manual
description: Create and review illustrated assembly manuals from an existing CAD assembly and repository evidence, with per-step fastener quantities, insertion directions, and readable viewpoints. Use for requests such as 組立マニュアル, どのボルトを何本使うか, or 工程ごとの組立図.
---

# CAD Assembly Manual

Keep this skill project-local. Read repository instructions and the viewer skill before operating a browser. Preserve donor geometry; a manual request authorizes presentation and documentation, not redesign, fabrication, or hardware operation.

## Evidence to procedure

Identify the exact assembly revision and hash. Use its occurrence inventory for quantities and the applicable BOM, source geometry, and engineering records for dimensions and order. A repeated motor label or split fixed/horn model is not another physical motor. Do not import obsolete camera or arm fasteners into a gripper-only manual.

Give each fastener a stable code. Record where nuts are first inserted and where the same nuts are later used; count them once. Reconcile step consumption with the assembly inventory. Distinguish under-head bolt length from a countersunk model's overall length. CAD thread envelopes do not determine purchased thread specifications or torque.

For a novice-facing manual, state diameter, length in mm, and count in each relevant step. Explain shorthand such as M2×6; do not make the reader decode it or return to an appendix to find the length. Give nut/washer thickness where it affects the stack.

Name an unresolved interface at its actual step. Write an explicit conditional procedure where the installation is not verified; do not invent a torque, substitute screw, captive-nut retention method, or insertion path. Existing, case-replacement, and self-tapping holes are different interfaces.

## Pictures that teach assembly

Capture staged **display-only** views. State which parts are hidden and whether a picture is an installed-position diagram, an exploded diagram, or an actual procedure photograph. Do not imply that hiding a motor proves access behind it.

Choose front views for hole patterns and L/R labels, oblique views for depth, and a second view or a clearly labeled schematic for hidden nuts, shoulders, and insertion direction. Highlight only the parts introduced in the step. Match callouts to projected geometry; do not place a label near an arbitrary pixel. Use part codes and text as well as color. A large assembly overview cannot replace a legible fastener detail.

Inspect the rendered images, not just file existence. A drawing must remain understandable at its intended PDF print size. Avoid overlapping callouts, gray parts on gray backgrounds, unexplained arrows, and tiny screw heads. If insertion is unknown, say so; an arrow may describe nominal bolt orientation without asserting collision-free insertion.

For local Chili3D captures, read [references/chili3d-views.md](references/chili3d-views.md) for the observed matrix, occlusion, material, and coordinate-label pitfalls.

## Review and delivery

Use as many passes as the request and findings justify. If five reviews are requested, perform five separate inspect → finding → edit → recheck passes, record the evidence and remaining unknowns, and do not relabel one inspection as five reviews. Suggested distinct passes: mechanical evidence; viewpoints; insertion/stack comprehension; novice instruction and counts; rendered HTML/PDF quality.

Produce an editable source, a browser-readable manual, and a printable artifact when useful. Open the manual in a new tab while preserving the user's CAD tab. Verify image loads, quantity reconciliation, page breaks, Japanese fonts, readable labels, and the actual final PDF. Rendering checks prove document usability, not physical assembly approval.

Keep the main picture adjacent to its action/check text; put supplemental viewpoints after those instructions. Prevent a short quantity ledger from splitting into an isolated tail page. If a print height cap shrinks embedded labels, give the view enough page width and use another page instead of hiding the detail. Offer original-size image links in HTML and page numbers in PDF when useful for cross-reference.

Keep project-specific dimensions and this task's review findings in the manual/evidence directory, rather than hard-coding them into this reusable skill. Update the skill only for demonstrated reusable lessons.
