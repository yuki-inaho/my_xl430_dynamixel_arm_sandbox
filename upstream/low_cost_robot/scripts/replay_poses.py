"""Pose-replay regression harness: prove the arm's DEGREES OF FREEDOM do not break.

Answers the core user requirement (DoD C-C3 / C-C4): a set of representative poses
that the CURRENT (XL330) arm can reach WITHOUT self-collision must still be reachable
WITHOUT self-collision on the XL430 model — i.e. enlarging the servos must not lose
workspace or break the kinematics.

For each pose it commands the position actuators to the target, settles, then measures
  - tracking error   : |reached qpos - target| per actuator (<= TRACKING_TOL rad)
  - self-interference: worst non-adjacent arm-on-arm contact depth (<= PENETRATION_LIMIT)
and reports {reachable, self_interference_mm, max_track_err_rad, ok} per pose.

DRY: the contact / interference / adjacency classification is REUSED from
scripts/check_simulation.py (no duplicate physics logic). The same thresholds apply.

    # 1) build the reference set on the baseline (XL330) model:
    uv run --group sim python scripts/replay_poses.py --model simulation/low_cost_robot/scene.xml \\
        --emit-grid --save-reachable temp/replay_baseline.json
    # 2) regress that reference set on the XL430-proxy model:
    uv run --group sim python scripts/replay_poses.py --model temp/sim_xl430proxy/scene_xl430proxy.xml \\
        --poses temp/replay_baseline.json --json > temp/replay_xl430.json
"""
from __future__ import annotations
import sys
import json
import argparse
import itertools
from pathlib import Path

import numpy as np
import mujoco

# DRY: reuse the validated physics helpers + thresholds from the checker.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_simulation import (_interference, PENETRATION_LIMIT_MM,  # noqa: E402
                              TRACKING_TOL)


def _native(o):
    """JSON default hook: numpy scalars (e.g. np.bool_ from `x <= LIMIT`) -> native."""
    return o.item() if hasattr(o, "item") else str(o)


def grid_poses(model, fractions=(-0.5, 0.0, 0.5),
               extra: list[list[float]] | None = None) -> list[list[float]]:
    """Representative poses: each actuator set to {-50%, 0, +50%} of its ctrl range
    (full-end self-collisions are a known workspace property and are avoided), plus
    any explicit working poses. Cartesian product over the nu actuators."""
    lo = model.actuator_ctrlrange[:, 0]
    hi = model.actuator_ctrlrange[:, 1]
    mid = (hi + lo) / 2.0
    half = (hi - lo) / 2.0
    levels = [[float(mid[j] + f * half[j]) for f in fractions] for j in range(model.nu)]
    poses = [list(p) for p in itertools.product(*levels)]
    if extra:
        poses.extend([list(p) for p in extra])
    return poses


def _parse_fractions(value: str) -> tuple[float, ...]:
    try:
        out = tuple(float(x.strip()) for x in value.split(",") if x.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected comma-separated floats, got {value!r}") from exc
    if not out:
        raise argparse.ArgumentTypeError("at least one fraction is required")
    if any(x < -1.0 or x > 1.0 for x in out):
        raise argparse.ArgumentTypeError("fractions must lie within [-1.0, 1.0]")
    return out


def replay_pose(model, data, target: list[float], settle_s: float = 2.0) -> dict:
    """Command `target`, settle, measure tracking error + non-adjacent self-interference."""
    mujoco.mj_resetData(model, data)
    tgt = np.asarray(target, float)
    data.ctrl[:] = tgt
    for _ in range(int(settle_s / model.opt.timestep)):
        mujoco.mj_step(model, data)
    finite = bool(np.all(np.isfinite(data.qpos)) and np.all(np.isfinite(data.qvel)))
    errs = []
    for i in range(model.nu):
        jid = int(model.actuator_trnid[i, 0])
        qadr = int(model.jnt_qposadr[jid])
        errs.append(abs(float(data.qpos[qadr]) - float(tgt[i])))
    max_err = max(errs) if errs else 0.0
    intf = _interference(model, data)
    reachable = finite and max_err <= TRACKING_TOL
    no_self = intf["self_mm"] <= PENETRATION_LIMIT_MM
    return {
        "target": [round(x, 4) for x in target],
        "finite": finite,
        "max_track_err_rad": round(max_err, 4),
        "reachable": reachable,                       # tracked the command (DOF works)
        "self_interference_mm": intf["self_mm"],
        "self_pair": intf["self_pair"],
        "no_self_collision": no_self,
        "ok": reachable and no_self,                  # reached AND collision-free
    }


def _load_targets(args, model) -> list[list[float]]:
    """Poses come from --poses (a JSON file of targets or a prior reachable-set dump)
    and/or --emit-grid. No implicit fallback: at least one source must be given."""
    targets: list[list[float]] = []
    if args.poses:
        doc = json.loads(Path(args.poses).read_text())
        if isinstance(doc, dict) and "targets" in doc:        # reachable-set dump
            targets.extend([list(t) for t in doc["targets"]])
        elif isinstance(doc, list):                           # raw list of poses
            targets.extend([list(t) for t in doc])
        else:
            raise SystemExit(f"--poses {args.poses}: expected a list or {{'targets':[...]}}")
    if args.emit_grid:
        targets.extend(grid_poses(model, fractions=args.fractions))
    if not targets:
        raise SystemExit("no poses: pass --poses FILE and/or --emit-grid (no fallback)")
    return targets


def run(model_path: Path, targets: list[list[float]], settle_s: float = 2.0) -> dict:
    model = mujoco.MjModel.from_xml_path(str(model_path.resolve()))
    data = mujoco.MjData(model)
    results = [replay_pose(model, data, t, settle_s) for t in targets]
    reachable_ok = [r for r in results if r["ok"]]
    worst = max((r["self_interference_mm"] for r in results), default=0.0)
    worst_track = max((r["max_track_err_rad"] for r in results), default=0.0)
    return {
        "model": str(model_path),
        "n_poses": len(results),
        "n_ok": len(reachable_ok),                    # reached AND collision-free
        "worst_self_interference_mm": round(worst, 3),
        "worst_track_err_rad": round(worst_track, 4),
        "thresholds": {"penetration_mm": PENETRATION_LIMIT_MM, "tracking_rad": TRACKING_TOL},
        "poses": results,
        "targets_ok": [r["target"] for r in reachable_ok],   # the reference set
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path,
                    default=Path("simulation/low_cost_robot/scene.xml"))
    ap.add_argument("--poses", type=Path, help="JSON list of targets or a reachable-set dump")
    ap.add_argument("--emit-grid", action="store_true",
                    help="add the {-50%%,0,+50%%} actuator grid to the poses")
    ap.add_argument("--fractions", type=_parse_fractions,
                    default=(-0.5, 0.0, 0.5),
                    help=("comma-separated actuator-range fractions for --emit-grid; "
                          "use --fractions=-0.6,-0.3,0,0.3,0.6 for a 5-level grid"))
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("--save-reachable", type=Path,
                    help="write {'targets':[...]} of the OK poses (the reference set)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    model = mujoco.MjModel.from_xml_path(str(a.model.resolve()))
    targets = _load_targets(a, model)
    out = run(a.model, targets, a.settle)

    if a.save_reachable:
        a.save_reachable.parent.mkdir(parents=True, exist_ok=True)
        a.save_reachable.write_text(json.dumps(
            {"model": str(a.model), "targets": out["targets_ok"]},
            indent=2, default=_native))

    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=_native))
    else:
        print(f"Model: {a.model}")
        print(f"  poses={out['n_poses']} ok(reached & collision-free)={out['n_ok']}")
        print(f"  worst self-interference={out['worst_self_interference_mm']}mm "
              f"(limit {PENETRATION_LIMIT_MM})")
        print(f"  worst tracking error={out['worst_track_err_rad']}rad "
              f"(tol {TRACKING_TOL})")
    return 0 if out["n_ok"] == out["n_poses"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
