# Research context: where this skill sits

The "measure → equivalent parametric model → swap parameter" approach is an
instance of an active research area, known under several names: **CAD reverse
engineering, design-intent recovery, feature recognition, CAD program synthesis,
B-rep learning, constraint inference, CAD re-parameterization.**

## The autoencoder framing

| DNN / software-dev analogy | CAD counterpart |
|---|---|
| Autoencoder | read STEP/B-rep/STL → compress to design operations/constraints/function → decode back to CAD code/STEP |
| Latent representation | feature graph, sketch-extrude history, constraint graph, **design-intent graph** (see `cadre.intent`) |
| Decoder | CadQuery / OpenSCAD / FeatureScript / FreeCAD Python |
| Reconstruction loss | bbox / hole-position / axis / volume / surface distance / interference (see `cadre.equivalence`, `cadre.checks`) |
| Refactoring | restructure history/params while preserving shape, function, assembly |
| TDD | write shape/hole/axis/clearance/assembly tests first; keep green through parameterization |

Key point: the latent need not be an opaque vector. For mechanical parts a
**human-readable intent layer** (YAML) is better — that is `cadre.intent.PartIntent`.

## Related work (cited by the advisory)

- **DeepCAD** — CAD as a generative model over sketch/extrude operation sequences (shape autoencoding). arXiv:2105.09492
- **Fusion 360 Gallery** — CAD as a *program* executed in CAD software; 8,625 human sketch/extrude sequences; reconstruct CAD program from target shape. arXiv:2010.02392
- **CAD-Recode** — point cloud → executable Python CAD code; LLM-friendly editing/QA. arXiv:2412.14042
- **UV-Net** — learning directly on B-rep faces/edges/vertices + topology. arXiv:2006.10211
- **SolidGen** — autoregressive direct B-rep synthesis (no history). arXiv:2203.13944
- **BrepGen** — diffusion over structured latent B-rep geometry. arXiv:2401.15563
- **SECAD-Net** — learn sketch/extrude ops for compact, easy-to-edit reconstructions. arXiv:2303.10613
- **MiCADangelo** — editable CAD from 3D scans with explicit sketch-level constraints. arXiv:2510.23429
- **Vitruvion** — parametric sketches as primitives + constraints (intent lives in constraints). arXiv:2109.14124
- **Aligning Constraint Generation with Design Intent** — constraints must capture intent so edits update predictably. arXiv:2504.13178
- **Zero-shot CAD Program Re-Parameterization** — infer *meaningful* manipulation axes; intent depends on real-world meaning, not geometry alone. arXiv:2306.03217

## Why fully-automatic STEP→clean-parametric is still hard

1. **Intent isn't in the geometry.** Which dimension is a free parameter, which
   face is a motor seat, which constraint must hold — none are in the B-rep.
2. **Constraints are hard.** Fully- (not over-) constrained sketches that update
   predictably need more than recovered lines/circles.
3. **B-rep topology is unstable.** A fillet or boolean-order change reshuffles
   face/edge IDs — like untestable side effects in code.

## This skill's stance: semi-automatic refactoring

`B-rep analysis (cadre.probes) + feature recognition (hole families) + LLM intent
labelling (cadre.descriptor) + CadQuery re-implementation (cadre.parametric,
studies/.../connector.py) + TDD diff verification (cadre.equivalence, cadre.checks,
cadre.intent tests)`. Not full auto-generation — the pragmatic, robust middle
ground for real robot parts.
