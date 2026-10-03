"""TDD tests for the study parts (studies/xl430_lowcost/parts).

Run: uv run pytest -q tests/test_parts.py

These pin the part-reconstruction behaviour. Per part <p> (shoulder_to_elbow,
elbow_to_wrist):
  - test_<p>_builds          : generates a watertight solid (手順5)
  - test_<p>_family_match     : C-A2 hole families == real part — in-face pattern
                                (count, dia Δ≤0.1mm, in-face center NN≤0.15mm). NOTE:
                                C-A2 compares the per-family in-FACE pattern; the axial
                                seat position is a separate concern (checked in the part
                                module's own inspect output), so this gate is in-plane.
  - test_<p>_xl430_clearance  : XL430 body clears its pocket/cradle (手順7, C-B1)

The study layer (`import domain`, part modules) is not an installed package, so we
inject its directory onto sys.path here (a conftest would also work).
"""
import sys
import importlib.util
import tempfile
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]                                   # cad-reverse-parametric
_STUDY = _ROOT / "studies" / "xl430_lowcost"
_HW_STEP = _ROOT.parents[1] / "hardware/follower/step"
_HW_STL = _ROOT.parents[1] / "hardware/follower/stl"

# Make `import domain` (used inside the part module) resolvable.
if str(_STUDY) not in sys.path:
    sys.path.insert(0, str(_STUDY))


def _load_part_module(name: str):
    spec = importlib.util.spec_from_file_location(
        f"{name}_part", _STUDY / "parts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_study_module(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_study", _STUDY / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _family_match(real_step: Path, recon_step: Path, recon_filter=None):
    """C-A2: family set equal, diameter Δ≤0.1mm, axis-line count equal, in-face center
    NN match ≤0.15mm. Returns (ok, report-list).

    Keys by (diameter@2dp, axis_dir@1dp) and GROUPS families per key into a list, so
    two near-equal-diameter families on the same axis (e.g. phi2.30 + phi2.34 along Z)
    are NEITHER merged nor silently dropped — a 1dp key would collide and a dict would
    overwrite, hiding a family (a false pass). Per key, families are matched greedily by
    axis-line count + center pattern.

    `recon_filter` (optional) post-processes the recon family list before comparison. It is
    applied to recon only, never to the real reference, so it cannot hide a real-part hole."""
    from collections import defaultdict
    from cadre import cylinder_faces, checks
    real = cylinder_faces(real_step)["hole_families"]
    recon = cylinder_faces(recon_step)["hole_families"]
    if recon_filter is not None:
        recon = recon_filter(recon)

    def key(f):
        return (round(f["diameter"], 2), tuple(round(x, 1) for x in f["axis_dir"]))
    rb, cb = defaultdict(list), defaultdict(list)
    for f in real:
        rb[key(f)].append(f)
    for f in recon:
        cb[key(f)].append(f)

    report = []
    ok = set(rb) == set(cb)
    if not ok:
        report.append(f"family key set mismatch real={sorted(rb)} recon={sorted(cb)}")
    for k in rb:
        rfs, cfs = rb[k], cb.get(k, [])
        if len(rfs) != len(cfs):
            report.append(f"{k}: family count {len(rfs)} vs {len(cfs)}"); ok = False; continue
        remaining = list(cfs)
        for rf in rfs:
            best, bi = None, -1
            for i, cf in enumerate(remaining):
                if cf["axes"] != rf["axes"]:
                    continue
                m = checks.hole_pattern_match(rf["centers"], cf["centers"], tol_mm=0.15)
                if m.passed and (best is None or m.value < best.value):
                    best, bi = m, i
            if best is None:
                report.append(f"{k} axes={rf['axes']}: no center-matching recon family")
                ok = False
            else:
                dd = abs(rf["diameter"] - remaining[bi]["diameter"])
                fok = dd <= 0.1
                ok = ok and fok
                report.append(f"{k} axes={rf['axes']}: diaΔ={dd:.3f} centerNN={best.value} "
                              f"pass={fok}")
                remaining.pop(bi)
    return ok, report


def _brep_or_skip():
    from cadre import brep_available
    if not brep_available():
        pytest.skip("cadquery/OCP not available")


def _to_trimesh(model):
    """Tessellate a cadquery Workplane to a watertight trimesh.Trimesh via STL."""
    import tempfile
    import trimesh
    from cadre import parametric
    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "m"
        parametric.export(model, stem, formats=("stl",))
        return trimesh.load(f"{stem}.stl", force="mesh")


def _export_step(model):
    """Export a model to a temp STEP and return the path (kept alive by caller's tmp)."""
    import tempfile
    from cadre import parametric
    td = tempfile.mkdtemp()
    stem = Path(td) / "recon"
    parametric.export(model, stem, formats=("step",))
    return Path(f"{stem}.step")


def _extension_features(mod):
    intent = mod.PartIntent.load(mod.INTENT)
    return {f.name: f for f in intent.features}


def _assert_functional_family(report, label, diameter, expected_centers, expected_axes):
    from cadre import checks

    families = [
        f for f in report["hole_families"]
        if abs(float(f["diameter"]) - diameter) <= 0.05
        and tuple(round(x, 1) for x in f["axis_dir"]) == (1.0, 0.0, 0.0)
    ]
    assert len(families) == 1, (
        f"{label}: expected one functional family d={diameter}, got {families}; "
        f"all_families={report['hole_families']}"
    )
    family = families[0]
    match = checks.hole_pattern_match(expected_centers, family["centers"], tol_mm=0.15)
    assert family["axes"] == expected_axes and match.passed, (
        f"{label}: axes/centers changed; expected_axes={expected_axes} "
        f"actual_axes={family['axes']} centerNN={match.value} faces={family['faces']} "
        f"expected_centers={expected_centers} actual_centers={family['centers']}"
    )
    assert family["faces"] >= family["axes"], (
        f"{label}: face count should remain auditable; family={family}"
    )


def test_shoulder_to_elbow_builds():
    """手順5: stage-1 reconstruction generates a watertight solid."""
    _brep_or_skip()
    import domain
    mod = _load_part_module("shoulder_to_elbow")
    model = mod.make_shoulder_to_elbow(domain.XL430, domain.XL330)
    mesh = _to_trimesh(model)
    assert mesh.is_watertight, "stage-1 reconstruction must be a closed solid"
    assert mesh.volume > 0


def test_shoulder_to_elbow_family_match():
    """手順6 / C-A2: reconstructed hole families == the real part's families
    (count, diameter Δ≤0.1mm, in-face center ≤0.15mm). Mesh-equiv C-A1 is NOT expected
    to pass (organic surface) — feature-level equivalence is the gate."""
    _brep_or_skip()
    real_step = _HW_STEP / "shoulder_to_elbow.step"
    if not real_step.exists():
        pytest.skip(f"real part missing: {real_step}")
    import domain
    mod = _load_part_module("shoulder_to_elbow")
    recon = _export_step(mod.make_shoulder_to_elbow(domain.XL430, domain.XL330))
    ok, report = _family_match(real_step, recon)
    assert ok, "C-A2 family mismatch:\n  " + "\n  ".join(report)


def test_shoulder_to_elbow_xl430_clearance():
    """手順7 / C-B1: after the XL430 swap, the downstream XL430 servo body clears the
    bracket (checks.envelope_clearance == 0 material inside the keepout).

    Geometry of THIS bracket (from the real part): the downstream tail is a flat tab
    X[-14.8,14.8], holes at x=-14.75 along X. The downstream servo (joint3) bolts onto
    the -X face of the tab and its body extends further -X — it is NOT cradled inside
    the bracket. So the keepout is the XL430 envelope placed on the -X side of the
    mount plane (offset outward by half the servo X-extent + the swap clearance). The
    bracket must not protrude into that body volume."""
    _brep_or_skip()
    import domain
    from cadre import checks, parametric
    mod = _load_part_module("shoulder_to_elbow")
    swapped = mod.make_shoulder_to_elbow(domain.XL430, domain.XL430)
    part_mesh = _to_trimesh(swapped)

    intent = mod.PartIntent.load(mod.INTENT)
    dn = {f.name: f for f in intent.features}["downstream_servo_mount"].constraints
    centers = dn["mount_centers_mm"]
    x_face = centers[0][0]                                 # -14.75 mount plane (along X)
    ys = [c[1] for c in centers]
    zs = [c[2] for c in centers]
    y_c, z_c = (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0
    env = domain.XL430.envelope
    clr = float(dn["clearance_mm"])
    # envelope_proxy maps env to box(w, d, h): X-extent = env.w (28.5). Servo body
    # extends -X from the mount face -> center it at x_face - clr - w/2.
    x_body = x_face - clr - env.w / 2.0
    keepout = parametric.envelope_proxy(env, clearance=0.0).translate((x_body, y_c, z_c))
    keep_mesh = _to_trimesh(keepout)

    res = checks.envelope_clearance(part_mesh, keep_mesh, samples=4000)
    assert res.passed, f"XL430 body intrudes into the bracket: {res.detail}"


# ---- elbow_to_wrist (joint3 motor cradle — the real XL330->XL430 swap) ----

def test_elbow_to_wrist_builds():
    """手順5: stage-1 reconstruction generates a watertight solid."""
    _brep_or_skip()
    import domain
    mod = _load_part_module("elbow_to_wrist")
    mesh = _to_trimesh(mod.make_elbow_to_wrist(domain.XL330))
    assert mesh.is_watertight, "stage-1 reconstruction must be a closed solid"
    assert mesh.volume > 0


def test_elbow_to_wrist_family_match():
    """手順6 / C-A2: reconstructed hole families == the real part (in-face pattern:
    count, dia Δ≤0.1mm, in-face center NN≤0.15mm). C-A1 mesh-equiv NOT expected."""
    _brep_or_skip()
    real_step = _HW_STEP / "elbow_to_wrist.step"
    if not real_step.exists():
        pytest.skip(f"real part missing: {real_step}")
    import domain
    mod = _load_part_module("elbow_to_wrist")
    recon = _export_step(mod.make_elbow_to_wrist(domain.XL330))
    ok, report = _family_match(real_step, recon)
    assert ok, "C-A2 family mismatch:\n  " + "\n  ".join(report)


def test_elbow_to_wrist_xl430_clearance():
    """手順7 / C-B1: after the XL330->XL430 swap, the XL430 motor body fits in the
    cradle cavity with zero bracket-material intrusion (envelope_clearance == 0 inside).

    Geometry: the motor is cradled between the two X side-rails, above the base plate
    (Z=0), output axis = Y. The keepout is the XL430 envelope placed in the cavity:
    centered in X over the footprint, lifted above the base plate, set back from the
    Y=42 end wall. The grown bracket must not pinch the (now larger) XL430 body."""
    _brep_or_skip()
    import domain
    from cadre import checks, parametric
    mod = _load_part_module("elbow_to_wrist")
    swapped = mod.make_elbow_to_wrist(domain.XL430)
    part_mesh = _to_trimesh(swapped)

    intent = mod.PartIntent.load(mod.INTENT)
    cr = {f.name: f for f in intent.features}["motor_cradle"].constraints
    clr = float(cr["clearance_mm"])
    wall = float(cr["wall_mm"])
    env = domain.XL430.envelope
    mw, mh, md = env.as_tuple()
    # envelope_proxy maps env(w,h,d) -> box(w, d, h): X-extent=w, Y-extent=d, Z-extent=h.
    foot_x = max(22.0, mw + 2 * (clr + wall))
    x_c = foot_x / 2.0                          # X centered in the footprint
    z_c = mod.BASE_T + clr + mh / 2.0           # Z-extent = h, lifted above base plate
    y_c = (mod.FACE_Y - mod.END_WALL_T) - clr - md / 2.0   # Y-extent = d, back off wall
    keepout = parametric.envelope_proxy(env, clearance=0.0).translate((x_c, y_c, z_c))
    keep_mesh = _to_trimesh(keepout)

    res = checks.envelope_clearance(part_mesh, keep_mesh, samples=4000)
    assert res.passed, f"XL430 motor body intrudes into the bracket: {res.detail}"


# ---- batch: the 4 peripheral parts (gripper static/moving, extension, rotation) ----
#
# Finding (honest): these parts mount on the servo HORN or are already wider than the
# servo body (and shoulder_rotation holds joint1 = XL430 already), so the XL330->XL430
# swap is a GEOMETRIC NO-OP for them — verified, not assumed. The real geometric swap
# burden was on shoulder_to_elbow (mixed connector) and elbow_to_wrist (joint3 cradle).
# Hence the per-part gates here are: builds + C-A2 family_match (the kinematic interface),
# plus, for swap-applicable parts, a recorded swap-effect (no silent change).

def _build_via(part_name, builder_attr, *args):
    import domain  # noqa: F401
    mod = _load_part_module(part_name)
    return mod, getattr(mod, builder_attr)(*args)


def test_gripper_static_part_builds():
    _brep_or_skip()
    import domain
    mod, model = _build_via("gripper_static_part", "make_gripper_static", domain.XL330)
    mesh = _to_trimesh(model)
    assert mesh.is_watertight and mesh.volume > 0


def test_gripper_static_part_family_match():
    _brep_or_skip()
    real = _HW_STEP / "gripper_static_part.step"
    if not real.exists():
        pytest.skip("real part missing")
    import domain
    mod, model = _build_via("gripper_static_part", "make_gripper_static", domain.XL330)
    ok, report = _family_match(real, _export_step(model))
    assert ok, "C-A2 mismatch:\n  " + "\n  ".join(report)


def test_gripper_static_part_swap_recorded():
    """C-B (swap evidence): the XL430 variant is generated; its geometric effect is
    measured. For this horn/jaw part the swap is a documented NO-OP (footprint already
    clears the XL430 body) — asserted explicitly so it cannot be silently misreported."""
    _brep_or_skip()
    import domain
    mod = _load_part_module("gripper_static_part")
    o = _to_trimesh(mod.make_gripper_static(domain.XL330))
    x = _to_trimesh(mod.make_gripper_static(domain.XL430))
    assert o.is_watertight and x.is_watertight
    assert abs(x.volume - o.volume) < 1.0, "swap unexpectedly changed geometry; update finding"


def test_gripper_moving_part_family_match():
    """gripper_moving reproduces the real OPEN-recess part (phi31 breaches the side
    walls, exactly as the real part's single open phi31 face) -> not watertight by
    design; family match (B-rep) is still the gate."""
    _brep_or_skip()
    real = _HW_STEP / "gripper_moving_part.step"
    if not real.exists():
        pytest.skip("real part missing")
    import domain
    mod, model = _build_via("gripper_moving_part", "make_gripper_moving", domain.XL330)
    ok, report = _family_match(real, _export_step(model))
    assert ok, "C-A2 mismatch:\n  " + "\n  ".join(report)


def test_gripper_moving_part_swap_recorded():
    _brep_or_skip()
    import domain
    mod = _load_part_module("gripper_moving_part")
    o = _to_trimesh(mod.make_gripper_moving(domain.XL330))
    x = _to_trimesh(mod.make_gripper_moving(domain.XL430))
    assert o.volume > 0 and x.volume > 0
    assert abs(x.volume - o.volume) < 1.0, "horn-only part: swap must be a no-op"


def test_gripper_moving_printable_variant_is_watertight_without_moving_holes():
    """Print-only repair may add outer material, but must keep functional holes."""
    _brep_or_skip()
    import domain
    from cadre import cylinder_faces

    mod = _load_part_module("gripper_moving_part")
    canonical = _export_step(mod.make_gripper_moving(domain.XL430))
    printable_model = mod.make_gripper_moving_printable(domain.XL430)
    printable_mesh = _to_trimesh(printable_model)
    printable_step = _export_step(printable_model)

    assert printable_mesh.is_watertight and printable_mesh.is_volume
    source = cylinder_faces(canonical)["hole_families"]
    repaired = cylinder_faces(printable_step)["hole_families"]
    for family in source:
        candidates = [
            f for f in repaired
            if abs(float(f["diameter"]) - float(family["diameter"])) <= 0.05
            and tuple(round(x, 1) for x in f["axis_dir"]) == tuple(round(x, 1) for x in family["axis_dir"])
            and int(f["axes"]) == int(family["axes"])
        ]
        assert candidates, f"printable variant lost family {family}; repaired={repaired}"
        assert any(
            __import__("cadre").checks.hole_pattern_match(
                family["centers"], candidate["centers"], tol_mm=0.15
            ).passed
            for candidate in candidates
        ), f"printable variant moved family {family}; repaired={repaired}"


def test_print_readiness_detects_and_repairs_gripper_moving_nonmanifold_stl():
    """Print readiness gate fails canonical non-manifold STL and passes print repair."""
    _brep_or_skip()
    mod = _load_study_module("validate_print_readiness")

    fail_code, fail_result = mod._run(repair=False)
    assert fail_code == 2
    failed_names = {item["name"] for item in fail_result["blocking_failures"]}
    assert "gripper_moving_part_xl430" in failed_names

    with tempfile.TemporaryDirectory() as td:
        ok_code, ok_result = mod._run(print_dir=Path(td) / "print", repair=True)
    assert ok_code == 0 and ok_result["passed"], ok_result
    repair = ok_result["package"]["gripper_moving_part_xl430"]
    assert repair["family_preservation_passed"]
    assert repair["repaired_mesh"]["watertight"]
    assert repair["repaired_mesh"]["is_volume"]
    assert repair["repaired_mesh"]["nonmanifold_or_boundary_edges"] == 0


def test_elbow_to_wrist_extension_builds():
    _brep_or_skip()
    import domain
    mod, model = _build_via("elbow_to_wrist_extension", "make_extension", domain.XL330)
    mesh = _to_trimesh(model)
    assert mesh.is_watertight and mesh.volume > 0


def test_elbow_to_wrist_extension_family_match():
    _brep_or_skip()
    real = _HW_STEP / "elbow_to_wrist_extension.step"
    if not real.exists():
        pytest.skip("real part missing")
    import domain
    mod, model = _build_via("elbow_to_wrist_extension", "make_extension", domain.XL330)
    ok, report = _family_match(real, _export_step(model))
    assert ok, "C-A2 mismatch:\n  " + "\n  ".join(report)


def test_elbow_to_wrist_extension_original_shape_preserved():
    """No approved change mask exists, so the generated part must be the original STEP.

    This is the gate that prevents a local bolt-pattern concern from becoming a destructive
    global redesign. A candidate that adds a collar or changes the organic end profile fails
    here before min-wall/interference checks are considered.
    """
    _brep_or_skip()
    import domain

    mod, model = _build_via("elbow_to_wrist_extension", "make_extension", domain.XL330)
    feat = _extension_features(mod)
    preserve = feat["original_shape_preservation"].constraints
    bbox = preserve["bbox_mm"]
    solid = model.val()
    bb = solid.BoundingBox()

    assert abs(bb.xmin - float(bbox["x"][0])) < 0.01
    assert abs(bb.xmax - float(bbox["x"][1])) < 0.01
    assert abs(bb.ymin - float(bbox["y"][0])) < 0.01
    assert abs(bb.ymax - float(bbox["y"][1])) < 0.01
    assert abs(bb.zmin - float(bbox["z"][0])) < 0.01
    assert abs(bb.zmax - float(bbox["z"][1])) < 0.01

    ok, report = _family_match(_HW_STEP / "elbow_to_wrist_extension.step", _export_step(model))
    assert ok, "original-shape preservation C-A2 mismatch:\n  " + "\n  ".join(report)

    real_stl = _HW_STL / "elbow_to_wrist_extension.stl"
    if not real_stl.exists():
        pytest.skip(f"real STL missing: {real_stl}")
    from cadre import compare, verdict, EquivalenceThresholds, parametric
    with tempfile.TemporaryDirectory() as td:
        candidate = Path(td) / "candidate"
        parametric.export(model, candidate, formats=("stl",))
        cmp = compare(real_stl, Path(f"{candidate}.stl"), samples=4000)
    v = verdict(cmp, EquivalenceThresholds())
    assert v["equivalent"], (
        "original-shape preservation C-A1 mismatch; candidate is not the original outline. "
        f"verdict={v} bbox_delta={cmp['bbox_delta_mm']} "
        f"surface={cmp['surface_distance']} volume_delta_pct={cmp['volume_delta_pct']}"
    )


def test_elbow_to_wrist_extension_functional_families_preserved():
    """Functional cut families remain the original auditable holes and partial reliefs."""
    _brep_or_skip()
    import domain
    from cadre import cylinder_faces

    mod = _load_part_module("elbow_to_wrist_extension")
    feat = _extension_features(mod)
    _, model = _build_via("elbow_to_wrist_extension", "make_extension", domain.XL330)
    report = cylinder_faces(_export_step(model))

    horn = feat["upstream_horn_mount"].constraints
    relief = feat["upstream_partial_relief"].constraints
    down = feat["downstream_mount"].constraints
    expected_diameters = {
        round(float(horn["hole_diameter_mm"]), 2),
        round(float(relief["diameter_mm"]), 2),
        round(float(down["hole_diameter_mm"]), 2),
    }
    families = report["hole_families"]
    actual_diameters = {round(float(f["diameter"]), 2) for f in families}
    assert actual_diameters <= expected_diameters, (
        "unexpected cylindrical hole family appeared; "
        f"expected_diameters={sorted(expected_diameters)} "
        f"actual_diameters={sorted(actual_diameters)} "
        f"all_families={families}"
    )
    _assert_functional_family(
        report, "upstream taps", float(horn["hole_diameter_mm"]),
        [[0.0, float(y), float(z)] for y, z in horn["diamond_centers_yz_mm"]],
        expected_axes=4,
    )
    _assert_functional_family(
        report, "upstream partial relief arcs", float(relief["diameter_mm"]),
        [[0.0, float(y), float(z)] for y, z in relief["centers_yz_mm"]],
        expected_axes=2,
    )
    _assert_functional_family(
        report, "downstream M2 through holes", float(down["hole_diameter_mm"]),
        [[float(x), float(y), float(z)] for x, y, z in down["mount_centers_mm"]],
        expected_axes=2,
    )


def test_elbow_to_wrist_extension_has_no_unapproved_circular_collar():
    """Reject the destructive R12/phi24 circular collar until a local mask is approved."""
    _brep_or_skip()
    import domain
    from cadre import cylinder_faces

    mod = _load_part_module("elbow_to_wrist_extension")
    _, model = _build_via("elbow_to_wrist_extension", "make_extension", domain.XL330)
    report = cylinder_faces(_export_step(model))
    diameters = {round(float(f["diameter"]), 2) for f in report["hole_families"]}
    assert 24.0 not in diameters, (
        "unapproved circular collar wall appeared; original-shape-preserving mode must not "
        f"introduce a phi24/R12 support family. families={report['hole_families']}"
    )


def test_elbow_to_wrist_extension_fastening_holes_remain_boltable():
    """The four servo/horn fastening pilot holes remain the original auditable family."""
    _brep_or_skip()
    import domain
    from cadre import cylinder_faces

    mod = _load_part_module("elbow_to_wrist_extension")
    feat = _extension_features(mod)
    horn = feat["upstream_horn_mount"].constraints
    _, model = _build_via("elbow_to_wrist_extension", "make_extension", domain.XL330)
    report = cylinder_faces(_export_step(model))
    _assert_functional_family(
        report, "upstream fastening holes", float(horn["hole_diameter_mm"]),
        [[0.0, float(y), float(z)] for y, z in horn["diamond_centers_yz_mm"]],
        expected_axes=4,
    )
    family = [
        f for f in report["hole_families"]
        if abs(float(f["diameter"]) - float(horn["hole_diameter_mm"])) <= 0.05
        and tuple(round(x, 1) for x in f["axis_dir"]) == (1.0, 0.0, 0.0)
    ][0]
    assert family["faces"] == 8, (
        "original blind fastening holes should expose two cylindrical faces per axis; "
        f"family={family}"
    )


def test_elbow_to_wrist_extension_link_length_preserved():
    """C-B5: preserve the 90.1mm functional link dimension across the swap.

    No approved change mask exists for this organic part, so XL430 must be a geometric
    no-op here. This gate pins the configured link length and no-bbox-growth behaviour.
    """
    _brep_or_skip()
    import domain
    mod = _load_part_module("elbow_to_wrist_extension")
    feat = _extension_features(mod)
    link_length = float(feat["link_beam"].constraints["link_length_y_mm"])
    o = _to_trimesh(mod.make_extension(domain.XL330))
    x = _to_trimesh(mod.make_extension(domain.XL430))
    assert abs(link_length - 90.1) < 0.001
    assert abs(o.bounds[0][1] - -73.046) < 0.2
    assert abs(x.bounds[0][1] - o.bounds[0][1]) < 0.2
    assert abs(x.bounding_box.extents[1] - o.bounding_box.extents[1]) < 0.2


def test_elbow_to_wrist_extension_swap_is_noop_until_change_mask_exists():
    """XL430 must not change this part until an accepted local edit mask exists."""
    _brep_or_skip()
    import domain

    mod = _load_part_module("elbow_to_wrist_extension")
    feat = _extension_features(mod)
    assert feat["original_shape_preservation"].constraints["active_local_edit"] is False
    o = _to_trimesh(mod.make_extension(domain.XL330))
    x = _to_trimesh(mod.make_extension(domain.XL430))
    assert abs(x.volume - o.volume) < 1.0
    assert max(abs(float(a) - float(b)) for a, b in zip(o.bounds.flatten(), x.bounds.flatten())) < 0.01


def test_elbow_to_wrist_extension_preservation_validator_cli():
    """The standalone validation helper must agree with the pytest preservation gates."""
    _brep_or_skip()
    mod = _load_study_module("validate_extension_preservation")
    code, result = mod._run(samples=500)
    assert code == 0 and result["passed"], result


def test_fastening_interface_validator_detects_shifted_extension_red_pattern():
    """TDD red pattern: the fastening overlay validator must fail shifted hole centers."""
    _brep_or_skip()
    mod = _load_study_module("validate_fastening_interfaces")
    reference = _HW_STEP / "elbow_to_wrist_extension.step"
    code, result = mod._run(
        reference=reference,
        candidate=reference,
        candidate_translate=(0.0, 1.0, 0.0),
        fail_on_mismatch=True,
    )
    assert code == 2
    assert not result["passed"]
    assert result["worst_center_nn_mm"] > 0.15


def test_fastening_interface_validator_accepts_extension_original_and_current():
    """Original STEP and current generated no-op model keep the same fastening centers."""
    _brep_or_skip()
    mod = _load_study_module("validate_fastening_interfaces")
    reference = _HW_STEP / "elbow_to_wrist_extension.step"
    current = _ROOT / "outputs" / "parts" / "elbow_to_wrist_extension_xl430.step"

    original_code, original = mod._run(reference=reference, candidate=reference)
    current_code, current_result = mod._run(reference=reference, candidate=current)

    assert original_code == 0 and original["passed"], original
    assert current_code == 0 and current_result["passed"], current_result


def test_liaison_interface_prototype_reports_shifted_mounting_red_pattern():
    """Liaison prototype must surface failed mounting alignment, not only raw holes."""
    _brep_or_skip()
    mod = _load_study_module("build_liaison_interfaces")
    reference = _HW_STEP / "elbow_to_wrist_extension.step"
    _, result = mod._run(
        reference=reference,
        candidate=reference,
        candidate_translate=(0.0, 1.0, 0.0),
    )
    assert not result["passed"]
    failed = [m for l in result["liaisons"] for m in l["mountings"] if not m["passed"]]
    assert failed
    assert max(m["center_nn_mm"] for m in failed) > 0.15


def test_liaison_interface_prototype_accepts_current_extension_model():
    """Current no-op extension produces liaison records with all mountings aligned."""
    _brep_or_skip()
    mod = _load_study_module("build_liaison_interfaces")
    _, result = mod._run()
    assert result["passed"], result
    ids = {liaison["id"] for liaison in result["liaisons"]}
    assert "elbow_to_wrist_extension.upstream_horn_mount" in ids
    assert "elbow_to_wrist_extension.downstream_mount" in ids
    assert all(m["passed"] for l in result["liaisons"] for m in l["mountings"])


def test_assembly_liaison_characterization_detects_mating_offsets():
    """Actual assembly liaison prototype must expose real mating offsets, not hide them."""
    _brep_or_skip()
    mod = _load_study_module("validate_assembly_liaisons")
    _, result = mod._run()
    assert not result["passed"]
    liaisons = {liaison["id"]: liaison for liaison in result["liaisons"]}
    assert liaisons["assembly.connector_116.upstream_horn_pair"]["contact"]["min_distance_mm"] == 0.0
    assert liaisons["assembly.connector_116.upstream_horn_pair"]["mountings"][0]["center_nn_mm"] > 1.0
    assert liaisons["assembly.connector_116.downstream_mount_pair"]["mountings"][0]["center_nn_mm"] >= 1.0


def test_assembly_liaison_characterization_reports_depth_and_tool_access_fields():
    """Assembly liaison JSON includes screw-depth and tool-access status fields."""
    _brep_or_skip()
    mod = _load_study_module("validate_assembly_liaisons")
    _, result = mod._run()
    for liaison in result["liaisons"]:
        fastener = liaison["fastener_set"]
        assert "screw_length_depth_check" in fastener
        assert "tool_access_check" in fastener
        assert fastener["screw_length_depth_check"]["status"] in {"pass", "fail", "unknown", "not_applicable"}
        assert fastener["tool_access_check"]["status"] in {"pass", "fail", "unknown", "not_applicable"}


def test_rule_catalog_detects_shifted_candidate_red_pattern_and_stores_duckdb():
    """Data-driven rules must fail shifted holes and persist the run to DuckDB."""
    _brep_or_skip()
    mod = _load_study_module("validate_rule_catalog")
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "validation_rules.duckdb"
        code, result = mod._run(
            profile_id="candidate_preservation",
            candidate_translate=(0.0, 1.0, 0.0),
            preservation_samples=500,
            db_path=db,
            sync_db=True,
            store_run=True,
        )
    assert code == 2
    assert not result["passed"]
    assert result["blocking_failed_count"] > 0
    failed_ids = {item["rule_id"] for item in result["failed_rules"]}
    assert "hole_family_preservation.worst_center_nn" in failed_ids
    assert result["duckdb"]["counts"]["rules"] >= 10
    assert result["duckdb"]["counts"]["validation_runs"] == 1
    assert result["duckdb"]["counts"]["rule_results"] == len(result["rule_results"])


def test_rule_catalog_accepts_current_candidate_and_stores_duckdb():
    """Current no-op candidate passes blocking catalog rules and can be queried later."""
    _brep_or_skip()
    mod = _load_study_module("validate_rule_catalog")
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "validation_rules.duckdb"
        code, result = mod._run(
            profile_id="candidate_preservation",
            preservation_samples=500,
            db_path=db,
            sync_db=True,
            store_run=True,
        )
        inspect = mod._inspect_db(db)
    assert code == 0 and result["passed"], result
    assert result["blocking_failed_count"] == 0
    assert inspect["counts"]["rule_catalogs"] == 1
    assert inspect["counts"]["rule_profiles"] >= 2
    assert inspect["counts"]["rule_groups"] >= 7
    assert inspect["counts"]["rules"] == result["duckdb"]["counts"]["rules"]
    assert inspect["counts"]["validation_runs"] == 1


def test_rule_catalog_assembly_profile_records_nonblocking_mating_findings():
    """Known arm.step mating offsets are retained as non-blocking characterization rules."""
    _brep_or_skip()
    mod = _load_study_module("validate_rule_catalog")
    code, result = mod._run(profile_id="assembly_characterization")
    assert code == 0
    assert result["passed"], result
    assert result["failed_count"] > 0
    assert result["blocking_failed_count"] == 0
    failed_ids = {item["rule_id"] for item in result["failed_rules"]}
    assert "actual_mating_alignment.actual_center_offsets" in failed_ids
    assert "fastener_depth.depth_status_pass_or_na" in failed_ids
    assert "tool_access.tool_status_pass_or_na" in failed_ids


def test_shoulder_rotation_builds_and_no_swap():
    """shoulder_rotation holds joint1 = XL430 already -> SWAP NOT APPLICABLE. Build
    stage-1 and assert the intent records swap_applicable: false (explicit, not silent)."""
    _brep_or_skip()
    import yaml
    mod = _load_part_module("shoulder_rotation")
    mesh = _to_trimesh(mod.make_shoulder_rotation())
    assert mesh.is_watertight and mesh.volume > 0
    doc = yaml.safe_load(Path(mod.INTENT).read_text())
    assert doc.get("swap_applicable") is False, "must explicitly mark swap not applicable"


def test_shoulder_rotation_family_match():
    _brep_or_skip()
    real = _HW_STEP / "shoulder_rotation.step"
    if not real.exists():
        pytest.skip("real part missing")
    mod, model = _build_via("shoulder_rotation", "make_shoulder_rotation")
    ok, report = _family_match(real, _export_step(model))
    assert ok, "C-A2 mismatch:\n  " + "\n  ".join(report)
