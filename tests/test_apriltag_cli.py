"""CLI end-to-end tests for arm-tag-sheet."""

import hashlib
import json

import pytest

from arm_observer.apriltag.cli import main

SHEET_1 = "apriltag_36h11_a4_sheet_1_ids_000-011.pdf"
SHEET_2 = "apriltag_36h11_a4_sheet_2_ids_012-023.pdf"


def test_generate_writes_two_pdfs_and_manifest(tmp_path):
    assert main(["generate", "--output-dir", str(tmp_path)]) == 0
    assert sorted(path.name for path in tmp_path.glob("*.pdf")) == [SHEET_1, SHEET_2]
    manifest = json.loads((tmp_path / "sheets.json").read_text(encoding="utf-8"))
    assert manifest["family"] == "tag36h11"
    assert [entry["ids"] for entry in manifest["sheets"]] == [
        list(range(12)),
        list(range(12, 24)),
    ]
    assert [entry["file"] for entry in manifest["sheets"]] == [SHEET_1, SHEET_2]
    for entry in manifest["sheets"]:
        digest = hashlib.sha256((tmp_path / entry["file"]).read_bytes()).hexdigest()
        assert entry["sha256"] == digest


def test_verify_synthetic_exit_zero(tmp_path):
    assert main(["verify", "--output-dir", str(tmp_path), "--rms-limit", "0.5"]) == 0
    report = json.loads((tmp_path / "synthetic_verify.json").read_text(encoding="utf-8"))
    assert sorted(report["detected_ids"]) == list(range(12))
    assert report["max_rms_px"] <= 0.5
    assert report["corner_refinement"] == "CORNER_REFINE_APRILTAG"
    assert (tmp_path / "synthetic_scene.png").exists()


@pytest.mark.parametrize("arguments", [
    ["generate", "--tag-size-mm", "nan"],
    ["generate", "--first-id", "-1"],
    ["verify", "--px-per-mm", "inf"],
    ["verify", "--blur-sigma", "-1"],
    ["verify", "--rms-limit", "nan"],
])
def test_invalid_input_leaves_no_artifacts(tmp_path, arguments):
    assert main([*arguments, "--output-dir", str(tmp_path)]) == 1
    assert not list(tmp_path.iterdir())


def test_image_write_failure_cannot_claim_success(tmp_path, monkeypatch):
    monkeypatch.setattr("arm_observer.apriltag.cli.cv2.imwrite", lambda *args: False)
    assert main(["verify", "--output-dir", str(tmp_path)]) == 1
    assert not (tmp_path / "synthetic_verify.json").exists()
