---
name: cad-reverse-parametric
description: Inspect STEP/STL geometry, preserve existing shapes during local parametric edits, and validate fixtures against mating CAD with CadQuery/OCP. Use for CAD reverse engineering, hole identification, fit, interference, assembly and print-readiness investigation.
---

# Evidence-Gated CAD Changes

This project-local copy supplies the generic `cadre` package. Historical robot
studies are NOT bundled. The archived `references/upstream-skill.md` is provenance,
not an executable instruction set for this repository. Project parameters and
acceptance thresholds belong outside this reusable skill.

## Preserve Before Changing

Imported B-rep is authoritative when design history is unavailable. A local request
does not authorize whole-part redesign. Declare a change mask; preserve everything
outside it. Add-on fixtures must not silently remodel their host. If reconstructing,
establish equivalent shape before changing a parameter.

Keep nominal CAD fit, printed fit, strength, access, motion and manufacturing
approval separate. Use authorized nominal CAD dimensions to start a prototype;
do not demand unnecessary physical measurements. Record printed tolerance/fit
checks at trial assembly, without claiming they were measured.

## Inspect

From a repository with the package installed using uv:

```bash
uv run python -m cadre.cli inspect path/to/part.step
uv run python -m cadre.cli edges path/to/part.step --indexes 0,1
uv run python -m cadre.cli edge-match path/to/part.step --lengths 9.146 --tolerance 0.01
uv run python -m cadre.cli equiv original.stl candidate.stl --fail-on-non-equivalent
```

Apply the repository's command wrapper where required. Cylinder families are not
automatically holes: classify concavity, trimmed axial spans and openings. An axis
reference point is not a bore opening. Match occurrences by path, frame and geometry,
not repeated names or an assumed mapping between CAD labels and physical motor IDs.

## Build and Challenge

- Keep domain parameters and source hashes in the project module.
- Export to a unique run directory, re-import, and test exported geometry.
- Require valid positive-volume connected solids for individual printed parts.
  Edge-only contact does not create an integral part.
- Use bad controls: wrong pattern, shifted placement, short screw, disconnected
  solid, failed Boolean, occupied tool corridor. Never weaken a gate to pass.
- Test actual host, mating parts, fasteners and device, not just the local feature.
- Never silently discard surface-only obstacles; use the conservative method in
  [add-on-fixtures.md](references/add-on-fixtures.md) when applicable.

## Review and Handoff

Use the independent playwright-cli skill for browser operations. Verify DOM
inventory, inspect XYZ orthographic and assembly views, and match the exact artifact.
A render is not a clearance proof. Record units, transforms, hashes, exclusions,
errors and unknowns. Do not promote a prototype because rendering or slicing works.

Load references as needed:
- [geometry-review.md](references/geometry-review.md): topology and negative controls.
- [assembly-serviceability.md](references/assembly-serviceability.md): screws/tools/wiring.
- [add-on-fixtures.md](references/add-on-fixtures.md): clamps and staged assembly.
- [chili3d_viewing.md](references/chili3d_viewing.md): inspect the local version first.
- [step-to-slicer.md](references/step-to-slicer.md): print gates; historical study commands need adaptation.
