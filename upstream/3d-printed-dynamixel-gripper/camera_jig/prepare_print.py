"""Single-plate trial print preparation. Does not grant mechanical approval."""

import argparse
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

from camera_jig.build import CAMERA_LOC, ROOT, sha
from scripts.assembly_io import bounds
from scripts.orca_presets import resolve_preset

PARTS = ("saddle", "front_jaw", "camera_spacer")
MACHINE = "Creality Ender-3 Pro 0.4 nozzle"
PROCESS = "0.20mm Standard @Creality Ender3 Pro 0.4"


def mesh_report(mesh):
    good = (
        mesh.is_watertight
        and mesh.is_winding_consistent
        and mesh.volume > 0
        and len(mesh.split(only_watertight=False)) == 1
        and np.isfinite(mesh.vertices).all()
    )
    return {
        "pass": bool(good),
        "watertight": mesh.is_watertight,
        "winding_consistent": mesh.is_winding_consistent,
        "volume_mm3": float(mesh.volume),
        "bounds_mm": mesh.bounds.tolist(),
        "triangles": len(mesh.faces),
    }


def commands(text):
    for line in text.splitlines():
        code = line.split(";", 1)[0].strip()
        if code:
            yield code


def check_gcode(text):
    errors = []
    codes = list(commands(text))
    names = [c.split()[0] for c in codes]
    for needed in ("G28", "G90", "G21", "M83", "M109", "M190", "M104", "M140", "M84"):
        if needed not in names:
            errors.append(f"Missing {needed}")
    for forbidden in (
        "M191",
        "M600",
        "START_PRINT",
        "END_PRINT",
        "M0",
        "M1",
        "M25",
        "M500",
        "M502",
        "G2",
        "G3",
    ):
        if forbidden in names:
            errors.append(f"Unexpected {forbidden}")
    if "G92 E0" not in codes:
        errors.append("Missing relative-E reset")
    temperatures = {}
    for cmd, limit in (("M104", 230), ("M109", 230), ("M140", 65), ("M190", 65)):
        vals = []
        for c in codes:
            if c.split()[0] == cmd:
                m = re.search(r"\b[SR](-?[\d.]+)", c)
                if not m:
                    errors.append(f"Unparsed temperature {c}")
                else:
                    vals.append(float(m[1]))
        if not vals or min(vals) < 0 or max(vals) > limit:
            errors.append(f"Temperature bounds {cmd}: {vals}")
        temperatures[cmd] = sorted(set(vals))
    if temperatures.get("M104", [])[-1:] and not any(c == "M104 S0" for c in codes[-30:]):
        errors.append("No final hotend shutdown")
    if not any(c == "M140 S0" for c in codes[-30:]):
        errors.append("No final bed shutdown")
    moves = {a: [] for a in "XYZ"}
    absolute = True
    position = {a: 0.0 for a in "XYZ"}
    for c in codes:
        cmd = c.split()[0]
        if cmd in ("G90", "G91"):
            absolute = cmd == "G90"
        if cmd in ("G0", "G1"):
            for a in "XYZ":
                m = re.search(rf"\b{a}(-?(?:\d+(?:\.\d*)?|\.\d+))", c)
                if m:
                    position[a] = float(m[1]) + (0 if absolute else position[a])
                    moves[a].append(position[a])
    for a, values in moves.items():
        if (
            not values
            or min(values) < -0.01
            or max(values) > {"X": 220, "Y": 220, "Z": 250}[a] + 0.01
        ):
            errors.append(f"Travel bounds {a}")
    layers = re.search(r"; total layer number: (\d+)", text)
    if not layers or int(layers[1]) <= 1:
        errors.append("Missing layers")
    if not re.search(r"^; print_sequence = by layer$", text, re.MULTILINE):
        errors.append("Not confirmed layer-by-layer printing")
    if not re.search(r"^; enable_support = 1$", text, re.MULTILINE):
        errors.append("Support not enabled")
    return {
        "pass": not errors,
        "errors": errors,
        "temperatures": temperatures,
        "motion_bounds_mm": {a: [min(v), max(v)] if v else None for a, v in moves.items()},
        "layers": int(layers[1]) if layers else None,
    }


def check_project(path, gcode, *, review_standard_pla_bed_warning=False):
    errors = []
    with zipfile.ZipFile(path) as archive:
        model = ET.fromstring(archive.read("3D/3dmodel.model"))
        count = len(model.findall("{*}build/{*}item"))
        plate = json.loads(archive.read("Metadata/plate_1.json"))
        info = ET.fromstring(archive.read("Metadata/slice_info.config"))
        settings = ET.fromstring(archive.read("Metadata/model_settings.config"))
        config = json.loads(archive.read("Metadata/project_settings.config"))
    if count != len(PARTS) or len(info.findall("plate")) != 1:
        errors.append("Need exactly three parts on one plate")
    expected = {f"{p}.stl" for p in PARTS}
    if {obj["name"] for obj in plate["bbox_objects"]} != expected:
        errors.append("Plate object names differ from allow-list")
    printed = set(re.findall(r"^; printing object (\S+) id:", gcode, re.MULTILINE))
    if printed != expected:
        errors.append("G-code does not print every allowed part")
    if plate["is_seq_print"]:
        errors.append("Sequential object mode is forbidden")
    if abs(plate["nozzle_diameter"] - 0.4) > 1e-5:
        errors.append("Unexpected nozzle")
    warnings = [x.attrib for x in info.findall(".//warning")]
    reviewed = []
    for warning in warnings:
        if (
            review_standard_pla_bed_warning
            and warning.get("msg") == "bed_temperature_too_high_than_filament"
            and warning.get("error_code") == "1000C001"
            and config.get("filament_type") == ["PLA"]
            and config.get("temperature_vitrification") == ["60"]
            and config.get("hot_plate_temp") == ["60"]
            and config.get("hot_plate_temp_initial_layer") == ["60"]
            and plate["bed_type"] == "hot_plate"
            and check_gcode(gcode)["temperatures"]["M140"] == [0.0, 60.0]
            and check_gcode(gcode)["temperatures"]["M190"] == [60.0]
        ):
            reviewed.append(
                {
                    **warning,
                    "decision": "retain standard PLA 60C bed; same as previous test print",
                    "reason": "Orca 2.4.2 warns at bed >= configured vitrification temperature, including equality",
                    "source": "https://github.com/OrcaSlicer/OrcaSlicer/blob/v2.4.2/src/libslic3r/GCode/GCodeProcessor.cpp#L5551-L5577",
                }
            )
    if len(warnings) != len(reviewed):
        errors.append("3MF contains slicer warnings; review before copying")
    if any(x.get("skipped") != "false" for x in info.findall(".//object")):
        errors.append("A part was skipped")
    if any(int(v) for x in settings.findall(".//mesh_stat") for v in x.attrib.values()):
        errors.append("Slicer repaired mesh implicitly")
    bounds_xy = plate["bbox_all"]
    if min(bounds_xy) < 0 or max(bounds_xy) > 220:
        errors.append("Plate bounds exceeded")
    return {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "reviewed_warnings": reviewed,
        "build_item_count": count,
        "plate_metadata": plate,
    }


def prepare(source, out, system, orca):
    source, out = source.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    validation = json.loads((source / "validation.json").read_text())
    if not (validation["geometry_pass"] and validation["static_assembly_pass"]):
        raise ValueError("Static geometry rejected; not eligible for trial slicing")
    stls, meshes = [], {}
    for name in PARTS:
        file = source / f"{name}_UNVALIDATED.step"
        if sha(file) != validation["output_sha256"][file.name]:
            raise ValueError(f"Source changed: {file}")
        shape = cq.importers.importStep(str(file)).val()
        if name == "front_jaw":
            shape = shape.rotate((0, 0, 0), (1, 0, 0), 90)
        elif name == "camera_spacer":
            shape = shape.moved(CAMERA_LOC.inverse)
        b = bounds(shape)
        shape = shape.translate((-(b[0] + b[3]) / 2, -(b[1] + b[4]) / 2, -b[2]))
        path = out / f"{name}.stl"
        cq.exporters.export(shape, str(path), tolerance=0.02, angularTolerance=0.1)
        mesh = trimesh.load_mesh(path)
        report = mesh_report(mesh)
        report["source_step_sha256"] = sha(file)
        report["stl_sha256"] = sha(path)
        report["brep_volume_mm3"] = shape.Volume()
        if not report["pass"] or abs(mesh.volume / shape.Volume() - 1) > 0.005:
            raise ValueError(f"Mesh failed: {name}: {report}")
        meshes[name], stls = report, [*stls, path]
    inputs = {
        "machine": system / f"Creality/machine/{MACHINE}.json",
        "process": system / f"Creality/process/{PROCESS}.json",
        "filament": system / "OrcaFilamentLibrary/filament/Generic PLA @System.json",
    }
    profiles = {k: resolve_preset(p, system) for k, p in inputs.items()}
    profiles["process"].update(
        {
            "curr_bed_type": "High Temp Plate",
            "adaptive_layer_height": "0",
            "print_sequence": "by layer",
            "wall_loops": "4",
            "sparse_infill_density": "35%",
            "sparse_infill_pattern": "gyroid",
            "enable_support": "1",
            "support_type": "normal(auto)",
            "support_on_build_plate_only": "0",
            "support_base_pattern_spacing": "2.5",
            "support_top_z_distance": "0.2",
            "support_bottom_z_distance": "0.2",
            "support_interface_top_layers": "3",
            "support_object_xy_distance": "0.35",
            "brim_type": "outer_only",
            "brim_width": "5",
            "brim_object_gap": "0.1",
            "initial_layer_speed": "20",
            "initial_layer_infill_speed": "20",
            "enable_prime_tower": "0",
            "enable_arc_fitting": "0",
            "layer_height": "0.2",
            "initial_layer_print_height": "0.2",
            "skirt_loops": "1",
        }
    )
    for k, data in profiles.items():
        (out / f"{k}.json").write_text(json.dumps(data, indent=2) + "\n")
    cmd = [
        str(orca),
        "--load-settings",
        f"{out}/machine.json;{out}/process.json",
        "--load-filaments",
        str(out / "filament.json"),
        "--orient",
        "0",
        "--arrange",
        "1",
        "--ensure-on-bed",
        "--slice",
        "0",
        "--outputdir",
        str(out),
        "--export-3mf",
        "job.3mf",
        *map(str, stls),
    ]
    proc = subprocess.run(
        cmd,
        cwd=out,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    (out / "slicer.log").write_text(proc.stdout + proc.stderr)
    report = {
        "scope": "user-requested single-plate trial print, NOT mechanical approval",
        "parts": meshes,
        "source_validation_sha256": sha(source / "validation.json"),
        "orca_sha256": sha(orca),
        "command": cmd,
        "exit_code": proc.returncode,
        "printer": MACHINE,
        "material": "Generic PLA",
        "fabrication_approved": False,
        "orientations": {
            "saddle": "upright on clamp bottom; support enabled",
            "front_jaw": "broad face on bed, X rotation +90 deg",
            "camera_spacer": "original local XY flat",
        },
    }
    (out / "preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    if proc.returncode:
        raise RuntimeError(f"Slicer exit {proc.returncode}; see {out}/slicer.log")
    result = json.loads((out / "result.json").read_text())
    if result["return_code"] != 0 or result["error_string"] != "Success.":
        raise ValueError(result)
    gcodes = list(out.glob("plate_*.gcode"))
    if len(gcodes) != 1:
        raise ValueError(f"Need exactly one plate, got {len(gcodes)}")
    gcode = gcodes[0].read_text()
    checked = check_gcode(gcode)
    project = check_project(out / "job.3mf", gcode, review_standard_pla_bed_warning=True)
    checked["pass"] = checked["pass"] and project["pass"]
    checked["errors"].extend(project["errors"])
    checked.update(
        {
            "plate_count": len(gcodes),
            "project": project,
            "gcode_sha256": sha(gcodes[0]),
            "slicer_result": result,
        }
    )
    (out / "gcode_validation.json").write_text(json.dumps(checked, indent=2) + "\n")
    print(json.dumps(checked, indent=2))
    if not checked["pass"]:
        raise ValueError("G-code gate failed")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT / "outputs/camera-jig-20260922")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--orca", type=Path, default=Path.home() / "Applications/OrcaSlicer.AppImage")
    p.add_argument("--system", type=Path, default=Path.home() / ".config/OrcaSlicer/system")
    args = p.parse_args()
    prepare(args.source, args.out, args.system, args.orca)


if __name__ == "__main__":
    main()
