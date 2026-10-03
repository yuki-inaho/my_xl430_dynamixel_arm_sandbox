"""Flatten OrcaSlicer presets for headless CLI slicing (`--load-settings`).

The GUI resolves preset ``inherits`` chains; the CLI config loader does NOT.
Passing an extracted system preset (e.g. ``~/.config/OrcaSlicer/system/
Creality/machine/Creality Ender-3 Pro 0.4 nozzle.json``) straight to
``--load-settings``/``--load-filaments`` slices with C++ defaults for every
inherited key — which fails validation or silently changes the profile. This
module resolves the chain and writes a flat, self-contained preset that keeps
the metadata the CLI requires (``type``, ``name``, ``from``) and the
compatibility field it checks (``compatible_printers``), while dropping
preset bookkeeping (``inherits``, ``setting_id``, ``*_condition``, ...).

Verified against the OrcaSlicer 2.4.2 CLI on 2026-09-22:

- leaf without ``from`` (system/User/user)  -> "...'s from unsupported"
- unresolved chain (no ``G92 E0`` inherited) -> exit -51, relative-E check
- process whose ``compatible_printers`` does not name the machine -> exit -17

Usage:

    python -m cadre.orca_presets \
        "$HOME/.config/OrcaSlicer/system/Creality/machine/Creality Ender-3 Pro 0.4 nozzle.json" \
        "$HOME/.config/OrcaSlicer/system/Creality/process/0.20mm Standard @Creality Ender3 Pro 0.4.json" \
        "$HOME/.config/OrcaSlicer/system/OrcaFilamentLibrary/filament/Generic PLA @System.json" \
        --out-dir /tmp/orca-profiles
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Preset bookkeeping the CLI config loader ignores or rejects; inheritance is
# resolved here, so it must not survive into the flat file.
_PRESET_ONLY_KEYS = {
    "inherits",
    "setting_id",
    "instantiation",
    "renamed_from",
    "print_settings_id",
    "filament_settings_id",
    "printer_settings_id",
}
_DROP_SUFFIXES = ("_condition",)


def build_preset_index(system_root: Path) -> dict[str, Path]:
    """Map every preset ``name`` under ``system_root`` to its file (first wins)."""
    index: dict[str, Path] = {}
    for path in sorted(Path(system_root).rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name")
        if name and name not in index:
            index[name] = path
    return index


def resolve_preset(preset_path: Path, system_root: Path) -> dict:
    """Return ``preset_path`` with its ``inherits`` chain merged base -> leaf."""
    index = build_preset_index(system_root)
    chain: list[dict] = []
    path = Path(preset_path)
    seen: set[Path] = set()
    while True:
        if path in seen:
            raise ValueError(f"inheritance cycle at {path}")
        seen.add(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid preset JSON {path}: {exc}") from exc
        chain.append(data)
        parent = data.get("inherits")
        if not parent:
            break
        if parent not in index:
            raise KeyError(
                f"inherited preset not found under {system_root}: {parent}"
            )
        path = index[parent]

    merged: dict = {}
    for data in reversed(chain):
        merged.update(data)
    return {
        key: value
        for key, value in merged.items()
        if key not in _PRESET_ONLY_KEYS and not key.endswith(_DROP_SUFFIXES)
    }


def write_resolved(preset_path: Path, out_dir: Path, system_root: Path) -> Path:
    """Resolve ``preset_path`` and write the flat JSON into ``out_dir``."""
    resolved = resolve_preset(preset_path, system_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / Path(preset_path).name
    out_path.write_text(
        json.dumps(resolved, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flatten OrcaSlicer system presets for the headless CLI."
    )
    parser.add_argument("presets", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--system-root",
        type=Path,
        default=Path.home() / ".config" / "OrcaSlicer" / "system",
        help="extracted OrcaSlicer system profile root",
    )
    args = parser.parse_args(argv)

    for preset in args.presets:
        out_path = write_resolved(preset, args.out_dir, args.system_root)
        print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())