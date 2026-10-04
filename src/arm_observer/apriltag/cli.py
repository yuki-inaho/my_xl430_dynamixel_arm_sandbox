"""Command line interface for tag sheet generation, verification and detection."""

import argparse
import hashlib
import json
import sys
from math import isfinite
from pathlib import Path

import cv2
from beartype import beartype
from beartype.roar import BeartypeCallHintViolation

from arm_observer.apriltag.detector import Detection, detect_tags
from arm_observer.apriltag.families import TAG36H11
from arm_observer.apriltag.layout import SheetPlan, SheetSpec, plan_sheets
from arm_observer.apriltag.pdf import sheet_filename, write_sheet_pdf
from arm_observer.apriltag.synthetic import SceneTruth, corner_rms_px, render_sheet_scene

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "tag-sheets"


def _add_sheet_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--tag-size-mm", type=float, default=40.0)
    parser.add_argument("--gap-mm", type=float, default=10.0)
    parser.add_argument("--margin-mm", type=float, default=12.0)
    parser.add_argument("--sheet-count", type=int, default=2)
    parser.add_argument("--first-id", type=int, default=0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and verify actual-size AprilTag 36h11 A4 sheets"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="Write A4 sheet PDFs and a manifest")
    _add_sheet_options(generate)
    generate.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    verify = commands.add_parser("verify", help="Detect a synthetic capture of one sheet")
    _add_sheet_options(verify)
    verify.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    verify.add_argument("--sheet-index", type=int, default=1)
    verify.add_argument("--px-per-mm", type=float, default=6.0)
    verify.add_argument("--blur-sigma", type=float, default=0.8)
    verify.add_argument("--noise-sigma", type=float, default=2.0)
    verify.add_argument("--seed", type=int, default=3)
    verify.add_argument("--rms-limit", type=float, default=0.5)
    verify.add_argument("--flat", action="store_true", help="Disable the default perspective warp")

    detect = commands.add_parser("detect", help="Detect tags in an existing image")
    detect.add_argument("--image", type=Path, required=True)
    detect.add_argument("--output-json", type=Path)
    return parser


def _spec(args: argparse.Namespace) -> SheetSpec:
    return SheetSpec(
        columns=args.columns,
        rows=args.rows,
        tag_size_mm=args.tag_size_mm,
        gap_mm=args.gap_mm,
        margin_mm=args.margin_mm,
        first_tag_id=args.first_id,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@beartype
def _checked_sheets(args: argparse.Namespace) -> tuple[SheetSpec, tuple[SheetPlan, ...]]:
    spec = _spec(args)
    plans = plan_sheets(spec, args.sheet_count, args.first_id)
    highest = max(max(plan.tag_ids) for plan in plans)
    if highest >= len(TAG36H11.codes):
        raise ValueError(
            f"requested tag id {highest} exceeds the pinned {TAG36H11.name} range "
            f"0..{len(TAG36H11.codes) - 1}"
        )
    return spec, plans


def run_generate(args: argparse.Namespace) -> int:
    spec, plans = _checked_sheets(args)
    entries = []
    for plan in plans:
        path = write_sheet_pdf(plan, TAG36H11, args.output_dir / sheet_filename(plan, TAG36H11))
        entries.append(
            {
                "index": plan.sheet_index,
                "ids": list(plan.tag_ids),
                "file": path.name,
                "sha256": _sha256(path),
            }
        )
    manifest = {
        "family": TAG36H11.name,
        "sheet_count": len(plans),
        "columns": spec.columns,
        "rows": spec.rows,
        "tag_size_mm": spec.tag_size_mm,
        "gap_mm": spec.gap_mm,
        "margin_mm": spec.margin_mm,
        "page_mm": {"width": spec.page.width_mm, "height": spec.page.height_mm},
        "sheets": entries,
    }
    manifest_path = args.output_dir / "sheets.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for entry, plan in zip(entries, plans):
        print(f"{entry['file']}: IDs {plan.tag_ids[0]}-{plan.tag_ids[-1]}")
    print(f"Manifest: {manifest_path}")
    return 0


def _score_detections(
    plan: SheetPlan, detections: tuple[Detection, ...], truths: tuple[SceneTruth, ...],
    rms_limit: float,
) -> dict[str, object]:
    truth = {item.tag_id: item.corners_px for item in truths}
    per_id = {
        detection.tag_id: corner_rms_px(detection, truth[detection.tag_id])
        for detection in detections
        if detection.tag_id in truth
    }
    expected = set(plan.tag_ids)
    detected = set(per_id)
    missing = sorted(expected - detected)
    unexpected = sorted({detection.tag_id for detection in detections} - expected)
    max_rms = max(per_id.values(), default=None)
    passed = not missing and not unexpected and max_rms is not None and max_rms <= rms_limit
    return {
        "expected_ids": sorted(expected),
        "detected_ids": sorted(detected),
        "missing_ids": missing,
        "unexpected_ids": unexpected,
        "per_id_rms_px": {str(key): round(value, 4) for key, value in sorted(per_id.items())},
        "max_rms_px": None if max_rms is None else round(max_rms, 4),
        "rms_limit_px": rms_limit,
        "passed": passed,
    }


def run_verify(args: argparse.Namespace) -> int:
    if not isfinite(args.rms_limit) or args.rms_limit <= 0:
        raise ValueError("rms limit must be finite and positive")
    _, plans = _checked_sheets(args)
    if not 1 <= args.sheet_index <= len(plans):
        raise ValueError(f"sheet index must be in 1..{len(plans)}")
    plan = plans[args.sheet_index - 1]
    scene = render_sheet_scene(
        plan, TAG36H11, px_per_mm=args.px_per_mm, perspective=not args.flat,
        blur_sigma=args.blur_sigma, noise_sigma=args.noise_sigma, seed=args.seed,
    )
    detections = detect_tags(scene.image)
    report = _score_detections(plan, detections, scene.truths, args.rms_limit)
    report.update({
        "family": TAG36H11.name,
        "sheet_index": plan.sheet_index,
        "corner_refinement": "CORNER_REFINE_APRILTAG",
        "perspective": not args.flat,
        "blur_sigma": args.blur_sigma,
        "noise_sigma": args.noise_sigma,
        "seed": args.seed,
    })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scene_path = args.output_dir / "synthetic_scene.png"
    if not cv2.imwrite(str(scene_path), scene.image):
        raise OSError(f"cannot write synthetic image: {scene_path}")
    report_path = args.output_dir / "synthetic_verify.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Detected {len(detections)}/{len(plan.tag_ids)} IDs; "
        f"max RMS {report['max_rms_px']} px (limit {args.rms_limit}); passed={report['passed']}"
    )
    print(f"Scene: {scene_path}\nReport: {report_path}")
    return 0 if report['passed'] else 2


def run_detect(args: argparse.Namespace) -> int:
    image = cv2.imread(str(args.image), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"cannot read image: {args.image}")
    detections = detect_tags(image)
    payload = {
        "image": str(args.image),
        "detections": [
            {"tag_id": detection.tag_id, "corners": [list(point) for point in detection.corners]}
            for detection in detections
        ],
    }
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Detected {len(detections)} tag(s): {sorted(d.tag_id for d in detections)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "generate":
            return run_generate(args)
        if args.command == "verify":
            return run_verify(args)
        return run_detect(args)
    except (OSError, ValueError, BeartypeCallHintViolation, cv2.error) as exc:
        print(f"arm-tag-sheet failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
