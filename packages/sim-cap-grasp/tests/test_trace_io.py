import gzip
import json
import signal

import pytest

from trace_io import compress_contacts, contact_rows, finalize_after_interrupt


def test_lossless_roundtrip_and_corruption_rejected(tmp_path):
    original = [
        {"i": i, "time": i * 0.001, "contacts": [{"force": [i * 0.23, 0, 0, 0, 0, 0]}]}
        for i in range(100)
    ]
    text = "".join(json.dumps(row) + "\n" for row in original)
    (tmp_path / "contacts.jsonl").write_text(text)
    assert list(contact_rows(tmp_path)) == original
    storage = compress_contacts(tmp_path)
    assert storage["lossless"]
    assert not (tmp_path / "contacts.jsonl").exists()
    assert list(contact_rows(tmp_path)) == original
    compressed = tmp_path / "contacts.jsonl.zst"
    compressed.write_bytes(compressed.read_bytes() + b"bad")
    with pytest.raises(ValueError, match="hash mismatch"):
        list(contact_rows(tmp_path))


def test_gzip_compatibility_and_ambiguous_trace_rejected(tmp_path):
    row = {"i": 0, "time": 0.0, "contacts": []}
    with gzip.open(tmp_path / "contacts.jsonl.gz", "wt") as stream:
        stream.write(json.dumps(row) + "\n")
    assert list(contact_rows(tmp_path)) == [row]
    (tmp_path / "contacts.jsonl").write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="ambiguous"):
        list(contact_rows(tmp_path))


def test_duplicate_interrupt_does_not_interrupt_finalizer():
    previous = signal.getsignal(signal.SIGINT)
    with finalize_after_interrupt():
        try:
            signal.raise_signal(signal.SIGINT)
        except KeyboardInterrupt:
            signal.raise_signal(signal.SIGINT)
        else:
            raise AssertionError("First SIGINT was not delivered")
    assert signal.getsignal(signal.SIGINT) == previous
