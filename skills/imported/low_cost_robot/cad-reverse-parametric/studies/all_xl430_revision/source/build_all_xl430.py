"""Generate the rigid all-XL430 replacement as an unaccepted candidate."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

from common import (
    EXPECTED_LEAVES,
    FOLLOWER_SOURCE,
    PART_NAMES,
    REFERENCE_DIR,
    STUDY_ID,
    check_reference_hashes,
    write_json,
)

sys.path.insert(0, str(FOLLOWER_SOURCE))

from mesh_export import export_closed_stl  # noqa: E402
from rebuild import build_geometry, require_single_solid  # noqa: E402

REFERENCE_XL430 = "/Robot Arm v14/XL-430_new v1:1"
EXISTING_XL430 = (
    "/Robot Arm v14/XL-430_new v1:1",
    "/Robot Arm v14/XL-430_new v1:2",
)
TARGETS = (
    ("J3", "/Robot Arm v14/XL,XC-330 v1:6", ("distal", "wrist")),
    # J4 anchors the extension's upstream axis and does not move with its distal end.
    ("J4", "/Robot Arm v14/XL,XC-330 v1:7", ()),
    (
        "J5_GRIPPER",
        "/Robot Arm v14/gripper v9:1/XL,XC-330 v1:1",
        ("distal", "wrist", "gripper"),
    ),
    ("J6", "/Robot Arm v14/XL,XC-330 v1:8", ("distal",)),
)


@dataclass
class Prototype:
    assembly: cq.Assembly
    manifest: list[dict]
    baseline: object


def _label_name(label: TDF_Label) -> str:
    attribute = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
        return attribute.Get().ToExtString()
    return "unnamed"


def read_assembly_nodes(path: Path) -> dict[str, cq.Location]:
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"Cannot read {path}")
    document = TDocStd_Document(TCollection_ExtendedString("assembly-nodes"))
    if not reader.Transfer(document):
        raise ValueError(f"Cannot transfer {path}")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    nodes: dict[str, cq.Location] = {}

    def walk(label: TDF_Label, location: cq.Location, parent: str) -> None:
        name = _label_name(label)
        if shape_tool.IsReference_s(label):
            location = location * cq.Location(shape_tool.GetLocation_s(label))
            referred = TDF_Label()
            if not shape_tool.GetReferredShape_s(label, referred):
                raise ValueError("Unresolved assembly reference")
        else:
            referred = label
        current = f"{parent}/{name}"
        if shape_tool.IsAssembly_s(referred):
            if current in nodes:
                raise ValueError(f"Duplicate assembly path: {current}")
            nodes[current] = location
            children = TDF_LabelSequence()
            shape_tool.GetComponents_s(referred, children)
            for index in range(1, children.Length() + 1):
                walk(children.Value(index), location, current)

    roots = TDF_LabelSequence()
    shape_tool.GetFreeShapes(roots)
    for index in range(1, roots.Length() + 1):
        walk(roots.Value(index), cq.Location(), "")
    return nodes


def component_name(value: str) -> str:
    return value.replace(" ", "_").replace(":", "_").replace("/", "_")


def rows_below(rows: list, parent: str) -> list:
    return [row for row in rows if row.path.startswith(f"{parent}/")]


def build_prototype(reference_dir: Path = REFERENCE_DIR) -> Prototype:
    baseline = build_geometry(reference_dir)
    rows = baseline.original
    nodes = read_assembly_nodes(reference_dir / "arm.step")
    reference_leaves = rows_below(rows, REFERENCE_XL430)
    if len(reference_leaves) != 35:
        raise ValueError("XL430 reference motor must have 35 leaf occurrences")
    for path in EXISTING_XL430:
        if len(rows_below(rows, path)) != 35:
            raise ValueError(f"Unexpected existing XL430 occurrence: {path}")

    target_rows = {path: rows_below(rows, path) for _, path, _ in TARGETS}
    if any(len(items) != 21 for items in target_rows.values()):
        raise ValueError("A former XL330 occurrence does not have 21 leaves")
    removed = {row.index for items in target_rows.values() for row in items}
    if len(removed) != 84:
        raise ValueError("Replacement targets overlap or are incomplete")

    assembly = cq.Assembly(name="Follower_all_XL430_UNACCEPTED_STUDY")
    manifest = []
    for row in rows:
        if row.index in removed:
            continue
        name = component_name(f"KEEP_{row.index:03d}_{row.name}")
        location = baseline.revised_locations[row.index]
        assembly.add(
            baseline.revised_shapes[row.index],
            loc=location,
            name=name,
            color=row.color or cq.Color(0.68, 0.71, 0.76),
        )
        manifest.append(
            {
                "name": name,
                "source_index": row.index,
                "action": "kept_from_geometry_revision",
                "logical_path": row.path,
                "transform": location.toTuple(),
            }
        )

    placement = baseline.placement
    placement_steps = {
        "distal": cq.Location(tuple(placement["distal_translation_mm"])),
        "wrist": cq.Location(tuple(placement["wrist_motor_additional_translation_mm"])),
        "gripper": cq.Location(tuple(placement["gripper_additional_translation_mm"])),
    }
    reference_top = nodes[REFERENCE_XL430]
    for tag, path, transforms in TARGETS:
        target_top = nodes[path]
        for transform in transforms:
            target_top = placement_steps[transform] * target_top
        for index, leaf in enumerate(reference_leaves):
            location = target_top * (reference_top.inverse * leaf.loc)
            name = component_name(f"{tag}_XL430_{index:02d}_{leaf.name}")
            assembly.add(
                leaf.shape,
                loc=location,
                name=name,
                color=leaf.color or cq.Color(0.55, 0.60, 0.66),
            )
            manifest.append(
                {
                    "name": name,
                    "action": "XL330_replaced_with_XL430",
                    "target_occurrence": path,
                    "reference_occurrence": REFERENCE_XL430,
                    "reference_leaf": leaf.path,
                    "logical_path": path + leaf.path[len(REFERENCE_XL430) :],
                    "transform": location.toTuple(),
                }
            )
    if (
        len(manifest) != EXPECTED_LEAVES
        or len({item["name"] for item in manifest}) != EXPECTED_LEAVES
    ):
        raise ValueError("Invalid replacement manifest")
    return Prototype(assembly, manifest, baseline)


def generate_candidate(run: Path, reference_dir: Path = REFERENCE_DIR) -> None:
    check_reference_hashes()
    if run.exists():
        raise FileExistsError(f"Run already exists; use another run-id: {run.name}")
    prototype = build_prototype(reference_dir)
    parts_dir = run / "CAD/parts"
    parts_dir.mkdir(parents=True)
    prototype.assembly.export(str(run / "CAD/arm_all_XL430_static_UNACCEPTED.step"))
    mesh_metadata = {}
    for name in PART_NAMES:
        shape = prototype.baseline.parts[name]
        require_single_solid(shape, name)
        cq.exporters.export(shape, str(parts_dir / f"{name}.step"))
        mesh_metadata[name] = export_closed_stl(
            shape,
            parts_dir / f"{name}.stl",
            allow_gripper_repair=name == "gripper_moving_unchanged",
        )
    write_json(run / "replacement_manifest.json", prototype.manifest)
    write_json(run / "reports/baseline_mesh_export.json", mesh_metadata)
    write_json(
        run / "generation.json",
        {
            "study_id": STUDY_ID,
            "acceptance_state": "unaccepted",
            "candidate_kind": "rigid_motor_replacement_no_bracket_redesign",
            "original_leaf_count": 161,
            "removed_leaf_count": 84,
            "inserted_leaf_count": 140,
            "expected_leaf_count": EXPECTED_LEAVES,
            "part_design_status": (
                "mixed_servo_baseline_geometry_not_all_xl430_validated"
            ),
            "reference_sha256": check_reference_hashes(),
        },
    )
    (run / "NOT_FOR_PRINT.txt").write_text(
        "UNACCEPTED / 未承認・印刷禁止\n"
        "全XL430剛体置換の診断用データです。\n"
        "7部品の全XL430適合、静止干渉、連続動作は未合格です。\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        generate_candidate(args.output.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"FAILED: {error}")
        return 3
    print("Generated unaccepted diagnostic candidate; validation is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
