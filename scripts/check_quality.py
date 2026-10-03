"""Enforce a small complexity budget for the maintained Python implementation."""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from radon.complexity import cc_rank, cc_visit
from radon.metrics import mi_visit

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ComplexityMetric:
    file: str
    symbol: str
    complexity: int
    rank: str


@dataclass(frozen=True)
class MaintainabilityMetric:
    file: str
    maintainability_index: float


@dataclass(frozen=True)
class QualityReport:
    maximum_allowed_complexity: int
    maximum_observed_complexity: int
    complexity: tuple[ComplexityMetric, ...]
    maintainability: tuple[MaintainabilityMetric, ...]


def measure() -> QualityReport:
    complexities = []
    maintainability = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(ROOT))
        maintainability.append(MaintainabilityMetric(relative, mi_visit(source, multi=True)))
        for block in cc_visit(source):
            blocks = (block, *getattr(block, "methods", ()))
            complexities.extend(
                ComplexityMetric(relative, item.name, item.complexity, cc_rank(item.complexity))
                for item in blocks
            )
    maximum = max((item.complexity for item in complexities), default=0)
    return QualityReport(10, maximum, tuple(complexities), tuple(maintainability))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = measure()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")
    print(
        f"Maximum complexity: {report.maximum_observed_complexity}; "
        f"allowed: {report.maximum_allowed_complexity}"
    )
    return int(report.maximum_observed_complexity > report.maximum_allowed_complexity)


if __name__ == "__main__":
    raise SystemExit(main())
