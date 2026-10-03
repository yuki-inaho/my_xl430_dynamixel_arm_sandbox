"""Generic impact-analysis orchestrator (dependency-inverted).

Walks a part tree, runs the probes, and applies an *injected* classifier and an
optional target `Envelope` for fit-checking. Knows nothing about servos — the
study layer supplies the keyword policy, the classifier rules and the target.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import Protocol, Callable

from .geometry import Envelope
from .probes import (KeywordPolicy, step_text_probe, stl_geometry_probe,
                     brep_probe, brep_available)


class Classifier(Protocol):
    def classify(self, text_probe: dict) -> str: ...


@dataclass(frozen=True)
class RuleClassifier:
    """Ordered rules; first matching rule's label wins. Fully generic."""
    rules: list[tuple[str, Callable[[dict], bool]]]
    default: str = "indirect"

    def classify(self, text_probe: dict) -> str:
        for label, pred in self.rules:
            if pred(text_probe):
                return label
        return self.default


@dataclass
class ImpactConfig:
    classifier: Classifier
    keyword_policy: KeywordPolicy | None = None
    target_envelope: Envelope | None = None
    assembly_size_bytes: int = 1_000_000
    tier_order: list[str] = field(
        default_factory=lambda: ["direct", "likely", "review",
                                 "indirect", "assembly_reference"])


def analyze_tree(parts_dir: Path, config: ImpactConfig,
                 use_brep: bool = True) -> dict:
    parts_dir = Path(parts_dir)
    steps = sorted(parts_dir.rglob("*.step"))
    stls = sorted(parts_dir.rglob("*.stl"))
    do_brep = use_brep and brep_available()

    step_rows, brep_rows, stl_rows = [], [], []
    for sp in steps:
        t = step_text_probe(sp, config.keyword_policy)
        if sp.stat().st_size > config.assembly_size_bytes:
            step_rows.append(_row(sp, parts_dir, "assembly_reference", t, None,
                                  config.target_envelope))
            continue
        impact = config.classifier.classify(t)
        b = brep_probe(sp) if do_brep else {"available": False}
        if b.get("available"):
            brep_rows.append(b)
        step_rows.append(_row(sp, parts_dir, impact, t, b, config.target_envelope))

    for mp in stls:
        s = stl_geometry_probe(mp)
        s["rel"] = str(mp.relative_to(parts_dir))
        if config.target_envelope:
            s["fit"] = config.target_envelope.fits_inside(s["bbox_mm"]).__dict__
        stl_rows.append(s)

    return {"steps": step_rows, "brep": brep_rows, "stls": stl_rows,
            "tier_order": config.tier_order}


def _row(sp: Path, root: Path, impact: str, t: dict, b: dict | None,
         target: Envelope | None) -> dict:
    fit = None
    if b and b.get("available") and target:
        fit = target.fits_inside(b["bbox_mm"])
    return {
        "name": sp.stem, "rel": str(sp.relative_to(root)), "impact": impact,
        "products": " | ".join(t["products"]),
        "bbox_mm": (b or {}).get("bbox_mm"),
        "faces": (b or {}).get("faces"),
        "cyl_faces": (b or {}).get("cylindrical_faces"),
        "target_fits": fit.fits if fit else None,
        "target_margins_mm": fit.margins_mm if fit else None,
        "keywords": t["keywords"],
    }
