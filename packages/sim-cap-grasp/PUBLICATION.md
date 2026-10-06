# Public integration — 2026-10-06

This is the technical GitHub snapshot of the reviewed random-grasp study.
It adds the executable study, focused tests, portable skills, workdoc/review,
100-trial and 335-proposal CSVs, and three synthetic screenshots. The unchanged
nominal model, preserved source assets and lock are inherited from base
`14577ac40ff059513ff6633f7331665f9755be75`.

Full saved states, contact logs, source freezes, videos and full HTML were
independently audited locally. They remain in the verified integration bundle;
they are not included in this public snapshot. Summary CSVs and images alone
cannot reproduce that historical audit. A fresh dynamics run is reproducible
using the commands in RANDOM_README.md, subject to platform differences.

Local full integration commit: `3553a1ecf7838105bb48381e7bf5cf6751df6f92`.
Its two intermediate commits were autosquashed/rebased onto the published base.
Tree `5709c9d9cdf9a84fa2b6e81e63df7e29afb81921` remained unchanged by rebase.
Real Git notes are attached to that local commit under `refs/notes/commits`.
The public snapshot has a different tree and commit identity. The portable note
copy is PUBLICATION_NOTES.json; that file is not a remote Git notes ref.

Bundle: 2,055,751,820 bytes.
SHA256: `a58af281d4664bf394ca4a3ab09d46cd024e02e736a11697741dc2794d692904`.
Bundle verify and actual branch/notes fetch into a separate receiver passed;
commit, parent, tree, notes and qualification-index hash were checked.
The bundle and source archives are excluded from Git publication.

Qualification-002: 100/100 selected trials SUCCESS, unsafe 0, invalid 0;
independent full-trace audit PASS. This is conditional on the fixed model,
pitch and pre-screen. During lowering 97 trials lose bilateral finger contact,
89 before box contact; maximum pre-box cap-center speed 0.69846 m/s.
Gentle continuously retained lowering remains unproven. Qualification-001 stays
INCOMPLETE (96 SUCCESS, one physical failure, three interrupted invalid traces).
The supplier's original 100 qualification traces were not delivered.

Publication excludes real photographs, conversations, input archives,
machine-specific absolute paths, exception logs and unrelated camera records.
The full staged integration passed private-content/hash checks. The reduced
snapshot is separately checked for content, hashes and valid relative links.
No robot or serial access is part of this integration.

Normal shell Git networking was unavailable in the integration environment.
The GitHub connector publishes a branch from the checked base, followed by PR
review and a single-commit squash merge. No published history is force-pushed.
Merge confirmation and its final GitHub identity are recorded separately after
the operation; this document alone is not proof that a merge has happened.
