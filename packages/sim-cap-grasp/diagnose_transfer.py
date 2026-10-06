"""Diagnostics beyond unchanged acceptance: full hold and transfer grip loss."""

import json

import numpy as np

from build_scene import ROOT, save_json
from trace_io import contact_rows


def main():
    reports = []
    for name in sorted(
        p.name
        for p in (ROOT / "results").iterdir()
        if p.is_dir()
        and p.name.startswith(("adaptive-", "jaw93-", "jaw95-"))
        and (p / "result.json").exists()
    ):
        path = ROOT / "results" / name
        with np.load(path / "states.npz") as z:
            s = {k: z[k] for k in z.files}
        t = s["time"]
        rel = np.einsum("nji,nj->ni", s["grip_rotation"], s["cap_position"] - s["grip_position"])
        speed = np.r_[
            0.0, np.linalg.norm(np.diff(s["cap_position"], axis=0) / np.diff(t)[:, None], axis=1)
        ]
        box = np.zeros(len(t))
        for i, row in enumerate(contact_rows(path)):
            box[i] = sum(
                max(0.0, c["force"][0])
                for c in row["contacts"]
                if {c["geom1"], c["geom2"]} == {"cap_geom", "box"}
            )
        hold = np.where(s["phase"] == "hold")[0]
        lower = np.where(s["phase"] == "lower")[0]
        bilateral = (s["left_force"] > 1e-5) & (s["right_force"] > 1e-5)
        both_lost = (s["left_force"] <= 1e-5) & (s["right_force"] <= 1e-5)
        contact = np.where((np.arange(len(t)) >= lower[0]) & (box > 1e-5))[0]
        first = int(contact[0]) if len(contact) else None
        lost = lower[both_lost[lower]]
        unilateral = lower[~bilateral[lower]]
        report = {
            "trial": name,
            "full_hold_duration_s": float(t[hold[-1]] - t[hold[0]]),
            "full_hold_bilateral_fraction": float(bilateral[hold[:-1]].mean()),
            "full_hold_grip_drift_max_m": float(
                np.linalg.norm(rel[hold] - rel[hold[0]], axis=1).max()
            ),
            "lower_first_bilateral_loss_s": float(t[unilateral[0]]) if len(unilateral) else None,
            "lower_first_both_contacts_lost_s": float(t[lost[0]]) if len(lost) else None,
            "lower_grip_relative_displacement_max_m": float(
                np.linalg.norm(rel[lower] - rel[lower[0]], axis=1).max()
            ),
            "first_box_contact_s": float(t[first]) if first is not None else None,
            "cap_speed_before_box_contact_m_s": float(speed[max(0, first - 1)])
            if first is not None
            else None,
            "lower_release_box_force_max_N": float(
                box[np.isin(s["phase"], ["lower", "release"])].max()
            ),
            "placement_latch": json.loads((path / "metadata.json").read_text()).get(
                "placement_latch"
            ),
            "scope": "Additional diagnostic, not a changed success criterion or hardware measurement",
        }
        reports.append(report)
    save_json(ROOT / "evidence/transfer-loss-diagnostics.json", reports)
    print(json.dumps(reports, indent=2), flush=True)
