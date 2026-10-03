"""Summarize joint-space safety from replay_poses.py JSON output.

This script is intentionally model-agnostic: it only assumes the replay JSON has
`poses[*].target`, `ok`, `reachable`, `no_self_collision`, `self_pair`, and
`self_interference_mm` fields. It can therefore be reused for other robots or
other collision models that emit the same shape.

Example:
    uv run python scripts/jointspace_safety_report.py \
      --input temp/replay_xl430_oriented.json \
      --joint-names joint1,joint2,joint3,joint4,joint5 \
      --focus-joints joint2,joint3,joint4 \
      --output-md temp/jointspace_safety_report.md \
      --output-json temp/jointspace_safety_report.json
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path
from typing import Any


def _round(v: float, digits: int) -> float:
    return round(float(v), digits)


def _pair_key(pair: Any) -> str:
    if not pair:
        return "(none)"
    return " <-> ".join(str(x) for x in pair)


def _reason(pose: dict) -> str:
    if pose.get("ok"):
        return "ok"
    if not pose.get("finite", True):
        return "nonfinite"
    reachable = bool(pose.get("reachable"))
    no_self = bool(pose.get("no_self_collision"))
    if not reachable and not no_self:
        return "tracking_and_self_collision"
    if not reachable:
        return "tracking"
    if not no_self:
        return "self_collision"
    return "unknown_not_ok"


def _parse_joint_names(value: str | None, n: int) -> list[str]:
    if value:
        names = [x.strip() for x in value.split(",") if x.strip()]
        if len(names) != n:
            raise SystemExit(f"--joint-names expected {n} names, got {len(names)}")
        return names
    return [f"joint{i + 1}" for i in range(n)]


def _parse_joint_indexes(value: str | None, names: list[str]) -> list[int]:
    if not value:
        return list(range(min(3, len(names))))
    out: list[int] = []
    lookup = {name: i for i, name in enumerate(names)}
    for raw in value.split(","):
        token = raw.strip()
        if not token:
            continue
        if token in lookup:
            out.append(lookup[token])
            continue
        try:
            idx = int(token) - 1
        except ValueError as exc:
            raise SystemExit(f"unknown joint in --focus-joints: {token}") from exc
        if idx < 0 or idx >= len(names):
            raise SystemExit(f"joint index out of range in --focus-joints: {token}")
        out.append(idx)
    if not out:
        raise SystemExit("--focus-joints produced no joints")
    return out


def _level_stats(poses: list[dict], joint_index: int, precision: int) -> list[dict]:
    buckets: dict[float, list[dict]] = collections.defaultdict(list)
    for p in poses:
        buckets[_round(p["target"][joint_index], precision)].append(p)
    rows = []
    for level in sorted(buckets):
        items = buckets[level]
        lost = sum(not p.get("ok", False) for p in items)
        rows.append({
            "level": level,
            "total": len(items),
            "ok": len(items) - lost,
            "lost": lost,
            "lost_rate": lost / len(items) if items else 0.0,
        })
    return rows


def _group_stats(poses: list[dict], indexes: list[int], precision: int) -> list[dict]:
    buckets: dict[tuple[float, ...], list[dict]] = collections.defaultdict(list)
    for p in poses:
        key = tuple(_round(p["target"][i], precision) for i in indexes)
        buckets[key].append(p)
    rows = []
    for key in sorted(buckets):
        items = buckets[key]
        lost = sum(not p.get("ok", False) for p in items)
        worst_self = max((float(p.get("self_interference_mm") or 0.0) for p in items),
                         default=0.0)
        pairs = collections.Counter(_pair_key(p.get("self_pair")) for p in items
                                    if not p.get("ok", False))
        rows.append({
            "levels": list(key),
            "total": len(items),
            "ok": len(items) - lost,
            "lost": lost,
            "lost_rate": lost / len(items) if items else 0.0,
            "worst_self_interference_mm": round(worst_self, 3),
            "dominant_lost_pair": pairs.most_common(1)[0][0] if pairs else None,
        })
    return rows


def _matrix(poses: list[dict], a: int, b: int, precision: int) -> dict:
    a_levels = sorted({_round(p["target"][a], precision) for p in poses})
    b_levels = sorted({_round(p["target"][b], precision) for p in poses})
    cells = []
    for av in a_levels:
        row = []
        for bv in b_levels:
            items = [p for p in poses
                     if _round(p["target"][a], precision) == av
                     and _round(p["target"][b], precision) == bv]
            lost = sum(not p.get("ok", False) for p in items)
            row.append({"total": len(items), "lost": lost, "ok": len(items) - lost})
        cells.append(row)
    return {"a_levels": a_levels, "b_levels": b_levels, "cells": cells}


def analyze(doc: dict, joint_names: list[str] | None = None,
            focus_indexes: list[int] | None = None, precision: int = 4,
            mostly_threshold: float = 0.75) -> dict:
    poses = list(doc.get("poses") or [])
    if not poses:
        raise ValueError("input JSON has no poses; run replay_poses.py with --json first")
    n_joints = len(poses[0]["target"])
    names = joint_names or [f"joint{i + 1}" for i in range(n_joints)]
    focus = focus_indexes or list(range(min(3, n_joints)))
    total = len(poses)
    ok = sum(bool(p.get("ok")) for p in poses)
    lost = total - ok
    reasons = collections.Counter(_reason(p) for p in poses)
    lost_pairs = collections.Counter(_pair_key(p.get("self_pair")) for p in poses
                                     if not p.get("ok", False))
    per_joint = {
        names[i]: _level_stats(poses, i, precision)
        for i in range(n_joints)
    }
    focus_groups = _group_stats(poses, focus, precision)
    focus_groups_by_risk = sorted(
        focus_groups,
        key=lambda r: (-r["lost_rate"], -r["lost"], r["levels"]),
    )
    matrices = {}
    for a, b in itertools.combinations(focus, 2):
        matrices[f"{names[a]}__{names[b]}"] = _matrix(poses, a, b, precision)
    high_risk_levels = []
    zero_loss_levels = []
    for name, rows in per_joint.items():
        for row in rows:
            item = {"joint": name, **row}
            if row["lost_rate"] >= mostly_threshold and row["lost"]:
                high_risk_levels.append(item)
            if row["lost"] == 0:
                zero_loss_levels.append(item)
    return {
        "source_model": doc.get("model"),
        "thresholds": doc.get("thresholds", {}),
        "joint_names": names,
        "focus_joints": [names[i] for i in focus],
        "summary": {
            "total": total,
            "ok": ok,
            "lost": lost,
            "lost_rate": lost / total if total else 0.0,
            "worst_self_interference_mm": doc.get("worst_self_interference_mm"),
            "worst_track_err_rad": doc.get("worst_track_err_rad"),
        },
        "reason_counts": dict(reasons),
        "lost_pair_counts": dict(lost_pairs),
        "per_joint": per_joint,
        "focus_groups_by_risk": focus_groups_by_risk,
        "focus_groups_all_lost": [r for r in focus_groups_by_risk
                                  if r["lost"] == r["total"] and r["total"]],
        "focus_groups_all_safe": [r for r in focus_groups
                                  if r["lost"] == 0 and r["total"]],
        "high_risk_single_joint_levels": high_risk_levels,
        "zero_loss_single_joint_levels": zero_loss_levels,
        "matrices": matrices,
    }


def _pct(v: float) -> str:
    return f"{100.0 * v:.1f}%"


def _md_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join(":---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return out


def render_markdown(report: dict, top: int = 20) -> str:
    s = report["summary"]
    lines = [
        "# Joint-Space Safety Report",
        "",
        "## Protocol",
        "",
        "- Pose identity: `q = [joint1, joint2, ...]` in radians, in actuator order.",
        "- Safe pose: replay result has `ok=true`, meaning reachable and no "
        "non-adjacent self-collision beyond the configured penetration threshold.",
        "- Unsafe/lost pose: replay result has `ok=false`; reason and collision pair "
        "are summarized from the replay JSON.",
        "- This report is generated from replay output only; it is independent of a "
        "specific CAD or robot implementation as long as the JSON schema is compatible.",
        "",
        "## Summary",
        "",
    ]
    lines += _md_table(
        ["model", "poses", "ok", "lost", "lost rate", "worst self mm", "worst track rad"],
        [[
            report.get("source_model"),
            s["total"],
            s["ok"],
            s["lost"],
            _pct(s["lost_rate"]),
            s.get("worst_self_interference_mm"),
            s.get("worst_track_err_rad"),
        ]],
    )
    lines += ["", "## Outcome Reasons", ""]
    lines += _md_table(["outcome", "count"],
                       [[k, v] for k, v in sorted(report["reason_counts"].items())])
    lines += ["", "## Lost Collision Pairs", ""]
    lines += _md_table(["pair", "count"],
                       [[k, v] for k, v in sorted(
                           report["lost_pair_counts"].items(),
                           key=lambda kv: (-kv[1], kv[0]))])
    lines += ["", "## Per-Joint Level Risk", ""]
    for joint, rows in report["per_joint"].items():
        lines += [f"### {joint}", ""]
        lines += _md_table(
            ["level rad", "total", "ok", "lost", "lost rate"],
            [[r["level"], r["total"], r["ok"], r["lost"], _pct(r["lost_rate"])]
             for r in rows],
        )
        lines.append("")
    focus = ", ".join(report["focus_joints"])
    lines += [f"## Focus Joint Tuples By Risk ({focus})", ""]
    top_rows = report["focus_groups_by_risk"][:top]
    lines += _md_table(
        ["levels rad", "total", "ok", "lost", "lost rate", "worst self mm", "dominant pair"],
        [[r["levels"], r["total"], r["ok"], r["lost"], _pct(r["lost_rate"]),
          r["worst_self_interference_mm"], r["dominant_lost_pair"]]
         for r in top_rows],
    )
    lines += ["", "## All-Lost Focus Tuples", ""]
    all_lost = report["focus_groups_all_lost"][:top]
    lines += _md_table(
        ["levels rad", "total", "lost", "dominant pair"],
        [[r["levels"], r["total"], r["lost"], r["dominant_lost_pair"]]
         for r in all_lost],
    )
    lines += ["", "## All-Safe Focus Tuples", ""]
    all_safe = sorted(report["focus_groups_all_safe"], key=lambda r: r["levels"])[:top]
    lines += _md_table(
        ["levels rad", "total", "ok"],
        [[r["levels"], r["total"], r["ok"]] for r in all_safe],
    )
    lines += ["", "## Pairwise Lost/Total Matrices", ""]
    for key, mat in report["matrices"].items():
        a_name, b_name = key.split("__")
        lines += [f"### {a_name} x {b_name}", ""]
        headers = [f"{a_name} \\ {b_name}"] + [str(v) for v in mat["b_levels"]]
        rows = []
        for av, cells in zip(mat["a_levels"], mat["cells"]):
            rows.append([av] + [f"{c['lost']}/{c['total']}" for c in cells])
        lines += _md_table(headers, rows)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True,
                    help="JSON output from scripts/replay_poses.py --json")
    ap.add_argument("--joint-names",
                    help="comma-separated joint names; defaults to joint1,...")
    ap.add_argument("--focus-joints", default="2,3,4",
                    help="comma-separated 1-based indexes or joint names for tuple/matrix analysis")
    ap.add_argument("--precision", type=int, default=4)
    ap.add_argument("--mostly-threshold", type=float, default=0.75)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--output-md", type=Path)
    ap.add_argument("--output-json", type=Path)
    args = ap.parse_args(argv)

    doc = json.loads(args.input.read_text())
    poses = doc.get("poses") or []
    if not poses:
        raise SystemExit(f"{args.input}: no poses found")
    names = _parse_joint_names(args.joint_names, len(poses[0]["target"]))
    focus = _parse_joint_indexes(args.focus_joints, names)
    report = analyze(doc, names, focus, args.precision, args.mostly_threshold)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(report, args.top))
    if not args.output_json and not args.output_md:
        print(render_markdown(report, args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
