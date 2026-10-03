"""Rebuild the source-preserving, mixed-servo follower geometry revision.

This is NOT an XL430 conversion. Source datums are measured from the supplied
STEP files, and guarded by SHA-256 so a different revision fails closed.
Run: python source/rebuild.py --out regenerated --render
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
import numpy as np

from assembly_io import Occurrence, read_step

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_REFERENCE_DIR = REPO_ROOT / "hardware/follower/step"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "skills/cad-reverse-parametric/outputs/follower_geometry_revision"
)
VOLUME_TOL = 1e-4  # mm^3; volume interference, not a manufacturing tolerance
YC, ZC = 8.63030909986437, 8.47375720347861
HOLES_YZ = [(YC, ZC - 6), (YC + 6, ZC), (YC, ZC + 6), (YC - 6, ZC)]
WRIST_HOLES = [
    (x, y)
    for x in (2.9923594969, 18.9923594969)
    for y in (3.10332332496, 33.10332332496)
]
DISTAL_PREFIXES = (
    "/XL,XC-330 v1:6/",
    "/servo connector angle v4:1/",
    "/gripper v9:1/",
    "/XL,XC-330 v1:8/",
)


def solid_volume(shape: cq.Shape) -> float:
    """Ignore surfaces/drafting representations, never cancel signed solids."""
    return float(sum(s.Volume() for s in shape.Solids()))


def require_single_solid(shape: cq.Shape, name: str) -> None:
    if len(shape.Solids()) != 1 or not shape.isValid() or solid_volume(shape) <= 0:
        raise ValueError(f"{name}: invalid/disconnected solid; no accepted export")


def verify_sources(directory: Path) -> dict[str, str]:
    expected = json.loads((Path(__file__).with_name("input_sha256.json")).read_text())
    actual = {}
    for name, checksum in expected.items():
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing reference: {path}")
        actual[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual[name] != checksum:
            raise ValueError(
                f"Unexpected source revision: {name}. Re-measure datums first."
            )
    return actual


def reinforce_extension(original: cq.Shape, rim_mm: float = 2.5):
    """Add two 3 mm ear pads; preserve the 29 mm gap and all source material.

    Each pad is the convex hull of the four hole centres offset by mouth radius
    2.9 mm plus the specified rim. No full-width collar and no invented phi8 bore.
    Existing phi1.8 / 90-degree phi5.8 countersunk openings are re-opened.
    """
    if not math.isfinite(rim_mm) or not 2.5 <= rim_mm <= 3.0:
        raise ValueError(
            "Supported rim range is 2.5–3.0 mm; assembly checks still required"
        )
    profile = [(YC - 6, ZC), (YC, ZC - 6), (YC + 6, ZC), (YC, ZC + 6)]
    pad = (
        cq.Workplane("YZ")
        .polyline(profile)
        .close()
        .offset2D(2.9 + rim_mm)
        .extrude(3)
        .val()
    )
    pads = [pad.translate((14.5, 0, 0)), pad.translate((-17.5, 0, 0))]
    result = original.fuse(*pads).clean()
    for sign in (-1, 1):
        direction = cq.Vector(sign, 0, 0)
        for y, z in HOLES_YZ:
            bore = cq.Solid.makeCylinder(
                0.9, 3.2, cq.Vector(sign * 14.4, y, z), direction
            )
            sink = cq.Solid.makeCone(
                0.9, 2.9, 2, cq.Vector(sign * 15.5, y, z), direction
            )
            result = result.cut(bore, sink).clean()
    require_single_solid(result, "extension")
    return result, cq.Compound.makeCompound(pads)


def clear_base(original: cq.Shape):
    """Open the existing base floor below the installed idler, +0.25 mm clearance.

    The large tool covers the phi20.5 idler; the smaller stage covers the cap.
    The outer base dimensions and the four mounting-hole axes are unchanged.
    """
    tool = cq.Solid.makeCylinder(10.5, 5.0, cq.Vector(0, 68, -0.25), cq.Vector(0, 0, 1))
    tool = tool.fuse(
        cq.Solid.makeCylinder(5.55, 5.7, cq.Vector(0, 68, -0.25), cq.Vector(0, 0, 1))
    )
    result = original.cut(tool).clean()
    require_single_solid(result, "base")
    return result, tool


def add_wrist_standoffs(original: cq.Shape):
    """Keep the load-carrying floor intact with four integral 3.25 mm stand-offs.

    OD 5.3 / bore 2.3 mm, annular wall 1.5 mm. These are not claimed to meet the
    extension's 2.5 mm rim requirement or any unperformed strength calculation.
    The motor/gripper are lowered 3.25 mm; fastening stack needs physical review.
    """
    pads = []
    for x, y in WRIST_HOLES:
        pad = cq.Solid.makeCylinder(
            2.65, 3.35, cq.Vector(x, y, -3.25), cq.Vector(0, 0, 1)
        )
        bore = cq.Solid.makeCylinder(
            1.15, 3.55, cq.Vector(x, y, -3.35), cq.Vector(0, 0, 1)
        )
        pads.append(pad.cut(bore))
    result = original.fuse(*pads).clean()
    require_single_solid(result, "wrist")
    return result, cq.Compound.makeCompound(pads)


def unique_occurrence(rows: list[Occurrence], suffix: str) -> Occurrence:
    found = [row for row in rows if row.path.endswith(suffix)]
    if len(found) != 1:
        raise ValueError(f"Expected one component for {suffix}; found {len(found)}")
    return found[0]


@dataclass
class Build:
    original: list[Occurrence]
    assembly: cq.Assembly
    revised_shapes: dict[int, cq.Shape]
    revised_locations: dict[int, cq.Location]
    parts: dict[str, cq.Shape]
    local_sources: dict[str, cq.Shape]
    local_masks: dict[str, cq.Shape]
    target_index: int
    base_index: int
    wrist_index: int
    placement: dict


def build_geometry(reference_dir: Path, rim_mm: float = 2.5) -> Build:
    verify_sources(reference_dir)
    _, _, rows = read_step(reference_dir / "arm.step")
    target = unique_occurrence(rows, "/XL330_to_XL330_straight v5:1/connector:1")
    base = unique_occurrence(rows, "/Simple Base v9:1/Base:1")
    wrist = unique_occurrence(rows, "/servo connector angle v4:1/shoulder_rotation:1")
    long_source = cq.importers.importStep(
        str(reference_dir / "elbow_to_wrist_extension.step")
    ).val()
    extension, extension_mask = reinforce_extension(long_source, rim_mm)
    base_shape, base_mask = clear_base(base.shape)
    wrist_shape, wrist_mask = add_wrist_standoffs(wrist.shape)

    axis = np.array([5.5, 131.404346834981, 61.6632909605516])
    target_location = cq.Location(tuple(axis + [0, YC, -ZC]), (0, 0, 1), 180)
    downstream_pair = np.array(
        [5.5, axis[1] + YC + 69.3457752064813, axis[2] - ZC + 11.1736173480445]
    )
    distal_translation = downstream_pair - [5.25, 199.728271681865, 63.8305728769528]
    overrides = {
        target.index: extension,
        base.index: base_shape,
        wrist.index: wrist_shape,
    }
    labels = {
        target.index: "EXTENSION_ROUND_INTEGRATED",
        base.index: "BASE_IDLER_CLEARANCE",
        wrist.index: "WRIST_INTEGRAL_STANDOFFS",
    }
    assembly = cq.Assembly(name="Follower_geometry_revision_mixed_servos")
    shapes, locations = {}, {}
    for row in rows:
        shape = overrides.get(row.index, row.shape)
        location = target_location if row.index == target.index else row.loc
        # Match by identity, never by a contiguous index range: the base occurs
        # between distal items in the source STEP tree and must not be translated.
        if any(prefix in row.path for prefix in DISTAL_PREFIXES):
            location = cq.Location(tuple(distal_translation)) * location
        if any(prefix in row.path for prefix in ("/XL,XC-330 v1:6/", "/gripper v9:1/")):
            location = cq.Location((0, 1.15, -3.25)) * location
        if "/gripper v9:1/" in row.path:
            location = cq.Location((1.375, 0, 0)) * location
        name = f"{row.index:03d}_" + labels.get(
            row.index, "".join(c if c.isalnum() or c in "_-" else "_" for c in row.name)
        )
        color = (
            cq.Color(0.22, 0.58, 0.70)
            if row.index in overrides
            else row.color or cq.Color(0.68, 0.71, 0.76)
        )
        assembly.add(shape, loc=location, name=name, color=color)
        shapes[row.index], locations[row.index] = shape, location

    parts = {
        "elbow_to_wrist_extension_round": extension,
        "base_idler_clearance": base_shape,
        "elbow_to_wrist_standoff": wrist_shape,
    }
    for part_name, suffix in {
        "shoulder_rotation_unchanged": "/rotation connector:1",
        "shoulder_to_elbow_unchanged": "/XL430 to XL330 new connector v6:1/connector:1",
        "gripper_static_unchanged": "/gripper v9:1/static side:1",
        "gripper_moving_unchanged": "/gripper v9:1/moving side:1",
    }.items():
        parts[part_name] = unique_occurrence(rows, suffix).shape
    for name, shape in parts.items():
        require_single_solid(shape, name)
    placement = dict(
        upstream_axis_mm=axis.tolist(),
        target_transform=target_location.toTuple(),
        downstream_pair_mm=downstream_pair.tolist(),
        distal_translation_mm=distal_translation.tolist(),
        wrist_motor_additional_translation_mm=[0, 1.15, -3.25],
        gripper_additional_translation_mm=[1.375, 0, 0],
        downstream_side_clearance_each_mm=0.25,
        wrist_idler_clearance_mm=0.25,
        rim_mm=rim_mm,
        source_arm_external_span_mm=80.1001605549,
        source_standalone_external_span_mm=90.1001605549,
    )
    return Build(
        rows,
        assembly,
        shapes,
        locations,
        parts,
        {"extension": long_source, "base": base.shape, "wrist": wrist.shape},
        {"extension": extension_mask, "base": base_mask, "wrist": wrist_mask},
        target.index,
        base.index,
        wrist.index,
        placement,
    )


def write_geometry(build: Build, out: Path) -> None:
    (out / "CAD/parts").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(exist_ok=True)
    build.assembly.export(str(out / "CAD/follower_geometry_checked.step"))
    from mesh_export import export_closed_stl

    mesh_metadata = {}
    for name, shape in build.parts.items():
        cq.exporters.export(shape, str(out / f"CAD/parts/{name}.step"))
        mesh_metadata[name] = export_closed_stl(
            shape,
            out / f"CAD/parts/{name}.stl",
            allow_gripper_repair=name == "gripper_moving_unchanged",
        )
    (out / "reports/mesh_export.json").write_text(json.dumps(mesh_metadata, indent=2))
    manifest = [
        dict(
            index=row.index,
            original_path=row.path,
            exported_node_name=next(
                n.name
                for n in build.assembly.children
                if n.name.startswith(f"{row.index:03d}_")
            ),
            action="replaced"
            if row.index in (build.target_index, build.base_index, build.wrist_index)
            else "geometry_unchanged",
            transform=build.revised_locations[row.index].toTuple(),
            solids=len(build.revised_shapes[row.index].Solids()),
        )
        for row in build.original
    ]
    (out / "reports/component_manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "reports/placement.json").write_text(json.dumps(build.placement, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rim-mm", type=float, default=2.5)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    out, refs = args.out.resolve(), args.reference_dir.resolve()
    if out == refs or out.is_relative_to(refs):
        parser.error("Output must not overwrite the reference directory")
    try:
        data = build_geometry(refs, args.rim_mm)
        out.parent.mkdir(parents=True, exist_ok=True)
        # Accepted CAD is promoted only after re-import and geometry validation.
        # Failed attempts are isolated; they never overwrite a prior accepted model.
        with tempfile.TemporaryDirectory(
            prefix=".cad-stage-", dir=out.parent
        ) as temporary:
            staging = Path(temporary)
            write_geometry(data, staging)
            from validate import validate_release

            report = validate_release(data, staging)
            report["input_sha256"] = verify_sources(refs)
            report["environment"] = {
                "python": platform.python_version(),
                "cadquery": cq.__version__,
            }
            (staging / "reports/validation.json").write_text(
                json.dumps(report, indent=2)
            )
            if not report["geometry_checks_passed"]:
                diagnostic = out / "failed_validation"
                (staging / "CAD/follower_geometry_checked.step").rename(
                    staging / "CAD/follower_geometry_unaccepted.step"
                )
                shutil.copytree(staging, diagnostic, dirs_exist_ok=True)
                print(f"FAILED: no accepted CAD updated. Diagnostics: {diagnostic}")
                return 2
            if args.render:
                from make_previews import make_previews

                make_previews(data, staging)
            for source in staging.rglob("*"):
                if source.is_file():
                    destination = out / source.relative_to(staging)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)
        print(
            "Geometry checks passed for the saved reference pose; mixed servo configuration retained."
        )
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"FAILED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
