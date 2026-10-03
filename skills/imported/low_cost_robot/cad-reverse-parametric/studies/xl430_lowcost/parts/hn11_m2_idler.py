"""Printed HN11-I101 idler replacement using an M2 heat-set insert.

The replacement keeps the source idler ring envelope, its PCD16 hole pattern,
centre bore and cap interface, and converts the four 0-degree fastening holes
into blind heat-set insert seats opening on the outer (link-side) face.

The source HN11 STEP is third-party reference geometry.  It is read at runtime
from ``HN11_SOURCE_STEP`` (default: the ignored local work directory) and is
never copied into version control.

Generate:
    rtk uv run --project skills/cad-reverse-parametric \
        python skills/cad-reverse-parametric/studies/xl430_lowcost/parts/hn11_m2_idler.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType

from cadre import PartIntent


_HERE = Path(__file__).resolve()
_STUDY = _HERE.parents[1]
_CADRE_ROOT = _HERE.parents[3]
_REPO = _HERE.parents[5]
INTENT = _STUDY / "intent" / "hn11_m2_idler.yaml"
SOURCE_STEP = Path(
    os.environ.get(
        "HN11_SOURCE_STEP",
        _REPO / "temp" / "hn11_replacement_20260926" / "input" / "HN11.step",
    )
)
DEFAULT_OUT = _CADRE_ROOT / "outputs" / "prototypes" / "hn11_m2_idler"

PART_NAME = "hn11_m2_idler_xl430"


def _features(intent: PartIntent) -> dict[str, dict]:
    return {feature.name: feature.constraints for feature in intent.features}


def verify_source_sha(expected: str | None = None) -> str:
    """Return the source STEP SHA-256, or raise when it does not match.

    ``expected`` defaults to ``source.step_sha256`` in the intent file.  A
    mismatch means the input geometry was substituted or changed, so design
    work must stop instead of silently continuing.
    """
    if not SOURCE_STEP.is_file():
        raise FileNotFoundError(
            f"source HN11 STEP not found: {SOURCE_STEP}. Set HN11_SOURCE_STEP."
        )
    expected = expected if expected is not None else _source_block().get("step_sha256")
    actual = hashlib.sha256(SOURCE_STEP.read_bytes()).hexdigest()
    if expected and actual != expected:
        raise ValueError(
            f"source STEP SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def _source_solids() -> list[cq.Shape]:
    verify_source_sha()
    assembly = cq.importers.importStep(str(SOURCE_STEP)).val()
    return list(assembly.Solids())


def _max_dim(shape: cq.Shape) -> float:
    box = shape.BoundingBox()
    return max(box.xlen, box.ylen, box.zlen)


def load_source_rotor() -> cq.Shape:
    solids = _source_solids()
    rotor = next(s for s in solids if _max_dim(s) > 20.0)
    return rotor


def load_source_cap() -> cq.Shape:
    solids = _source_solids()
    return next(s for s in solids if 9.0 < _max_dim(s) < 12.0)


def _source_thickness_mm() -> float:
    return float(load_source_rotor().BoundingBox().zlen)


def _source_block() -> dict:
    import yaml

    data = yaml.safe_load(INTENT.read_text(encoding="utf-8"))
    return dict(data.get("source", {}))


def insert_spec(intent: PartIntent | None = None) -> dict:
    """Return the validated provisional insert-seat specification.

    Source faces and thickness come from the measured source rotor so the seat
    geometry is not rounded.  The seat depth is clamped so the floor keeps the
    requested minimum even when the measured thickness is slightly under 3.5.
    """
    intent = intent or PartIntent.load(INTENT)
    seat = dict(_features(intent)["insert_seat"])
    seat.update(_source_block())
    seat.setdefault("confirmed", False)
    box = load_source_rotor().BoundingBox()
    seat["outer_face_world_z_mm"] = box.zmin
    seat["motor_face_world_z_mm"] = box.zmax
    seat["thickness_mm"] = box.zlen
    floor_min = float(seat["minimum_floor_mm"])
    seat["insert_bore_depth_mm"] = min(
        float(seat["insert_bore_depth_mm"]), box.zlen - floor_min
    )
    seat["floor_mm"] = box.zlen - float(seat["insert_bore_depth_mm"])
    return seat


def validate_insert_dimensions(
    intent: PartIntent | None = None, **overrides
) -> dict:
    """Validate provisional insert dimensions; raise ValueError when unusable.

    These are prototype gates, not strength qualification.  Out-of-range values
    must be rejected so upstream callers cannot silently accept a wrong insert.
    """
    spec = insert_spec(intent)
    spec.update(overrides)
    od = float(spec["insert_outer_diameter_mm"])
    length = float(spec["insert_length_mm"])
    bore = float(spec["insert_bore_diameter_mm"])
    depth = float(spec["insert_bore_depth_mm"])
    pitch = float(spec["insert_pitch_mm"])
    floor_min = float(spec["minimum_floor_mm"])
    thickness = float(spec["thickness_mm"])

    if not 2.5 <= od <= 3.6:
        raise ValueError(f"insert outer diameter out of range: {od}")
    if not 2.5 <= length <= 4.0:
        raise ValueError(f"insert length out of range: {length}")
    if bore >= od - 0.2:
        raise ValueError(f"bore {bore} leaves no insert wall for OD {od}")
    if pitch <= 0.0:
        raise ValueError(f"invalid pitch: {pitch}")
    if floor_min < 0.2:
        raise ValueError(f"minimum floor too small: {floor_min}")
    floor = thickness - depth
    if floor < floor_min - 1e-9:
        raise ValueError(f"floor {floor} below minimum {floor_min}")
    if length > depth + 0.3 + 1e-9:
        raise ValueError(f"insert length {length} protrudes too far beyond seat {depth}")
    spec["floor_mm"] = floor
    spec["confirmed"] = False
    return spec


def _cylinder_faces(shape: cq.Shape) -> list[dict]:
    rows = []
    for face in shape.Faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        cylinder = surface.Cylinder()
        direction = cylinder.Axis().Direction()
        point = cylinder.Axis().Location()
        box = face.BoundingBox()
        rows.append(
            {
                "diameter_mm": 2.0 * float(cylinder.Radius()),
                "axis_dir": (direction.X(), direction.Y(), direction.Z()),
                "axis_pt": (point.X(), point.Y(), point.Z()),
                "zmin": box.zmin,
                "zmax": box.zmax,
                "zlen": box.zlen,
            }
        )
    return rows


def coaxial_cylinder_faces(shape: cq.Shape, axis_xy: tuple[float, float] | None = None) -> list[dict]:
    rows = _cylinder_faces(shape)
    if axis_xy is not None:
        for row in rows:
            dx = row["axis_pt"][0] - axis_xy[0]
            dy = row["axis_pt"][1] - axis_xy[1]
            row["radial_mm"] = (dx * dx + dy * dy) ** 0.5
    return rows


def seat_features(shape: cq.Shape, intent: PartIntent | None = None) -> list[dict]:
    spec = insert_spec(intent)
    axis_xy = tuple(float(v) for v in spec["axis_world_xy_mm"])
    outer_z = float(spec["outer_face_world_z_mm"])
    motor_z = float(spec["motor_face_world_z_mm"])
    bore = float(spec["insert_bore_diameter_mm"])
    radius = bore / 2.0
    seats = []
    for row in coaxial_cylinder_faces(shape, axis_xy):
        dz = abs(row["axis_dir"][2])
        if dz < 0.999:
            continue
        if abs(row["diameter_mm"] - bore) > 0.06:
            continue
        if abs(row["radial_mm"] - float(spec["pcd_mm"]) / 2.0) > 0.06:
            continue
        if abs(row["zmin"] - outer_z) > 0.06:
            continue
        zmax = row["zmax"]
        floor = motor_z - zmax
        seats.append(
            {
                "diameter_mm": row["diameter_mm"],
                "radial_mm": row["radial_mm"],
                "depth_mm": zmax - row["zmin"],
                "floor_mm": floor,
                "blind": floor > 1e-6,
                "opens_toward": "outer" if abs(row["zmin"] - outer_z) < 1e-6 else "motor",
                "zmin": row["zmin"],
                "zmax": zmax,
            }
        )
    return seats


def make_rotor(intent: PartIntent | None = None) -> cq.Shape:
    """Bore blind heat-set insert seats into a copy of the source rotor."""
    intent = intent or PartIntent.load(INTENT)
    spec = validate_insert_dimensions(intent)
    fill = _features(intent)["motor_face_clearance_fill"]
    rotor = load_source_rotor()
    axis_xy = tuple(float(v) for v in spec["axis_world_xy_mm"])
    outer_z = float(spec["outer_face_world_z_mm"])
    motor_z = float(spec["motor_face_world_z_mm"])
    thickness = float(spec["thickness_mm"])
    bore = float(spec["insert_bore_diameter_mm"])
    depth = float(spec["insert_bore_depth_mm"])
    counterbore = float(fill["fill_diameter_mm"])
    counterbore_depth = float(fill["fill_depth_mm"])
    import math

    for angle in spec["family_angles_deg"]:
        rad = math.radians(float(angle))
        x = axis_xy[0] + float(spec["pcd_mm"]) / 2.0 * math.cos(rad)
        y = axis_xy[1] + float(spec["pcd_mm"]) / 2.0 * math.sin(rad)
        # The 0-degree counterbore reaches the rotor OD, so its fill is inset by
        # 0.01 mm.  The plug is inset 0.03 mm and the seat is cut at the nominal
        # radius, so the effective seat diameter equals the nominal bore and no
        # boolean surface sits on an exact coincidence (keeps the mesh watertight).
        counterbore_fill = cq.Solid.makeCylinder(
            counterbore / 2.0 - 0.01, counterbore_depth,
            cq.Vector(x, y, motor_z - counterbore_depth), cq.Vector(0, 0, 1),
        )
        hole_plug = cq.Solid.makeCylinder(
            bore / 2.0 - 0.03, thickness, cq.Vector(x, y, outer_z), cq.Vector(0, 0, 1)
        )
        rotor = rotor.fuse(counterbore_fill).fuse(hole_plug)
    rotor = rotor.clean()
    for angle in spec["family_angles_deg"]:
        rad = math.radians(float(angle))
        x = axis_xy[0] + float(spec["pcd_mm"]) / 2.0 * math.cos(rad)
        y = axis_xy[1] + float(spec["pcd_mm"]) / 2.0 * math.sin(rad)
        seat = cq.Solid.makeCylinder(
            bore / 2.0, depth, cq.Vector(x, y, outer_z), cq.Vector(0, 0, 1)
        )
        rotor = rotor.cut(seat)
    return rotor.clean()


def make_cap(intent: PartIntent | None = None) -> cq.Shape:
    """Return the unmodified source cap solid."""
    return load_source_cap()


def coupon_spec(intent: PartIntent | None = None) -> dict:
    intent = intent or PartIntent.load(INTENT)
    return dict(_features(intent)["coupon"])


def make_coupon(intent: PartIntent | None = None) -> cq.Shape:
    intent = intent or PartIntent.load(INTENT)
    spec = coupon_spec(intent)
    sx, sy, sz = (float(v) for v in spec["block_xyz_mm"])
    diameters = [float(v) for v in spec["hole_diameters_mm"]]
    hole_depth = float(spec["hole_depth_mm"])
    coupon = (
        cq.Workplane("XY")
        .box(sx, sy, sz, centered=(True, True, False))
        .val()
    )
    start = -sx / 2.0 + 4.0
    step = (sx - 8.0) / max(1, len(diameters) - 1)
    for i, diameter in enumerate(diameters):
        x = start + i * step
        cutter = cq.Solid.makeCylinder(
            diameter / 2.0, hole_depth,
            cq.Vector(x, 0.0, sz - hole_depth), cq.Vector(0, 0, 1),
        )
        coupon = coupon.cut(cutter)
        # Raised pip count identifies the hole diameter after printing
        # (1 pip = smallest diameter, 5 pips = largest).
        for k in range(i + 1):
            px = x - (i * 1.6) / 2.0 + k * 1.6
            pip = cq.Solid.makeCylinder(
                0.7, 0.6, cq.Vector(px, -4.0, sz), cq.Vector(0, 0, 1)
            )
            coupon = coupon.fuse(pip)
    return coupon.clean()


def bom(intent: PartIntent | None = None) -> dict:
    spec = insert_spec(intent)
    return {
        "part": PART_NAME,
        "per_set": [
            {"item": "hn11_m2_rotor", "qty": 1, "note": "printed, 0-degree blind insert seats"},
            {"item": "hn11_m2_cap", "qty": 1, "note": "printed from source cap geometry"},
            {"item": "M2 heat-set insert", "qty": 4, "note": f"ESJNNK {spec['insert_thread']}x{spec['insert_length_mm']}x{spec['insert_outer_diameter_mm']} (OD provisional)"},
            {"item": "M2 pan-head screw", "qty": 4,
             "note": ("through the link plate into the rotor inserts; length per joint: "
                      "M2x5 where the idler-side plate span is 2.0 mm (R3 J2), "
                      "M2x7 candidate where it is 4.0 mm (R3 J3/J4). Engagement is "
                      "capped by the 3.0 mm seat depth; confirm stock and the head "
                      "seat before ordering")},
            {"item": "M3x5 flat-head screw", "qty": 1, "note": "official FHS M3x5, centre of the printed cap"},
        ],
        "insert_seat": {k: spec[k] for k in (
            "insert_bore_diameter_mm", "insert_bore_depth_mm", "minimum_floor_mm",
            "insert_outer_diameter_mm", "insert_length_mm", "pcd_mm", "confirmed",
        )},
        "depth_margin_note": (
            "seat depth 3.0 mm equals the nominal insert length, so no SPIROL-style "
            "length+2-pitch margin is available in the 3.5 mm rotor; verify the "
            "heat-set result on one printed body set before the six-set run"
        ),
        "unqualified": ["strength", "fit", "retention", "service life", "servo centre thread depth"],
    }


def export(out: Path = DEFAULT_OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    intent = PartIntent.load(INTENT)
    rotor = make_rotor(intent)
    cap = make_cap(intent)
    coupon = make_coupon(intent)
    if not rotor.isValid() or len(rotor.Solids()) != 1:
        raise RuntimeError("rotor is not one valid solid")
    paths = {
        "rotor_step": out / "hn11_m2_rotor.step",
        "rotor_stl": out / "hn11_m2_rotor.stl",
        "cap_step": out / "hn11_m2_cap.step",
        "cap_stl": out / "hn11_m2_cap.stl",
        "assembly_step": out / "hn11_m2_idler_assembly.step",
        "coupon_step": out / "hn11_m2_insert_coupon.step",
        "coupon_stl": out / "hn11_m2_insert_coupon.stl",
        "bom": out / "hn11_m2_idler_bom.json",
    }
    cq.exporters.export(rotor, str(paths["rotor_step"]))
    cq.exporters.export(rotor, str(paths["rotor_stl"]), tolerance=0.05, angularTolerance=0.1)
    cq.exporters.export(cap, str(paths["cap_step"]))
    cq.exporters.export(cap, str(paths["cap_stl"]), tolerance=0.05, angularTolerance=0.1)
    cq.exporters.export(cq.Compound.makeCompound([rotor, cap]), str(paths["assembly_step"]))
    cq.exporters.export(coupon, str(paths["coupon_step"]))
    cq.exporters.export(coupon, str(paths["coupon_stl"]), tolerance=0.05, angularTolerance=0.1)
    paths["bom"].write_text(json.dumps(bom(intent), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {name: str(path) for name, path in paths.items()}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    print(json.dumps(export(args.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
