"""Generic report writers (CSV + Markdown). Title and intro lines are injected."""
from __future__ import annotations
import csv
import json
from pathlib import Path


def write_all(analysis: dict, out_dir: Path, title: str,
              intro_lines: list[str]) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_step_csv(analysis["steps"], out_dir / "step_impact.csv")
    _write_stl_csv(analysis["stls"], out_dir / "stl_stats.csv")
    (out_dir / "brep.json").write_text(
        json.dumps(analysis["brep"], indent=2, ensure_ascii=False))
    md = _markdown(analysis, title, intro_lines)
    (out_dir / "IMPACT_REPORT.md").write_text(md)
    return {"out": str(out_dir),
            "files": ["step_impact.csv", "stl_stats.csv", "brep.json",
                      "IMPACT_REPORT.md"]}


def _flat(row: dict) -> dict:
    r = {k: v for k, v in row.items() if k != "keywords"}
    for k, v in row.get("keywords", {}).items():
        r[f"kw_{k}"] = v
    return r


def _write_step_csv(rows: list[dict], path: Path):
    if not rows:
        return
    flat = [_flat(r) for r in rows]
    keys = sorted({k for r in flat for k in r})
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(flat)


def _write_stl_csv(rows: list[dict], path: Path):
    if not rows:
        return
    cols = ["rel", "name", "bbox_mm", "volume_mm3", "area_mm2",
            "triangles", "watertight"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _markdown(analysis: dict, title: str, intro_lines: list[str]) -> str:
    order = {t: i for i, t in enumerate(analysis["tier_order"])}
    steps = sorted(analysis["steps"], key=lambda r: order.get(r["impact"], 99))
    L = [f"# {title}\n"]
    L += [l if l.endswith("\n") else l + "\n" for l in intro_lines]
    L.append("\n## Per-part impact (STEP)\n")
    L.append("| path | impact | bbox mm | cyl faces | target fits | PRODUCT |")
    L.append("|---|---|---|---|---|---|")
    for r in steps:
        def cell(v):
            return "-" if v is None else v
        L.append(f"| {r.get('rel', r['name'])} | **{r['impact']}** "
                 f"| {cell(r.get('bbox_mm'))} | {cell(r.get('cyl_faces'))} "
                 f"| {cell(r.get('target_fits'))} "
                 f"| {str(r.get('products', ''))[:42]} |")
    L.append("\n## STL envelopes\n")
    L.append("| part | bbox mm | target fits | margins mm |")
    L.append("|---|---|---|---|")
    for r in sorted(analysis["stls"], key=lambda x: x["name"]):
        fit = r.get("fit") or {}
        L.append(f"| {r['name']} | {r['bbox_mm']} | {fit.get('fits','-')} "
                 f"| {fit.get('margins_mm','-')} |")
    return "\n".join(L) + "\n"
