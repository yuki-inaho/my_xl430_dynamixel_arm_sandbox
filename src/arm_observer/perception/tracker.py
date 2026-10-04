"""Metric articulated FilterReg with automatic initialization and visibility checks.

PCA proposes rigid initial poses; Gaussian moments and the shared per-body twist
core estimate the pose. A nearest-neighbour distance ranks initialization seeds
only. It never replaces the Gaussian E step or solves an ICP update.
"""

import itertools
import time
from dataclasses import dataclass

import cv2
import numpy as np
from articulated_filterreg.geometry import (
    CadModel,
    State,
    point_jacobians,
    projection,
    projection_jacobian,
)
from articulated_filterreg.native import assemble_blocks

# The compiled SciPy export has no usable annotation in the installed wheel.
from scipy.spatial import cKDTree  # ty: ignore[unresolved-import]

from arm_observer.perception.filterreg import gaussian_filter
from arm_observer.perception.renderer import CadRenderer, Rendered
from arm_observer.perception.source import Frame


@dataclass(frozen=True)
class RegistrationConfig:
    backend: str = 'native'
    point_limit: int = 1200
    tracking_iterations: int = 1
    min_iou: float = .60
    max_residual_m: float = .015
    max_frame_age: float = .5
    upright_base: bool = True
    min_base_points: int = 100
    max_base_depth_error_m: float = .015


@dataclass(frozen=True)
class Estimate:
    status: str
    state: State | None
    rendering: Rendered | None
    quality: dict
    elapsed_seconds: float
    reason: str | None = None


def sample_points(frame: Frame, mask: np.ndarray, limit: int) -> np.ndarray:
    if mask.shape != frame.depth_m.shape:
        raise ValueError('mask and aligned depth dimensions differ')
    valid = mask & np.isfinite(frame.depth_m) & (frame.depth_m > .1) & (frame.depth_m < 4)
    y, x = np.nonzero(valid)
    if len(y) < 100:
        raise ValueError('fewer than 100 valid foreground depth samples')
    z = frame.depth_m[y, x]
    keep = abs(z - np.median(z)) < .25
    y, x, z = y[keep], x[keep], z[keep]
    indices = np.linspace(0, len(z) - 1, min(limit, len(z)), dtype=int)
    x, y, z = x[indices], y[indices], z[indices]
    return np.column_stack(((x-frame.K[0, 2])*z/frame.K[0, 0],
                            (y-frame.K[1, 2])*z/frame.K[1, 1], z))


def _surface(rendering: Rendered, limit: int):
    y, x = np.nonzero(rendering.mask)
    if len(y) < 100:
        raise ValueError('fewer than 100 visible CAD samples')
    indices = np.linspace(0, len(y) - 1, min(limit, len(y)), dtype=int)
    y, x = y[indices], x[indices]
    return rendering.xyz[y, x].astype(float), rendering.levels[y, x], y, x


def _silhouette_field(mask):
    # Image assistance is explicit and comes solely from the automatic RGB mask.
    inside = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    outside = cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 3)
    distance = outside - inside
    gy, gx = np.gradient(distance)
    return distance, gy, gx


def _silhouette_terms(rendering, maps, K, field):
    distance, gy, gx = field
    boundary = rendering.mask & ~cv2.erode(
        rendering.mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    boundary[[0, -1], :] = False
    boundary[:, [0, -1]] = False
    yy, xx = np.nonzero(boundary)
    yy, xx = yy[::2], xx[::2]
    p, b = rendering.xyz[yy, xx].astype(float), rendering.levels[yy, xx]
    if len(p) == 0:
        return (np.zeros((maps.shape[-1], maps.shape[-1])), np.zeros(maps.shape[-1]),
                p, b, distance)
    J = np.einsum('nij,njk->nik', projection_jacobian(p, K), point_jacobians(p, b, maps))
    js = np.einsum('ni,nij->nj', np.column_stack((gx[yy, xx], gy[yy, xx])), J)
    residual = distance[yy, xx]
    weight = np.minimum(1., 8/np.maximum(abs(residual), 1e-10)) / (len(p)*16)
    return js.T@(weight[:, None]*js), -js.T@(weight*residual), p, b, distance


def _reference(model, points, levels, state):
    transforms = model.chain.transforms(state)
    out = np.empty_like(points)
    for level, transform in enumerate(transforms):
        keep = levels == level
        out[keep] = (points[keep]-transform[:3, 3])@transform[:3, :3]
    return out


def _increment(H, g, state, fixed_root):
    active = np.arange(7, len(g)) if fixed_root else np.r_[np.arange(6), np.arange(7, len(g))]
    h = H[np.ix_(active, active)]
    damping = .002*np.maximum(np.diag(h), 1)
    delta = np.zeros(len(g))
    delta[active] = np.linalg.solve(h+np.diag(damping), g[active])
    origin_motion = delta[3:6] + np.cross(delta[:3], state.translation)
    ratio = max(1., np.linalg.norm(delta[:3])/.12, np.linalg.norm(origin_motion)/.02,
                float(np.max(abs(delta[7:])))/.15)
    return delta/ratio


def _frozen_cost(model, state, reference, body, mu, weights, boundary, levels, distance, K):
    points = model.chain.transform(reference, body, state)
    if np.min(points[:, 2]) <= .05:
        return float('inf')
    value = np.sum(weights*np.sum((points-mu)**2, axis=1))/(weights.sum()*.012**2)
    if len(boundary):
        p = model.chain.transform(boundary, levels, state)
        if np.min(p[:, 2]) <= .05:
            return float('inf')
        pixels = projection(p, K).astype(np.float32)
        residual = abs(cv2.remap(distance.astype(np.float32), pixels[:, 0].reshape(1, -1),
                                pixels[:, 1].reshape(1, -1), cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=100).ravel())
        value += np.mean(np.where(residual <= 8, residual**2, 16*residual-64))/16
    return value


def _line_step(model, state, points, body, mu, weights, delta, upright_base,
               K, foot_row_min, boundary, boundary_levels, distance):
    reference = _reference(model, points, body, state)
    boundary_reference = _reference(model, boundary, boundary_levels, state)
    old = _frozen_cost(model, state, reference, body, mu, weights,
                       boundary_reference, boundary_levels, distance, K)
    for factor in (1., .5, .25, .125):
        proposed = state.increment(delta*factor)
        if upright_base and proposed.rotation[1, 2] > -.5:
            continue
        foot = proposed.rotation@np.array([0., -.028, .004]) + proposed.translation
        if upright_base and K[1, 1]*foot[1]/foot[2]+K[1, 2] < foot_row_min:
            continue
        if np.max(abs(proposed.joints)) > np.pi:
            continue
        cost = _frozen_cost(model, proposed, reference, body, mu, weights,
                            boundary_reference, boundary_levels, distance, K)
        if cost < old:
            return proposed
    return state


def register(model, renderer, frame, mask, target, initial, config,
             sigmas=(.012, .006), iterations=3, fixed_root=False):
    state = initial
    field = _silhouette_field(mask)
    lower_row = np.max(np.nonzero(mask)[0])
    foot_row_min = lower_row-frame.K[1, 1]*.05/np.median(target[:, 2])
    for sigma in sigmas:
        with gaussian_filter(target, sigma, config.backend) as gaussian:
            for _ in range(iterations):
                rendering = renderer.render(state, frame.K)
                points, body, y, x = _surface(rendering, config.point_limit)
                moments = gaussian.evaluate(points)
                mass = moments[:, 0]
                valid = mass > 1e-8
                if np.count_nonzero(valid) < 50:
                    raise ValueError('insufficient Gaussian overlap')
                p, b, mass, moment = points[valid], body[valid], mass[valid], moments[valid]
                mu = moment[:, 1:4]/mass[:, None]
                outlier = (2*np.pi*sigma*sigma)**1.5*.1/.9*len(target)/len(p)
                weights = mass/(mass+outlier)
                maps = model.chain.space_maps(state)
                H, g = assemble_blocks(p, mu, weights, b, maps)
                H /= weights.sum()*.012**2
                g /= weights.sum()*.012**2
                ih, ig, bp, bl, distance = _silhouette_terms(
                    rendering, maps, frame.K, field)
                updated = _line_step(model, state, p, b, mu, weights,
                                     _increment(H+ih, g+ig, state, fixed_root), config.upright_base,
                                     frame.K, foot_row_min, bp, bl, distance)
                if updated is state:
                    break
                state = updated
    return state


def base_quality(image, frame):
    base = image.mask & (image.levels == 0)
    valid = base & np.isfinite(frame.depth_m) & (frame.depth_m > .1) & (frame.depth_m < 4)
    count = int(np.count_nonzero(valid))
    error = (float(np.median(abs(image.xyz[:, :, 2][valid]-frame.depth_m[valid])))
             if count else None)
    return {'base_depth_points': count, 'median_base_depth_error_m': error}


def quality(renderer, frame, mask, target, state):
    image = renderer.render(state, frame.K)
    points, _, _, _ = _surface(image, 1500)
    distances = cKDTree(target).query(points, workers=1)[0]
    intersection = np.count_nonzero(image.mask & mask)
    union = np.count_nonzero(image.mask | mask)
    return image, {
        'iou': float(intersection)/max(int(union), 1),
        'median_surface_residual_m': float(np.median(distances)),
        'p90_surface_residual_m': float(np.percentile(distances, 90)),
        'scale': state.scale, 'observed_points': len(target),
        **base_quality(image, frame),
    }


def _basis(points):
    centered = points-points.mean(0)
    _, _, vectors = np.linalg.svd(centered, full_matrices=False)
    basis = vectors.T
    if np.linalg.det(basis) < 0:
        basis[:, -1] *= -1
    return basis


def _orientations():
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            rotation = np.eye(3)[:, permutation]*np.asarray(signs)
            if np.linalg.det(rotation) > 0:
                yield rotation


def _initial_proposals(model, frame, mask, target, config):
    # Deterministic area-weighted triangle samples, avoiding tessellation-density bias.
    triangles = model.vertices[model.faces]
    centers = triangles.mean(axis=1)
    areas = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0],
                                    triangles[:, 2]-triangles[:, 0]), axis=1)
    chosen = np.random.default_rng(17).choice(len(areas), 2500, p=areas/areas.sum())
    reference, levels = centers[chosen], model.face_level[chosen]
    target_basis = _basis(target)
    tree = cKDTree(target)
    # In an upright tabletop view the lowest thick foreground region supplies a
    # second initialization proposal for the partly occluded foot. It is not a
    # fitted landmark or a calibration measurement.
    lower = target[:, 1] >= np.percentile(target[:, 1], 90)
    foot = target[lower].mean(0)
    reference_foot = np.array([0., -.028, .004])
    lower_row = np.max(np.nonzero(mask)[0])
    foot_row_min = lower_row-frame.K[1, 1]*.05/np.median(target[:, 2])
    candidates = []
    for shoulder, elbow, wrist in itertools.product(
            (-1., 0., 1.), (-1.5, -.75, 0., .75, 1.5), (-1.5, 0., 1.5)):
        joints = np.array([0., shoulder, elbow, wrist])
        source = model.chain.transform(reference, levels, State(np.eye(3), np.zeros(3), 0., joints))
        basis = _basis(source)
        for orientation in _orientations():
            rotation = target_basis@orientation@basis.T
            if config.upright_base and rotation[1, 2] > -.5:
                continue
            translations = (target.mean(0)-rotation@source.mean(0), foot-rotation@reference_foot)
            for translation in translations:
                camera_foot = rotation@reference_foot+translation
                foot_row = frame.K[1, 1]*camera_foot[1]/camera_foot[2]+frame.K[1, 2]
                if config.upright_base and foot_row < foot_row_min:
                    continue
                points = source@rotation.T+translation
                distances = tree.query(points, workers=1)[0]
                score = np.mean(np.minimum(distances, .04)**2)
                candidates.append((score, State(rotation, translation, 0., joints)))
    return candidates


def _visible_proposals(renderer, frame, mask, target, candidates):
    visible_candidates = []
    for _, state in sorted(candidates, key=lambda item: item[0])[:100]:
        try:
            _, metrics = quality(renderer, frame, mask, target, state)
            score = metrics['median_surface_residual_m'] + .03*(1-metrics['iou'])
            visible_candidates.append((score, state))
        except ValueError:
            continue
    return visible_candidates


def initialize(model, renderer, frame, mask, target, config):
    candidates = _initial_proposals(model, frame, mask, target, config)
    visible_candidates = _visible_proposals(renderer, frame, mask, target, candidates)
    best = None
    for _, initial in sorted(visible_candidates, key=lambda item: item[0])[:12]:
        try:
            state = register(model, renderer, frame, mask, target, initial, config,
                             sigmas=(.03, .016, .008, .004), iterations=12)
            image, metrics = quality(renderer, frame, mask, target, state)
            score = metrics['median_surface_residual_m'] + .03*(1-metrics['iou'])
            if best is None or score < best[0]:
                best = score, state, image, metrics
        except ValueError:
            continue
    if best is None:
        raise ValueError('no initialization candidate overlaps the observed arm')
    state = register(model, renderer, frame, mask, target, best[1], config,
                     sigmas=(.015, .008, .004), iterations=20)
    image, metrics = quality(renderer, frame, mask, target, state)
    score = metrics['median_surface_residual_m'] + .03*(1-metrics['iou'])
    return (state, image, metrics) if score < best[0] else best[1:]


class PoseTracker:
    def __init__(self, model: CadModel, renderer: CadRenderer,
                 config=RegistrationConfig(), initial_state=None):
        self.model, self.renderer, self.config = model, renderer, config
        self.state = None
        self.seed = initial_state
        self.failures = 0

    def acceptable(self, metrics):
        return (metrics['iou'] >= self.config.min_iou and
                metrics['median_surface_residual_m'] <= self.config.max_residual_m and
                self.base_present(metrics))

    def base_present(self, metrics):
        error = metrics['median_base_depth_error_m']
        return (metrics['base_depth_points'] >= self.config.min_base_points and
                error is not None and error <= self.config.max_base_depth_error_m)

    def update(self, frame: Frame, mask: np.ndarray, acquire=True) -> Estimate:
        start = time.monotonic()
        if start-frame.received_monotonic > self.config.max_frame_age:
            return Estimate('lost', None, None, {}, 0, 'frame is stale')
        try:
            target = sample_points(frame, mask, self.config.point_limit)
            state, image, metrics = self._fit(frame, mask, target, acquire)
            # Continue a converging small-step estimate internally. Publishing
            # remains quality-gated; three failures still discard this candidate.
            # Otherwise each rejected step restarted from the same old pose and
            # could never follow a motion exceeding one iteration's step limit.
            self.state = state
            if not self.acceptable(metrics):
                raise ValueError(f'CAD mismatch: {metrics}')
        except (ValueError, np.linalg.LinAlgError) as error:
            self.failures += 1
            if self.failures >= 3:
                self.state = None
            return Estimate('lost', None, None, {}, time.monotonic()-start, str(error))
        self.state, self.seed, self.failures = state, state, 0
        return Estimate('tracking', state, image, metrics, time.monotonic()-start)

    def _fit(self, frame, mask, target, acquire):
        # A fixed tabletop scene retains its last accepted root after loss. Check
        # aligned depth independently of RGB masks, which often omit the black foot.
        if self.seed is not None:
            base = base_quality(self.renderer.render(self.seed, frame.K), frame)
            if not self.base_present(base):
                raise ValueError(f'fixed base absent or scene moved: {base}')
        if self.state is None:
            if not acquire:
                raise ValueError('reacquisition pending')
            recovered = self.try_seed(frame, mask, target)
            if recovered is not None:
                return recovered
            if self.seed is not None:
                raise ValueError('fixed-scene reacquisition failed; root retained')
            return initialize(self.model, self.renderer, frame, mask, target, self.config)
        state = register(self.model, self.renderer, frame, mask, target, self.state,
                         self.config, sigmas=(.008,),
                         iterations=self.config.tracking_iterations, fixed_root=True)
        image, metrics = quality(self.renderer, frame, mask, target, state)
        return state, image, metrics

    def try_seed(self, frame, mask, target):
        if self.seed is None:
            return None
        try:
            state = register(self.model, self.renderer, frame, mask, target, self.seed,
                             self.config, sigmas=(.025, .012, .006), iterations=8,
                             fixed_root=True)
            image, metrics = quality(self.renderer, frame, mask, target, state)
            if self.acceptable(metrics):
                return state, image, metrics
        except (ValueError, np.linalg.LinAlgError):
            pass
        return None
