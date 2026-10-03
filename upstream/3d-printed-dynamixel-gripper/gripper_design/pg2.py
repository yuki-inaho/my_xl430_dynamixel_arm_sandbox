"""Read-only intake and independent checks for the PG2 R5 crank-slider candidate.

Donor source is evidence, not imported Python. Dimensions below describe this
frozen revision only. Angles are mechanism-relative, never motor commands.
"""

import hashlib
import json
import math
import stat
import zipfile
from itertools import combinations
from pathlib import Path, PurePosixPath

from scripts.assembly_io import bounds, read_step


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or str(path) != name:
        raise ValueError(f"unsafe archive path: {name}")
    return path


def import_archive(
    archive: Path, destination: Path, *, archive_root="PG2_XL430", manifest_name="MANIFEST.sha256"
) -> dict:
    """Verify every sealed file before extracting into an unused directory."""
    if destination.exists():
        raise FileExistsError(destination)
    _safe_path(archive_root)
    _safe_path(manifest_name)
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive entries")
        if sum(member.file_size for member in members) > 500_000_000:
            raise ValueError("archive exceeds 500 MB intake limit")
        for member in members:
            path = _safe_path(member.filename.rstrip("/") if member.is_dir() else member.filename)
            if path.parts[0] != archive_root or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("unexpected archive root or symlink")
        manifest = f"{archive_root}/{manifest_name}"
        entries = {}
        for line in zipped.read(manifest).decode("utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            _safe_path(relative)
            if relative in entries or len(expected) != 64:
                raise ValueError("invalid manifest entry")
            entries[relative] = expected
            data = zipped.read(f"{archive_root}/{relative}")
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"SHA mismatch: {relative}")
        actual = {m.filename for m in members if not m.is_dir()}
        if actual != {manifest} | {f"{archive_root}/{name}" for name in entries}:
            raise ValueError("unsealed or missing archive files")
        destination.mkdir(parents=True, exist_ok=False)
        zipped.extractall(destination)
    receipt = {
        "archive_sha256": digest(archive),
        "archive_name": archive.name,
        "verified_file_count": len(entries),
        "files": entries,
        "manifest_sha256": digest(destination / manifest),
        "manifest_name": manifest_name,
        "archive_root": archive_root,
        "fabrication_approved": False,
        "powered_operation_approved": False,
    }
    (destination / "intake.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def verify_intake(root: Path) -> dict:
    receipt = json.loads((root.parent / "intake.json").read_text())
    for name, expected in receipt["files"].items():
        _safe_path(name)
        if digest(root / name) != expected:
            raise ValueError(f"SHA mismatch after intake: {name}")
    if digest(root / receipt.get("manifest_name", "MANIFEST.sha256")) != receipt["manifest_sha256"]:
        raise ValueError("manifest changed after intake")
    return receipt


def slider_state(angle_degrees: float) -> dict:
    if not math.isfinite(angle_degrees) or not 30 <= angle_degrees <= 140:
        raise ValueError("PG2 R5 mechanism angle must be finite and within 30..140 degrees")
    radius, length = 15.0, 36.0
    angle = math.radians(angle_degrees)
    pin_x, pin_y = radius * math.cos(angle), radius * math.sin(angle)
    jaw_x = pin_x + math.sqrt(length**2 - pin_y**2)
    closed_angle = math.radians(140)
    closed_x = radius * math.cos(closed_angle) + math.sqrt(
        length**2 - (radius * math.sin(closed_angle)) ** 2
    )
    return {
        "angle_degrees": angle_degrees,
        "right_pin_x_mm": jaw_x,
        "left_pin_x_mm": -jaw_x,
        "crank_pin_xy_mm": [pin_x, pin_y],
        "opening_mm": 2 * (jaw_x - closed_x) + 0.8,
        "link_closure_error_mm": abs(math.hypot(jaw_x - pin_x, pin_y) - length),
    }


def _solid_only(shape) -> bool:
    if shape.ShapeType() == "Solid":
        return True
    if shape.ShapeType() in {"Compound", "CompSolid"}:
        children = list(shape)
        return bool(children) and all(_solid_only(child) for child in children)
    return False


def scan_pairs(shapes: dict, *, tolerance_mm3=1e-4) -> list[dict]:
    """Inventory every unordered pair. No fastener or supplier-contact exclusions."""
    results = []
    for (a, first), (b, second) in combinations(shapes.items(), 2):
        row = {"a": a, "b": b}
        try:
            aa, bb = bounds(first), bounds(second)
            # Strict separation only: a touching shell is not automatically clear.
            if any(aa[i + 3] < bb[i] or bb[i + 3] < aa[i] for i in range(3)):
                row.update(status="PASS", reason="bbox_separated")
            elif not _solid_only(first) or not _solid_only(second):
                row.update(status="UNKNOWN", reason="non_solid_overlap")
            else:
                common = first.intersect(second)
                volume = sum(abs(s.Volume()) for s in common.Solids())
                if not math.isfinite(volume) or not common.isValid():
                    raise ValueError("invalid Boolean result")
                row.update(
                    status="FAIL" if volume > tolerance_mm3 else "PASS",
                    reason="solid_intersection" if volume > tolerance_mm3 else "boolean_clear",
                    volume_mm3=volume,
                )
        except Exception as exc:  # noqa: BLE001 - kernel failures must remain visible.
            row.update(status="ERROR", reason="kernel_error", detail=str(exc))
        results.append(row)
    return results


def inspect_saved_assembly(path: Path, angle_degrees: float) -> tuple[dict, dict]:
    _, _, occurrences = read_step(path)
    names = [row.name for row in occurrences]
    if len(set(names)) != len(names):
        raise ValueError("duplicate names: explicit occurrence mapping required")
    shapes = {row.name: row.world for row in occurrences}
    inventory = [
        {
            "name": row.name,
            "path": row.path,
            "valid": row.world.isValid(),
            "solid_count": len(row.world.Solids()),
            "solid_only": _solid_only(row.world),
            "bbox_mm": bounds(row.world),
        }
        for row in occurrences
    ]
    right, left = shapes["jaw_1"], shapes["jaw_-1"]
    gap = bounds(right)[0] - bounds(left)[3]
    mirrored = right.mirror("YZ")
    symmetry_error = left.cut(mirrored).Volume() + mirrored.cut(left).Volume()
    expected = slider_state(angle_degrees)
    pairs = scan_pairs(shapes)
    # These four intersections are donor-declared thread engagements, not
    # independently verified mating interfaces. Keep them visible and UNKNOWN.
    threaded = {f"servo_tap_{side}_{y}" for side in (-1, 1) for y in (-28, -4)}
    for row in pairs:
        other = (
            row["b"] if row["a"] == "XL430_W250" else row["a"] if row["b"] == "XL430_W250" else None
        )
        if other in threaded and row["status"] == "FAIL":
            row.update(status="UNKNOWN", reason="donor_declared_thread_engagement_not_verified")
    geometry_status = (
        "PASS"
        if (
            all(i["valid"] for i in inventory)
            and abs(gap - expected["opening_mm"]) <= 0.01
            and abs(symmetry_error) <= 1e-4
        )
        else "FAIL"
    )
    return {
        "path": str(path),
        "sha256": digest(path),
        "angle_degrees": angle_degrees,
        "occurrences": inventory,
        "occurrence_count": len(inventory),
        "measured_opening_mm": gap,
        "analytic_state": expected,
        "jaw_mirror_symmetric_difference_mm3": symmetry_error,
        "geometry_status": geometry_status,
        "pair_count": len(pairs),
        "pairs": pairs,
        "fabrication_approved": False,
        "whole_arm_fit_approved": False,
    }, shapes
