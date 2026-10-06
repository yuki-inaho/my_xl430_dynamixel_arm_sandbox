"""Read-only phase-resolved force/height diagnosis of preserved release failures."""

import json

import numpy as np

from build_scene import ROOT, save_json


def main():
    reports = []
    for name in ("development-002-t002", "development-002-t004"):
        path = ROOT / "results/development-002" / name
        with np.load(path / "states.npz") as z:
            s = {k: z[k] for k in z.files}
        n = len(s["time"])
        box = np.zeros(n)
        with (path / "contacts.jsonl").open() as handle:
            for i, line in enumerate(handle):
                row = json.loads(line)
                box[i] = sum(
                    max(0, c["force"][0])
                    for c in row["contacts"]
                    if {c["geom1"], c["geom2"]} == {"cap_geom", "box"}
                )
        az = np.clip(np.abs(s["cap_axis"][:, 2]), 0, 1)
        bottom = s["cap_position"][:, 2] - 0.0075 * az - 0.014 * np.sqrt(1 - az * az)
        phases = []
        for phase in ("hold", "lower", "release", "retract"):
            ids = np.where(s["phase"] == phase)[0]
            if len(ids):
                phases.append(
                    {
                        "phase": phase,
                        "bottom_min_m": float(bottom[ids].min()),
                        "cap_speed_max_m_s": float(
                            np.max(
                                np.linalg.norm(
                                    np.diff(s["cap_position"][ids], axis=0) / 0.001, axis=1
                                )
                            )
                        )
                        if len(ids) > 1
                        else None,
                        "box_force_max_N": float(box[ids].max()),
                        "finger_force_max_N": float(
                            np.maximum(s["left_force"][ids], s["right_force"][ids]).max()
                        ),
                    }
                )
        report = {
            "trial": name,
            "phases": phases,
            "result": json.loads((path / "result.json").read_text())["reason_codes"],
        }
        reports.append(report)
    save_json(ROOT / "evidence/setdown-preload-diagnosis.json", reports)
    print(json.dumps(reports, indent=2), flush=True)
