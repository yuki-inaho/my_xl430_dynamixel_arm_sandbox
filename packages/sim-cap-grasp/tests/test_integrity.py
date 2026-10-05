"""Independent malformed input/model controls; no synthetic grasp-success tests."""

import json
from argparse import Namespace

import mujoco
import pytest

import build_scene
from evaluate import validate_model
from run import run


def test_cap_passive_support_is_rejected():
    m = mujoco.MjModel.from_xml_path(str(build_scene.MODEL / "scene.xml"))
    assert validate_model(m) == []
    j = m.body("cap").jntadr[0]
    v = int(m.jnt_dofadr[j])
    m.dof_damping[v : v + 6] = 100
    assert "cap_passive_support" in validate_model(m)


def test_stale_and_tampered_cache_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(build_scene, "MODEL", tmp_path)
    source = tmp_path / "source.obj"
    source.write_text("source geometry")
    cache = tmp_path / "decomposition/example"
    cache.mkdir(parents=True)
    part = cache / "part_000.obj"
    part.write_text("preserved part")
    report = {"source_sha256": "wrong", "source_scale_to_m": 1.0, "parts": 1}
    (cache / "report.json").write_text(json.dumps(report))
    (tmp_path / "cache_hashes.json").write_text(
        json.dumps({str(part.relative_to(tmp_path)): build_scene.sha(part)})
    )
    with pytest.raises(ValueError, match="Stale"):
        build_scene.decompose_mesh("example", source)
    report["source_sha256"] = build_scene.sha(source)
    (cache / "report.json").write_text(json.dumps(report))
    part.write_text("tampered part")
    with pytest.raises(ValueError, match="hash mismatch"):
        build_scene.decompose_mesh("example", source)


def test_missing_inputs_do_not_repair_or_rewrite_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(build_scene, "INPUT", tmp_path)
    names = ["viewer/scene.xml"] + [
        f"scanfit/{p}_{s}.stl" for p in ("cot", "foam", "band") for s in ("L", "R")
    ]
    manifest = json.dumps({n: "missing" for n in names})
    (tmp_path / "hashes.json").write_text(manifest)
    with pytest.raises(ValueError, match="Missing"):
        build_scene.prepare_inputs()
    assert (tmp_path / "hashes.json").read_text() == manifest
    assert not (tmp_path / "viewer").exists()


def test_invalid_cli_does_not_create_partial_trial(tmp_path):
    target = tmp_path / "trial"
    for name, value in [
        ("mass", float("nan")),
        ("duration", -1),
        ("timestep", float("inf")),
        ("friction", 0),
    ]:
        args = Namespace(
            output=target,
            seed=0,
            mass=0.0015,
            duration=13.0,
            timestep=0.001,
            friction=0.7,
            no_close=False,
        )
        setattr(args, name, value)
        with pytest.raises(ValueError, match="finite and positive"):
            run(args)
        assert not target.exists()
