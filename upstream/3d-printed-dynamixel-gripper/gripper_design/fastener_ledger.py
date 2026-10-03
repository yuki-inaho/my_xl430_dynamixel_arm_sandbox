"""Fail-closed validation for the jaw fastener and support inventory."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "specs" / "jaw_fastener_ledger.yaml"


class FastenerLedgerError(ValueError):
    pass


def load_fastener_ledger(path: str | Path = DEFAULT_LEDGER) -> dict[str, Any]:
    ledger = yaml.safe_load(Path(path).read_text())
    validate_fastener_ledger(ledger)
    return ledger


def validate_fastener_ledger(ledger: dict[str, Any]) -> None:
    required_interfaces = {
        "xl430_output_side",
        "xl430_idler_side",
        "pinion_opposite_support_axis",
    }
    interfaces = ledger.get("interfaces", {})
    if set(interfaces) != required_interfaces:
        raise FastenerLedgerError("jaw ledger must inventory every changed support interface")
    for name, interface in interfaces.items():
        if interface.get("dimensions_confirmed") is not False:
            raise FastenerLedgerError(f"{name} dimensions cannot be confirmed without hardware")
        statuses = [value for key, value in interface.items() if key.endswith("_status")]
        if any(status == "PASS" for status in statuses):
            raise FastenerLedgerError(f"{name} cannot PASS before physical confirmation")
        if not interface.get("reason"):
            raise FastenerLedgerError(f"{name} requires an UNKNOWN reason")
    required_controls = {
        "insufficient_engagement",
        "bottoms_out",
        "head_collision",
        "tool_shaft_collision",
        "tool_handle_collision",
        "counterhold_unavailable",
        "unsupported_tool_motion",
    }
    if set(ledger.get("known_bad_controls", [])) != required_controls:
        raise FastenerLedgerError("known-bad fastener controls are incomplete")
    sequence = ledger.get("assembly_sequence", [])
    if not sequence or any("status" not in stage for stage in sequence):
        raise FastenerLedgerError("assembly sequence must preserve unchecked stages")
    release = ledger.get("release", {})
    if release.get("fabrication_approved") is not False:
        raise FastenerLedgerError("jaw fastener ledger cannot approve fabrication")
    if release.get("powered_operation_approved") is not False:
        raise FastenerLedgerError("jaw fastener ledger cannot approve powered operation")
