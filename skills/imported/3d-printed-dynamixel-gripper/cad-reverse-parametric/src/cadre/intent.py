"""Design-intent layer: a human-readable representation that sits between B-rep
extraction and parametric reconstruction.

In the autoencoder framing the user described, this is the *latent* — but kept
deliberately human-readable (YAML), because for mechanical parts a transparent,
editable intent graph beats an opaque vector. B-rep alone carries the final
shape but NOT *why* a hole is there, which face is a seat, which dimension is a
free parameter, or which constraint must be preserved. That semantic layer lives
here.

Generic on purpose: a `Feature.servo` is just a string label; no servo logic
leaks into the core. The study layer fills the values and decides what they mean.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml


@dataclass
class Feature:
    name: str
    type: str                                   # e.g. servo_mount, bore, structural_beam
    servo: str | None = None                    # opaque label, resolved by the study
    preserves: list[str] = field(default_factory=list)   # invariants to keep
    constraints: dict = field(default_factory=dict)      # numeric drivers


@dataclass
class PartIntent:
    part: str
    intent: str
    features: list[Feature] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)       # named checks to enforce

    # --- YAML round-trip ---

    @classmethod
    def from_dict(cls, d: dict) -> "PartIntent":
        feats = [Feature(**f) for f in d.get("features", [])]
        return cls(part=d["part"], intent=d.get("intent", ""),
                   features=feats, tests=d.get("tests", []))

    @classmethod
    def load(cls, path: str | Path) -> "PartIntent":
        return cls.from_dict(yaml.safe_load(Path(path).read_text()))

    def to_dict(self) -> dict:
        return {"part": self.part, "intent": self.intent,
                "features": [asdict(f) for f in self.features],
                "tests": self.tests}

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.to_dict(), sort_keys=False,
                                             allow_unicode=True))

    # --- queries used by reconstruction / verification ---

    def features_of_type(self, type_: str) -> list[Feature]:
        return [f for f in self.features if f.type == type_]

    def servo_mounts(self) -> list[Feature]:
        return self.features_of_type("servo_mount")
