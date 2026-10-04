"""Post-build regression tests, not independent physical metrology."""
from pathlib import Path
import hashlib
import json

import cadquery as cq
import numpy as np
from PIL import Image
import pytest
import trimesh

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['cot_L', 'cot_R', 'foam_L', 'foam_R', 'band_L', 'band_R']


@pytest.mark.parametrize('name', NAMES)
def test_step_roundtrip(name):
    shape = cq.importers.importStep(str(ROOT / 'models' / f'{name}.step')).val()
    assert shape.isValid()
    assert len(shape.Solids()) == 1
    assert shape.Volume() > 0


@pytest.mark.parametrize('name', NAMES)
def test_stl_closed_positive_volume(name):
    mesh = trimesh.load(ROOT / 'models' / f'{name}.stl', force='mesh')
    assert mesh.is_watertight
    assert mesh.volume > 0
    assert np.isfinite(mesh.vertices).all()


def test_named_glb_nodes_and_units():
    scene = trimesh.load(ROOT / 'models/soft_addons_scanfit.glb', force='scene', process=False)
    assert set(scene.graph.nodes_geometry) == set(NAMES)
    parameters = json.loads((ROOT / 'results/parameters.json').read_text())['components']
    rotation = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
    for name in NAMES:
        transform, key = scene.graph[name]
        mesh = scene.geometry[key].copy()
        mesh.apply_transform(transform)
        cad_vertices = mesh.vertices @ rotation * 1000
        reference = parameters[name]['export_bbox_mm']
        # Analytic B-rep bounds and tessellated bounds are not exactly identical.
        assert np.max(np.abs(cad_vertices.min(0) - reference['min'])) < 0.2
        assert np.max(np.abs(cad_vertices.max(0) - reference['max'])) < 0.2


def test_step_assembly_component_counts():
    counts = {'soft_addons_scanfit.step': 6,
              'soft_addons_L.step': 3, 'soft_addons_R.step': 3,
              'soft_addons_with_reference_frame.step': 9}
    for filename, count in counts.items():
        shape = cq.importers.importStep(str(ROOT / 'models' / filename)).val()
        assert shape.isValid()
        assert len(shape.Solids()) == count


def test_photo_overlay_resolution():
    photo = Image.open(ROOT / 'inputs/photo.jpg')
    for name in ['photo_overlay.png', 'photo_overlay_labeled.png', 'photo_model_labels.png']:
        assert Image.open(ROOT / 'results' / name).size == photo.size
    label = np.asarray(Image.open(ROOT / 'results/photo_model_labels.png'))
    assert set(np.unique(label)) == set(range(7))


def test_metric_rotation_is_right_handed():
    calibration = json.loads((ROOT / 'results/calibration.json').read_text())
    rotation = np.asarray(calibration['R_source_to_cad'])
    assert calibration['scale_mm_per_source_unit'] > 0
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-10)
    assert abs(np.linalg.det(rotation) - 1) < 1e-10


def test_input_hash_manifest():
    manifest = json.loads((ROOT / 'results/input_manifest.json').read_text())
    assert manifest['scan_vertices'] == 83525
    assert manifest['scan_faces'] == 147506
    for relative_path, expected in manifest['sha256'].items():
        assert hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest() == expected


def test_scan_comparison_keeps_texture():
    scene = trimesh.load(ROOT / 'models/scan_with_fitted_addons.glb', force='scene', process=False)
    assert set(scene.graph.nodes_geometry) == set(NAMES + ['scan_reference'])
    _, key = scene.graph['scan_reference']
    assert scene.geometry[key].visual.kind == 'texture'


def test_numeric_validation_report():
    result = json.loads((ROOT / 'results/validation.json').read_text())
    assert result['pass']
    assert result['all_step_valid'] and result['all_addon_meshes_watertight']
    assert result['glb_roundtrip_bounds_max_error_mm'] < 0.01
    assert result['max_mesh_vs_step_volume_relative_error'] < 0.025
