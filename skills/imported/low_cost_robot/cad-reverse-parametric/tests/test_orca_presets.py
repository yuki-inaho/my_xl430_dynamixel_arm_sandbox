"""Tests for OrcaSlicer CLI preset flattening. Run: uv run pytest -q"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadre.orca_presets import (
    build_preset_index,
    main,
    resolve_preset,
    write_resolved,
)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _machine_tree(root: Path) -> Path:
    _write(
        root / "Custom/machine/fdm_base.json",
        {
            "type": "machine",
            "name": "fdm_base",
            "from": "system",
            "before_layer_change_gcode": ";BEFORE_LAYER_CHANGE\nG92 E0\n",
            "printer_model": "Base Model",
        },
    )
    _write(
        root / "Creality/machine/leaf 0.4 nozzle.json",
        {
            "type": "machine",
            "name": "leaf 0.4 nozzle",
            "inherits": "fdm_base",
            "from": "system",
            "setting_id": "SomeId",
            "instantiation": "true",
            "nozzle_diameter": ["0.4"],
            "printer_model": "Creality Ender-3 Pro",
            "compatible_printers_condition": "",
        },
    )
    return root / "Creality/machine/leaf 0.4 nozzle.json"


def test_resolve_merges_inheritance_and_keeps_cli_metadata(tmp_path):
    root = tmp_path / "system"
    leaf = _machine_tree(root)

    resolved = resolve_preset(leaf, root)

    # inherited base keys survive the flattening (G92 E0 gates the -51 error)
    assert resolved["before_layer_change_gcode"] == ";BEFORE_LAYER_CHANGE\nG92 E0\n"
    # leaf overrides the base
    assert resolved["printer_model"] == "Creality Ender-3 Pro"
    assert resolved["nozzle_diameter"] == ["0.4"]
    # metadata the CLI loader requires
    assert resolved["type"] == "machine"
    assert resolved["name"] == "leaf 0.4 nozzle"
    assert resolved["from"] == "system"
    # preset bookkeeping and empty condition fields are dropped
    assert "inherits" not in resolved
    assert "setting_id" not in resolved
    assert "instantiation" not in resolved
    assert "compatible_printers_condition" not in resolved


def test_process_compatible_printers_survive(tmp_path):
    root = tmp_path / "system"
    _write(
        root / "Custom/process/fdm_process_common.json",
        {"type": "process", "name": "fdm_process_common", "from": "system"},
    )
    leaf = root / "Creality/process/0.20mm Standard.json"
    _write(
        leaf,
        {
            "type": "process",
            "name": "0.20mm Standard",
            "inherits": "fdm_process_common",
            "from": "system",
            "compatible_printers": ["Creality Ender-3 Pro 0.4 nozzle"],
        },
    )

    resolved = resolve_preset(leaf, root)

    # the CLI tests this list against the machine preset name (else exit -17)
    assert resolved["compatible_printers"] == ["Creality Ender-3 Pro 0.4 nozzle"]


def test_build_preset_index_finds_all_tiers(tmp_path):
    root = tmp_path / "system"
    leaf = _machine_tree(root)

    index = build_preset_index(root)

    assert index["fdm_base"] == root / "Custom/machine/fdm_base.json"
    assert index["leaf 0.4 nozzle"] == leaf


def test_missing_parent_raises(tmp_path):
    root = tmp_path / "system"
    leaf = root / "orphan.json"
    _write(leaf, {"type": "machine", "name": "orphan", "inherits": "nope"})

    with pytest.raises(KeyError, match="nope"):
        resolve_preset(leaf, root)


def test_inheritance_cycle_raises(tmp_path):
    root = tmp_path / "system"
    _write(root / "a.json", {"name": "a", "inherits": "b"})
    _write(root / "b.json", {"name": "b", "inherits": "a"})

    with pytest.raises(ValueError, match="cycle"):
        resolve_preset(root / "a.json", root)


def test_write_resolved_round_trip(tmp_path):
    root = tmp_path / "system"
    leaf = _machine_tree(root)
    out_dir = tmp_path / "profiles"

    out_path = write_resolved(leaf, out_dir, root)

    assert out_path == out_dir / "leaf 0.4 nozzle.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data == resolve_preset(leaf, root)


def test_main_writes_every_requested_preset(tmp_path, capsys):
    root = tmp_path / "system"
    leaf = _machine_tree(root)
    out_dir = tmp_path / "profiles"

    ret = main([str(leaf), "--system-root", str(root), "--out-dir", str(out_dir)])

    assert ret == 0
    assert (out_dir / "leaf 0.4 nozzle.json").is_file()
    assert capsys.readouterr().out.strip().endswith("leaf 0.4 nozzle.json")