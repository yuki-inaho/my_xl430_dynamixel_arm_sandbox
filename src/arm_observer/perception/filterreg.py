"""Fixed-observation Gaussian E step; the shared nanobind core supplies the M step."""

import numpy as np
from articulated_filterreg.native import GaussianMoments, _cloud


class GaussianCUDA:
    """Exact Gaussian moments in bounded CUDA batches, without nearest-point substitution."""

    def __init__(self, observations: np.ndarray, sigma: float, chunk: int = 512):
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError('CUDA unavailable; select native explicitly or install GPU extra')
        if not np.isfinite(sigma) or sigma <= 0 or chunk < 1:
            raise ValueError('sigma and chunk must be positive')
        self.torch = torch
        self.target = torch.as_tensor(_cloud(observations, 'observations'),
                                      dtype=torch.float32, device='cuda')
        self.values = torch.cat((
            torch.ones((len(observations), 1), device='cuda'), self.target,
            self.target.square().sum(1, keepdim=True),
        ), dim=1)
        self.sigma = sigma
        self.chunk = chunk

    def evaluate(self, queries: np.ndarray) -> np.ndarray:
        target, values = self.target, self.values
        if target is None or values is None:
            raise RuntimeError('filter is closed')
        torch = self.torch
        points = torch.as_tensor(_cloud(queries, 'queries'), dtype=torch.float32, device='cuda')
        output = []
        with torch.inference_mode():
            for batch in points.split(self.chunk):
                # Avoid the cancellation in ||x||²+||y||²-2x.y at millimetre sigma.
                distance = torch.cdist(
                    batch, target, compute_mode='donot_use_mm_for_euclid_dist')
                weights = torch.exp(distance.square() * (-.5 / self.sigma**2))
                output.append(weights @ values)
        return torch.cat(output).cpu().numpy().astype(np.float64)

    def close(self) -> None:
        self.target = None
        self.values = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def gaussian_filter(target: np.ndarray, sigma: float, backend: str):
    if backend == 'cuda':
        return GaussianCUDA(target, sigma)
    if backend == 'native':
        return GaussianMoments(target, sigma, 'lattice')
    raise ValueError('Gaussian backend must be cuda or native')
