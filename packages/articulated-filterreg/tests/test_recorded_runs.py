"""Audit assertions on actual recorded main experiments, not fabricated fixtures."""
from pathlib import Path
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def test_32_main_runs_are_complete_and_best_selection_is_consistent():
    records=[json.loads(p.read_text()) for p in sorted((ROOT/'results/trials').glob('trial_*.json'))]
    assert len(records)==32
    for r in records:
        assert r['status']=='completed' and len(r['trace'])>0
        assert r['final']['scale_depth_units_per_meter']>0
        R=np.array(r['final']['rotation_camera_from_reference'])
        np.testing.assert_allclose(R.T@R,np.eye(3),atol=1e-12)
        assert abs(np.linalg.det(R)-1)<1e-12
        assert np.max(np.abs(np.asarray(r['final']['joint_angles_rad'])))<=np.pi
        for step in r['trace']:
            assert step['frozen_cost_after']<=step['frozen_cost_before']+1e-10
            assert step['gaussian_queries']>=50
    best=json.loads((ROOT/'results/best.json').read_text())
    selected=min(records,key=lambda x:x['final_metrics']['selection_score'])
    assert best['id']==selected['id']
    assert best['final_metrics']['selection_score']<best['initial_metrics']['selection_score']
    metrics=json.loads((ROOT/'results/metrics.json').read_text())
    assert metrics['provisional_acceptance']['passed']
    assert len(metrics['held_out_landmarks'])==14
