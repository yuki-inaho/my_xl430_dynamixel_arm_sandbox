from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    path = Path(__file__).parents[1] / "studies/xl430_lowcost/prepare_print_package.py"
    spec = importlib.util.spec_from_file_location("prepare_print_package", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gcode_validation_accepts_expected_objects(tmp_path):
    module = _load_module()
    gcode = tmp_path / "plate_1.gcode"
    result = tmp_path / "result.json"
    gcode.write_text(
        "; total layer number: 12\n"
        "; estimated printing time (normal mode) = 20m\n"
        "; filament used [cm3] = 4.2\n"
        "START_PRINT EXTRUDER_TEMP=200 BED_TEMP=50\n"
        "EXCLUDE_OBJECT_DEFINE NAME=part_a.stl_id_0_copy_0\n"
        "EXCLUDE_OBJECT_DEFINE NAME=part_b.stl_id_1_copy_0\n"
        "END_PRINT\n",
        encoding="utf-8",
    )
    result.write_text(
        json.dumps({"return_code": 0, "error_string": "Success."}), encoding="utf-8"
    )

    report = module._validate_gcode(gcode, result, ["part_a", "part_b"])

    assert report["passed"]
    assert report["m191_count"] == 0
    assert report["layer_count"] == "12"


def test_gcode_validation_rejects_chamber_wait(tmp_path):
    module = _load_module()
    gcode = tmp_path / "plate_1.gcode"
    result = tmp_path / "result.json"
    gcode.write_text(
        "START_PRINT\nM191 S35\nEXCLUDE_OBJECT_DEFINE NAME=part_a.stl_id_0_copy_0\nEND_PRINT\n",
        encoding="utf-8",
    )
    result.write_text(
        json.dumps({"return_code": 0, "error_string": "Success."}), encoding="utf-8"
    )

    report = module._validate_gcode(gcode, result, ["part_a"])

    assert not report["passed"]
    assert report["m191_count"] == 1
