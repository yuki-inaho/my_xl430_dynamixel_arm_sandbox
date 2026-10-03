"""Build a compact, structured feature descriptor for LLM design-intent labelling.

The right division of labour (per the design-intent methodology): do NOT hand a
raw STEP to an LLM. Extract structure deterministically (Python/B-rep), then ask
the LLM only to *name the intent* of each feature and map it to CadQuery function
+ parameter names. This module produces that structured hand-off.
"""
from __future__ import annotations
import json


def feature_descriptor(brep_result: dict, adjacent_parts: list[str] | None = None,
                       filename_hint: str | None = None) -> dict:
    """Turn a `brep_probe` result into the compact descriptor an LLM labels."""
    faces = []
    for fam in brep_result.get("hole_families", []):
        for center in fam["centers"]:
            faces.append({
                "radius": fam["radius"],
                "diameter": fam["diameter"],
                "screw": fam["screw"],
                "axis": fam["axis_dir"],
                "center": center,
            })
    return {
        "part": brep_result.get("name"),
        "bbox_mm": brep_result.get("bbox_mm"),
        "solids": brep_result.get("solids"),
        "cylindrical_axes": faces,
        "adjacent_parts": adjacent_parts or [],
        "filename_hint": filename_hint or brep_result.get("name"),
    }


LABELLING_PROMPT = (
    "You are given structured CAD features extracted from a STEP part (radii, "
    "axes, centers, bbox, adjacency, filename hint). For each cylindrical axis and "
    "the part overall, infer the DESIGN INTENT: what the feature is for (e.g. "
    "servo mounting hole, output-shaft bore, idler support, cable relief), which "
    "axis/dimension is the reference, and which features must move together when a "
    "parameter (e.g. the servo model) changes. Output a PartIntent: features[] with "
    "{name, type, servo?, preserves[], constraints{}} and tests[] (named checks). "
    "Map each to a CadQuery function name + parameter names. Do not restate raw "
    "geometry; produce the intent layer."
)


def to_prompt(descriptor: dict) -> str:
    return LABELLING_PROMPT + "\n\nFEATURES:\n" + json.dumps(descriptor, indent=2)
