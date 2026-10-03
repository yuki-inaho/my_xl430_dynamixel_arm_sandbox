from importlib.metadata import distribution
from pathlib import Path

from arm_observer.cli import build_parser, main


def test_installed_command_targets_renamed_package():
    package = distribution("my-dynamixel-arm-sandbox")
    entry = next(entry for entry in package.entry_points if entry.name == "arm-status")
    assert entry.value == "arm_observer.cli:main"
    assert entry.load() is main


def test_default_config_still_resolves_to_workspace():
    root = Path(__file__).resolve().parents[1]
    args = build_parser().parse_args(["metadata"])
    assert args.config == root / "config/arm.toml"
