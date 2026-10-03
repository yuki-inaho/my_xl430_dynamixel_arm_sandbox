"""Trace supplier representation candidates without accepting internal contacts."""

import argparse
import json
import math
from pathlib import Path

from gripper_design.pg2 import _solid_only, digest
from scripts.assembly_io import bounds, read_step
from scripts.review_pg3_motion_clearance import EPSILON_MM
from scripts.triage_pg3_contacts import source_signature


def match_envelopes(reference, candidate):
    if not reference or len(reference) != len(candidate):
        raise ValueError("nonempty equal inventories required")
    for rows in (reference, candidate):
        if len({r["id"] for r in rows}) != len(rows):
            raise ValueError("duplicate occurrence identity")
        for row in rows:
            bb = row["bounds_mm"]
            if (
                len(bb) != 6
                or not all(math.isfinite(v) for v in bb)
                or any(bb[i] > bb[i + 3] for i in range(3))
            ):
                raise ValueError("finite ordered bounds required")
    result, used = [], set()
    for source in reference:
        choices = [
            target
            for target in candidate
            if target["solid_only"] == source["solid_only"]
            and target["solid_count"] == source["solid_count"]
            and max(abs(a - b) for a, b in zip(source["bounds_mm"], target["bounds_mm"]))
            <= EPSILON_MM
        ]
        if len(choices) != 1 or choices[0]["id"] in used:
            raise ValueError(f"missing, ambiguous or reused match for {source['id']}")
        target = choices[0]
        used.add(target["id"])
        solid_volume = source["solid_only"] and target["solid_only"]
        result.append(
            {
                "reference_id": source["id"],
                "candidate_id": target["id"],
                "max_bbox_error_mm": max(
                    abs(a - b) for a, b in zip(source["bounds_mm"], target["bounds_mm"])
                ),
                "volume_difference_mm3": abs(source["volume_mm3"] - target["volume_mm3"])
                if solid_volume
                else None,
                "area_difference_mm2": abs(source["area_mm2"] - target["area_mm2"]),
                "status": "ENVELOPE_CORRESPONDENCE_CANDIDATE",
                "material_equivalence_proven": False,
            }
        )
    return result


def describe(name, shape, label):
    is_solid = _solid_only(shape)
    if not shape.isValid():
        raise ValueError(f"invalid source topology: {name}")
    area = shape.Area()
    volume = shape.Volume() if is_solid else None
    if not math.isfinite(area) or (volume is not None and not math.isfinite(volume)):
        raise ValueError("nonfinite geometric signature")
    return {
        "id": name,
        "source_label": label,
        "shape_type": shape.ShapeType(),
        "solid_only": is_solid,
        "solid_count": len(shape.Solids()),
        "face_count": len(shape.Faces()),
        "bounds_mm": bounds(shape),
        "area_mm2": area,
        "volume_mm3": volume,
    }


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    vendor_path = Path("references/robotis-xl430-new-20180324/XL-430_new.stp")
    arm_path = Path("references/arm-r3/arm_XL430_R3.step")
    manifest_path = Path("references/arm-r3/manifest.json")
    if digest(vendor_path) != "5eeefe74bed670f70e993e103beab1d25e7bf2b9b297a7923066d96db550f2a1":
        raise ValueError("unreviewed official STEP")
    metadata = json.loads(manifest_path.read_text())
    meta = {r["name"]: r for r in metadata}
    if len(meta) != len(metadata):
        raise ValueError("duplicate R3 manifest identity")
    _vendor_doc, _vendor_st, vendor = read_step(vendor_path)
    _arm_doc, _arm_st, arm_all = read_step(arm_path)
    arm = [r for r in arm_all if r.name.startswith("M06_ref")]
    anchor = [r for r in vendor if r.name == "DC11_A01_DUMMY"]
    if len(vendor) != 35 or len(arm) != 35 or len(anchor) != 1:
        raise ValueError("reviewed motor inventory changed")
    body = next(r for r in arm if r.name == "M06_ref00")
    if meta[body.name]["source_leaf_name"] != "DC11_A01_DUMMY:1":
        raise ValueError("R3 body anchor changed")
    rotated_body = anchor[0].world.rotate((0, 0, 0), (0, 1, 0), 90)
    first, second = bounds(rotated_body), bounds(body.world)
    shift = tuple((second[i] + second[i + 3] - first[i] - first[i + 3]) / 2 for i in range(3))
    if max(abs(a - b) for a, b in zip(shift, (-0.2, 234.9, 164.6))) > EPSILON_MM:
        raise ValueError("body registration disagrees with reviewed arm placement")
    reference = [
        describe(
            f"official_leaf_{r.index:02d}",
            r.world.rotate((0, 0, 0), (0, 1, 0), 90).translate(shift),
            r.name,
        )
        for r in vendor
    ]
    candidate = [describe(r.name, r.world, meta[r.name]["source_leaf_name"]) for r in arm]
    correspondence = match_envelopes(reference, candidate)
    correspondence_by_arm = {r["candidate_id"]: r for r in correspondence}

    checkpoint_manifest = checkpoint / "review.json"
    saved = checkpoint / "arm_camera_mid_CANDIDATE.step"
    raw_path = checkpoint / "collisions_mid.json"
    manifest = json.loads(checkpoint_manifest.read_text())
    for path in (saved, raw_path):
        if digest(path) != manifest["output_sha256"][path.name]:
            raise ValueError("checkpoint SHA mismatch")
    _saved_doc, _saved_st, saved_rows = read_step(saved)
    shapes = {r.name: r.world for r in saved_rows}
    if len(shapes) != len(saved_rows):
        raise ValueError("ambiguous saved identity")
    retained = {f"ARM_{r.name}": r for r in arm if r.name != "M06_ref00"}
    if set(retained) != {n for n in shapes if n.startswith("ARM_M06_ref")}:
        raise ValueError("retained supplier inventory changed")
    signatures = {n: source_signature(shapes[n], r.world) for n, r in retained.items()}
    raw = json.loads(raw_path.read_text())
    internal = []
    for row in raw["pairs"]:
        pair = {row["a"], row["b"]}
        if row["status"] == "PASS" or "PG3_XL430_fixed" not in pair:
            continue
        names = pair & retained.keys()
        if not names:
            continue
        name = names.pop()
        original = retained[name].name
        internal.append(
            {
                "raw": row,
                "original_manifest": meta[original],
                "official_envelope_candidate": correspondence_by_arm[original],
                "retained_source_signature": signatures[name],
                "internal_contact_approved": False,
            }
        )
    report = {
        "scope": "source identity triage, not material equivalence or internal motor clearance",
        "transformation": {"rotation_Y_degrees": 90, "translation_mm": shift},
        "linear_matching_tolerance_mm": EPSILON_MM,
        "reference_records": reference,
        "arm_records": candidate,
        "correspondence": correspondence,
        "retained_signatures": signatures,
        "unresolved_internal_pairs": internal,
        "ordinal_identity_max_bbox_error_mm": max(
            max(abs(a - b) for a, b in zip(left["bounds_mm"], right["bounds_mm"]))
            for left, right in zip(reference, candidate)
        ),
        "source_sha256": {
            str(p): digest(p)
            for p in (
                vendor_path,
                arm_path,
                manifest_path,
                checkpoint_manifest,
                saved,
                raw_path,
                Path(__file__),
                Path("scripts/assembly_io.py"),
                Path("scripts/triage_pg3_contacts.py"),
                Path("scripts/review_pg3_motion_clearance.py"),
                Path("gripper_design/pg2.py"),
                Path("gripper_design/pg3.py"),
                Path("uv.lock"),
            )
        },
        "installation_approved": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(
        "correspondence candidates", len(correspondence), "raw unresolved internal", len(internal)
    )
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
