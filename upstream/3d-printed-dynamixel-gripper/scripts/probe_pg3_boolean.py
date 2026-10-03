"""Explicit kernel experiment, not a hidden repair or release checker."""

import json
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut

from gripper_design.pg3 import PG3Model, to_arm


def main():
    out = Path("outputs/pg3-install-boolean-r1")
    out.mkdir(parents=True, exist_ok=False)
    model = PG3Model()
    rows = []
    for name, shape in (
        ("crank_neutral", model.neutral["crank"]),
        ("crank_25", model.at(25)["crank"]),
        ("crank_arm_25", to_arm(model.at(25)["crank"])),
        ("motor_arm", to_arm(model.neutral["XL430_fixed"])),
    ):
        for copied in (False, True):
            tool = shape.copy() if copied else shape
            for parallel in (False, True):
                for fuzzy in (0, 1e-7, 1e-6):
                    result = {}
                    for label, klass in (("cut", BRepAlgoAPI_Cut), ("common", BRepAlgoAPI_Common)):
                        op = klass()
                        op.SetFuzzyValue(fuzzy)
                        s = shape._bool_op([shape], [tool], op, parallel=parallel)
                        result[label] = {"volume": s.Volume(), "valid": s.isValid()}
                    row = {
                        "part": name,
                        "independent_copy": copied,
                        "parallel": parallel,
                        "fuzzy_mm": fuzzy,
                        "original_volume": shape.Volume(),
                        **result,
                    }
                    rows.append(row)
                    print(json.dumps(row), flush=True)
    (out / "probe.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
