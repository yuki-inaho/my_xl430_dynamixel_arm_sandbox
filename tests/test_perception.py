"""Independent numerical checks for the optional perception pipeline."""

import numpy as np
import pytest

from arm_observer.perception.filterreg import GaussianCUDA
from arm_observer.perception.renderer import CadRenderer


def test_cuda_gaussian_matches_native_direct():
    torch = pytest.importorskip('torch')
    if not torch.cuda.is_available():
        pytest.skip('CUDA is required for this explicit GPU check')
    from articulated_filterreg.native import GaussianMoments

    rng = np.random.default_rng(12)
    target = rng.normal(0, .03, (113, 3)) + [0.1, 0.2, 0.9]
    points = rng.normal(0, .03, (37, 3)) + [0.1, 0.2, 0.9]
    with GaussianCUDA(target, .02) as gpu, GaussianMoments(target, .02, 'direct') as native:
        np.testing.assert_allclose(gpu.evaluate(points), native.evaluate(points),
                                   rtol=3e-5, atol=2e-6)


def test_rgbd_metric_units_pixel_centers_and_unsupported_distortion():
    from arm_observer.perception.source import prepare_frame

    rgb = np.zeros((48, 64, 3), np.uint8)
    counts = np.full((48, 64), 1000, np.uint16)
    intrinsics = dict(fx=100., fy=100., ppx=31.5, ppy=23.5,
                      coeffs=[0.]*5, model='distortion.inverse_brown_conrady')
    frame = prepare_frame(rgb, counts, intrinsics, .001, 7, {}, width=32)
    np.testing.assert_allclose(frame.depth_m, 1.)
    np.testing.assert_allclose(frame.K, [[50, 0, 15.5], [0, 50, 11.5], [0, 0, 1]])
    assert frame.rgb.shape[:2] == frame.depth_m.shape == (24, 32)
    with pytest.raises(ValueError, match='distortion not supported'):
        prepare_frame(rgb, counts, dict(intrinsics, coeffs=[.1, 0, 0, 0, 0]),
                      .001, 7, {}, width=32)


def test_gpu_rasterization_matches_camera_projection():
    pytest.importorskip('moderngl')
    from articulated_filterreg.geometry import CadModel, KinematicChain, State, projection

    vertices = np.array([[-.1, -.1, 0], [.1, -.1, 0], [0, .1, 0]])
    model = CadModel(vertices, np.array([[0, 1, 2]]), np.zeros(3, dtype=np.int32),
                     np.zeros(1, dtype=np.int32), np.ones(1), np.zeros(1), ['triangle'],
                     KinematicChain(np.empty((0, 3)), np.empty((0, 3))))
    state = State(np.eye(3), np.array([0., 0., 1.]), 0., np.empty(0))
    K = np.array([[100., 0., 50.], [0., 100., 40.], [0., 0., 1.]])
    with CadRenderer(model, 100, 80) as renderer:
        rendered = renderer.render(state, K)
        assert renderer.render(State.from_dict(state.to_dict()), K.copy()) is rendered
        shifted_k = K.copy()
        shifted_k[0, 2] += 20
        shifted = renderer.render(state, shifted_k)
        np.testing.assert_allclose(np.nonzero(shifted.mask)[1].mean(),
                                   np.nonzero(rendered.mask)[1].mean()+20, atol=1)
        moved = State(state.rotation, state.translation+[.1, 0, 0], 0., np.empty(0))
        assert not np.array_equal(renderer.render(moved, K).mask, rendered.mask)
    y, x = np.nonzero(rendered.mask)
    projected = projection(rendered.xyz[y, x], K)
    np.testing.assert_allclose(projected, np.column_stack((x, y)), atol=2e-5)
    np.testing.assert_allclose(rendered.xyz[y, x, 2], 1., atol=1e-6)
    assert rendered.mask[40, 50]
    assert not rendered.mask[5, 5]


def test_metric_joint_recovery_and_missing_depth_is_lost(monkeypatch):
    torch = pytest.importorskip('torch')
    pytest.importorskip('moderngl')
    if not torch.cuda.is_available():
        pytest.skip('explicit CUDA recovery needs the GPU extra')
    import time

    import trimesh
    from articulated_filterreg.geometry import CadModel, KinematicChain, State
    from scipy.spatial.transform import Rotation

    from arm_observer.perception.source import Frame
    from arm_observer.perception.tracker import (
        PoseTracker,
        RegistrationConfig,
        register,
        sample_points,
    )

    base = trimesh.creation.box([.06, .06, .035])
    link = trimesh.creation.box([.045, .025, .14])
    link.apply_translation([0, 0, .09])
    vertices = np.concatenate((base.vertices, link.vertices))
    faces = np.concatenate((base.faces, link.faces+len(base.vertices)))
    levels = np.r_[np.zeros(len(base.vertices)), np.ones(len(link.vertices))].astype(np.int32)
    face_levels = np.r_[np.zeros(len(base.faces)), np.ones(len(link.faces))].astype(np.int32)
    chain = KinematicChain(np.array([[0., 0., .02]]), np.array([[0., 1., 0.]]))
    model = CadModel(vertices, faces, levels, face_levels, face_levels, face_levels,
                     ['base', 'link'], chain)
    truth = State(Rotation.from_euler('x', 140, degrees=True).as_matrix(),
                  np.array([0., .01, .6]), 0., np.array([.30]))
    initial = State(truth.rotation, truth.translation, 0., np.array([.15]))
    K = np.array([[350., 0., 160.], [0., 350., 120.], [0., 0., 1.]])
    config = RegistrationConfig(backend='cuda', point_limit=1000)
    with CadRenderer(model, 320, 240) as renderer:
        observed = renderer.render(truth, K)
        frame = Frame(observed.rgb, observed.xyz[:, :, 2], K, 1, time.monotonic(), {})
        target = sample_points(frame, observed.mask, 1000)
        fitted = register(model, renderer, frame, observed.mask, target, initial, config,
                          sigmas=(.015, .008, .004), iterations=12, fixed_root=True)
        assert abs(fitted.joints[0]-truth.joints[0]) < .035
        assert fitted.scale == 1.
        tracker = PoseTracker(model, renderer, config)
        tracker.state = fitted
        fresh = Frame(frame.rgb, frame.depth_m, K, 2, time.monotonic(), {})
        assert tracker.update(fresh, observed.mask).status == 'tracking'
        empty = tracker.update(fresh, np.zeros_like(observed.mask), acquire=False)
        assert empty.status == 'lost' and empty.state is None
        for sequence in range(3, 6):
            missing = Frame(frame.rgb, np.zeros_like(frame.depth_m), K, sequence,
                            time.monotonic(), {})
            result = tracker.update(missing, observed.mask, acquire=False)
            assert result.status == 'lost'
            assert result.state is None
        assert tracker.state is None
        # A foreground mask can remain on a background object after the arm
        # disappears. It must not authorize moving the root to that object.
        def forbidden_initialization(*args):
            pytest.fail('anchored tracker attempted a global root search')
        monkeypatch.setattr('arm_observer.perception.tracker.initialize',
                            forbidden_initialization)
        background = Frame(frame.rgb, np.where(frame.depth_m > 0, frame.depth_m+.08, 0),
                           K, 6, time.monotonic(), {})
        for _ in range(4):
            absent = tracker.update(background, observed.mask)
            assert absent.status == 'lost' and absent.state is None
            assert 'fixed base absent' in absent.reason
        assert tracker.seed is not None
        restored = Frame(frame.rgb, frame.depth_m, K, 7, time.monotonic(), {})
        recovered = tracker.update(restored, observed.mask)
        assert recovered.status == 'tracking'
        assert recovered.state is not None
        assert abs(recovered.state.joints[0]-truth.joints[0]) < .035


def test_viewer_counts_only_fresh_poses_and_expires_old_masks(monkeypatch, tmp_path):
    from articulated_filterreg.geometry import State

    from arm_observer.perception.server import LiveSession
    from arm_observer.perception.source import Frame
    from arm_observer.perception.tracker import Estimate

    model_path = tmp_path/'model.npz'
    model_path.write_bytes(b'no geometry needed to verify publication timing')
    session = LiveSession(None, model_path, tmp_path)
    rgb = np.zeros((8, 8, 3), np.uint8)
    mask = np.ones((8, 8), bool)
    state = State(np.eye(3), np.array([0., 0., 1.]), 0., np.zeros(4))
    estimate = Estimate('tracking', state, None, {}, .01)
    monkeypatch.setattr('arm_observer.perception.server.time.monotonic', lambda: 100.1)
    frame = Frame(rgb, np.ones((8, 8)), np.eye(3), 1, 100., {})
    payload = session.publish(frame, mask, estimate, .1, 100.)
    assert payload['pose_hz'] == 10 and payload['pose'] is not None
    acquiring = session.publish(frame, mask, Estimate('reacquiring', None, None, {}, 0), .001, 100.)
    assert acquiring['pose_hz'] is None
    monkeypatch.setattr('arm_observer.perception.server.time.monotonic', lambda: 100.7)
    frame = Frame(rgb, frame.depth_m, frame.K, 2, 100.6, {})
    expired = session.publish(frame, mask, estimate, .1, 100.)
    assert expired['pose'] is None and expired['pose_hz'] is None
    assert expired['mask_age_seconds'] > .5
