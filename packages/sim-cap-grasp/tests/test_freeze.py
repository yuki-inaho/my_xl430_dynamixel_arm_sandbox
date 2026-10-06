import pytest

import batch


def test_freeze_detects_code_drift_and_pins_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    monkeypatch.setattr(batch, "MODEL", tmp_path / "model")
    (tmp_path / "model").mkdir()
    (tmp_path / "model/scene.xml").write_text("test model")
    (tmp_path / "evidence").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_sample.py").write_text("test evidence")
    for name in batch.RUNTIME_FILES:
        (tmp_path / name).write_text("original " + name)
    record = batch.freeze("unit", 37)
    assert {
        "assumptions.json",
        "pyproject.toml",
        "uv.lock",
        "trace_io.py",
        "tests/test_sample.py",
    } <= set(record["inputs"])
    assert batch.verify_freeze("unit", 37)
    (tmp_path / "protocol.json").write_text("tampered")
    with pytest.raises(ValueError, match="Frozen input changed"):
        batch.verify_freeze("unit", 37)
