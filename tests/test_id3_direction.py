"""Independent provenance and direction checks; all inputs are offline fixtures."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
from test_id3_motion import write_evidence

from arm_observer import id3_motion as motion

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "derive_direction", ROOT / "scripts/derive_id3_direction.py"
)
derive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(derive)


def read_fixture(tmp_path):
    old = ROOT / "reports/live_20261003T234141_004377+0900.jsonl"
    records = [json.loads(line) for line in old.read_text().splitlines()]
    for record in records:
        if record["kind"] == "metadata":
            record["simulated"] = False  # explicit offline representation of a hardware record
            record["acquisition_id"] = "offline-hardware-record-representation"
    path = tmp_path / "read.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path, records


def write_records(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def direction_record(tmp_path):
    log, _ = read_fixture(tmp_path)
    sources = []
    for name in ("manifest.json", "joints.json"):
        path = tmp_path / name
        path.write_bytes((derive.R3 / name).read_bytes())
        sources.append(path)
    derivation = derive.cad_direction(json.loads(sources[0].read_text()),
                                     json.loads(sources[1].read_text()))
    read = derive.folded_read(log)
    return {"kind": "cad_derivation", "motor_id": 3, "opening_count_sign": 1,
            "folded_count": read["folded_count"], "folded_read": read,
            "derivation": derivation,
            "sources": {str(p): derive.sha256(p) for p in sources}}


def test_changed_agreeing_signs_are_rejected(tmp_path):
    record = direction_record(tmp_path)
    record["opening_count_sign"] = -1
    record["derivation"]["opening_count_sign"] = -1
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, record))


def test_arbitrary_hashed_file_is_not_a_cad_source(tmp_path):
    record = direction_record(tmp_path)
    path = tmp_path / "not-cad.txt"
    path.write_text("not CAD")
    record["sources"] = {str(path): derive.sha256(path)}
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, record))


def test_read_log_must_exist_and_match_its_hash(tmp_path):
    record = direction_record(tmp_path)
    Path(record["folded_read"]["log"]).unlink()
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, record))


@pytest.mark.parametrize("simulated", [True, None, "false", 0])
def test_synthetic_or_unknown_read_source_is_rejected(tmp_path, simulated):
    path, records = read_fixture(tmp_path)
    records[0]["simulated"] = simulated
    write_records(path, records)
    with pytest.raises(ValueError):
        derive.folded_read(path)


@pytest.mark.parametrize("motor_id", [1, 3, 5])
@pytest.mark.parametrize("field,value", [("hardware_error", 32), ("device_alert", True)])
def test_fault_or_alert_on_any_motor_rejects_folded_log(tmp_path, motor_id, field, value):
    path, records = read_fixture(tmp_path)
    record = next(r for r in records if r["kind"] == "frame")
    motor = next(m for m in record["frame"]["motors"] if m["motor_id"] == motor_id)
    motor[field] = value
    write_records(path, records)
    with pytest.raises(ValueError):
        derive.folded_read(path)


def test_read_summary_is_independently_recomputed(tmp_path):
    record = direction_record(tmp_path)
    record["folded_read"]["frames"] = 999
    with pytest.raises(ValueError):
        motion.load_evidence(write_evidence(tmp_path, record))


def test_valid_cad_and_hardware_record_representation_is_accepted(tmp_path):
    record = direction_record(tmp_path)
    evidence = motion.load_evidence(write_evidence(tmp_path, copy.deepcopy(record)))
    assert evidence.sign == 1 and evidence.folded_count == 1153
