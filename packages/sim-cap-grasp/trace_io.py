"""Lossless contact-log storage; every original byte and physics step is retained."""

from __future__ import annotations

import gzip
import hashlib
import json
import signal
import subprocess
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def finalize_after_interrupt():
    """Accept one SIGINT; protect failure evidence from duplicate forwarded signals."""

    def interrupted(signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGINT, interrupted)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def contact_rows(directory):
    directory = Path(directory)
    plain = directory / "contacts.jsonl"
    formats = [directory / ("contacts.jsonl" + suffix) for suffix in ("", ".gz", ".zst")]
    if sum(p.exists() for p in formats) != 1:
        raise ValueError("Missing or ambiguous contact trace")
    if formats[1].exists():
        with gzip.open(formats[1], "rt") as handle:
            for line in handle:
                yield json.loads(line)
        return
    if plain.exists():
        with plain.open() as handle:
            for line in handle:
                yield json.loads(line)
        return
    compressed = directory / "contacts.jsonl.zst"
    storage = json.loads((directory / "storage.json").read_text())["contacts"]
    if storage.get("codec") != "zstd" or storage.get("path") != compressed.name:
        raise ValueError("Unsupported contact storage declaration")
    if file_sha(compressed) != storage["compressed_sha256"]:
        raise ValueError("Compressed contact-log hash mismatch")
    process = subprocess.Popen(["zstd", "-q", "-d", "-c", str(compressed)], stdout=subprocess.PIPE)
    digest = hashlib.sha256()
    count = 0
    try:
        for line in process.stdout:
            digest.update(line)
            count += len(line)
            yield json.loads(line)
        if process.wait() != 0:
            raise ValueError("Contact-log decompression failed")
        if (
            count != storage["uncompressed_bytes"]
            or digest.hexdigest() != storage["uncompressed_sha256"]
        ):
            raise ValueError("Lossless contact-log restoration mismatch")
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait()


def compress_contacts(directory):
    directory = Path(directory)
    plain = directory / "contacts.jsonl"
    if not plain.exists():
        return json.loads((directory / "storage.json").read_text())
    expected = file_sha(plain)
    expected_bytes = plain.stat().st_size
    temporary = directory / "contacts.jsonl.zst.partial"
    compressed = directory / "contacts.jsonl.zst"
    if compressed.exists() or temporary.exists():
        raise FileExistsError("Inspect existing compression attempt before retrying")
    subprocess.run(["zstd", "-q", "-T1", "-6", str(plain), "-o", str(temporary)], check=True)
    process = subprocess.Popen(["zstd", "-q", "-d", "-c", str(temporary)], stdout=subprocess.PIPE)
    digest = hashlib.sha256()
    count = 0
    with process.stdout:
        for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(block)
            count += len(block)
    if process.wait() or digest.hexdigest() != expected or count != expected_bytes:
        raise ValueError("Refusing to remove plain log: compression roundtrip failed")
    temporary.replace(compressed)
    storage = {
        "schema_version": 1,
        "lossless": True,
        "contacts": {
            "path": compressed.name,
            "codec": "zstd",
            "uncompressed_sha256": expected,
            "uncompressed_bytes": expected_bytes,
            "compressed_sha256": file_sha(compressed),
            "compressed_bytes": compressed.stat().st_size,
        },
    }
    (directory / "storage.json").write_text(json.dumps(storage, indent=2) + "\n")
    plain.unlink()  # Exact restoration was verified above; no samples are removed.
    return storage
