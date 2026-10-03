"""cadre — generic CAD reverse-engineering & parametric reconstruction toolkit.

Layering (SOLID): this package is the domain-agnostic core. It never references
a specific part file or a specific servo. Studies build on top of it.
"""
from .geometry import (Envelope, Component, FitResult, classify_screw,
                       DEFAULT_SCREW_BANDS)
from .probes import (KeywordPolicy, step_text_probe, stl_geometry_probe,
                     brep_probe, brep_available, group_cylinder_holes,
                     cylinder_faces, edge_records, match_edge_lengths)
from .equivalence import compare, verdict, EquivalenceThresholds
from .impact import (Classifier, RuleClassifier, ImpactConfig, analyze_tree)
from .intent import PartIntent, Feature
from .descriptor import feature_descriptor, to_prompt
from . import parametric, report, checks

__all__ = [
    "Envelope", "Component", "FitResult", "classify_screw", "DEFAULT_SCREW_BANDS",
    "KeywordPolicy", "step_text_probe", "stl_geometry_probe", "brep_probe",
    "brep_available", "group_cylinder_holes", "cylinder_faces", "edge_records",
    "match_edge_lengths", "compare", "verdict", "EquivalenceThresholds",
    "Classifier", "RuleClassifier", "ImpactConfig", "analyze_tree", "PartIntent",
    "Feature", "feature_descriptor", "to_prompt", "parametric", "report", "checks",
]
