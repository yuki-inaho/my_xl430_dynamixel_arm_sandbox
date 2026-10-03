"""Generic geometry value objects. No file I/O, no CAD kernel, no domain terms.

Pure data + math so it is trivially reusable and testable anywhere.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class Envelope:
    """An axis-aligned bounding box size (mm), order-independent on compare."""
    w: float
    h: float
    d: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.w, self.h, self.d)

    def sorted_dims(self) -> list[float]:
        return sorted(self.as_tuple(), reverse=True)

    def fits_inside(self, bbox: tuple[float, float, float] | list[float],
                    clearance: float = 0.0) -> "FitResult":
        """Best-axis-aligned test: does this envelope fit inside `bbox`?"""
        outer = sorted(bbox, reverse=True)
        inner = [x + 2 * clearance for x in self.sorted_dims()]
        margins = [round(o - i, 3) for o, i in zip(outer, inner)]
        return FitResult(fits=all(m >= 0 for m in margins), margins_mm=margins)

    def ratio_to(self, other: "Envelope") -> dict[str, float]:
        return {
            "w_ratio": round(other.w / self.w, 4),
            "h_ratio": round(other.h / self.h, 4),
            "d_ratio": round(other.d / self.d, 4),
            "dw_mm": round(other.w - self.w, 3),
            "dh_mm": round(other.h - self.h, 3),
            "dd_mm": round(other.d - self.d, 3),
        }


@dataclass(frozen=True)
class FitResult:
    fits: bool
    margins_mm: list[float]


@dataclass(frozen=True)
class Component:
    """A named thing with an envelope plus free-form metadata (domain layer fills meta)."""
    name: str
    envelope: Envelope
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["envelope"] = self.envelope.as_tuple()
        return d


# --- Metric clearance-hole classification (configurable, sensible default) ---

DEFAULT_SCREW_BANDS: tuple[tuple[str, float, float], ...] = (
    # Tap/press-fit holes are nearly nominal-diameter; clearance holes are wider.
    # Re-creating a part needs the distinction (self-tap into plastic vs through-bolt).
    ("M2-tap", 1.9, 2.15),
    ("M2", 2.15, 2.55),       # M2 clearance (~2.2-2.4)
    ("M2.5", 2.55, 3.05),
    ("M3", 3.05, 3.6),
    ("M4", 4.0, 4.8),
    ("M5", 5.1, 5.8),
)


def classify_screw(diameter: float,
                   bands: tuple[tuple[str, float, float], ...] = DEFAULT_SCREW_BANDS
                   ) -> str | None:
    for name, lo, hi in bands:
        if lo <= diameter <= hi:
            return name
    return None
