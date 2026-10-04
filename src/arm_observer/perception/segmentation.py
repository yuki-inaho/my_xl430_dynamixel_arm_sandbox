"""Automatic RGB foreground segmentation with pinned official BiRefNet lite weights."""

import time

import cv2
import numpy as np

MODEL_ID = 'ZhengPeng7/BiRefNet_lite'
REVISION = 'aa62cd87eafb9cc43056d08ef3615a14628b831d'


def registration_mask(mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Remove thin foreground cables from registration, preserving the raw mask separately."""
    if kernel_size < 1 or kernel_size % 2 != 1:
        raise ValueError('mask opening size must be a positive odd pixel count')
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)


class BiRefNetSegmenter:
    def __init__(self, size: int = 768, threshold: float = .5):
        import torch
        from transformers import AutoModelForImageSegmentation

        if not torch.cuda.is_available():
            raise RuntimeError('BiRefNet CUDA mode requires a working CUDA device')
        if size < 128 or size % 32 or not 0 < threshold < 1:
            raise ValueError('segmentation size must be a multiple of 32 >=128; threshold in (0,1)')
        # Batch-one GPU inference does not benefit from a large CPU thread pool;
        # keep CPU launches from contending with camera/registration workers.
        torch.set_num_threads(1)
        self.torch = torch
        self.size = size
        self.threshold = threshold
        self.model = AutoModelForImageSegmentation.from_pretrained(
            MODEL_ID, revision=REVISION, code_revision=REVISION,
            trust_remote_code=True, use_safetensors=True,
        ).eval().to('cuda').half()
        self.mean = torch.tensor([.485, .456, .406], device='cuda').reshape(1, 3, 1, 1)
        self.std = torch.tensor([.229, .224, .225], device='cuda').reshape(1, 3, 1, 1)
        self.last_seconds = None

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        torch = self.torch
        start = time.monotonic()
        resized = cv2.resize(rgb, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
        image = torch.as_tensor(resized, device='cuda').permute(2, 0, 1).unsqueeze(0).float() / 255
        image = ((image - self.mean) / self.std).half()
        with torch.inference_mode():
            logits = self.model(image)[-1]
            probability = logits.sigmoid().float()
            probability = torch.nn.functional.interpolate(
                probability, rgb.shape[:2], mode='bilinear', align_corners=False,
            )[0, 0].cpu().numpy()
        self.last_seconds = time.monotonic() - start
        return probability > self.threshold

    @property
    def provenance(self) -> dict:
        return {'model_id': MODEL_ID, 'revision': REVISION, 'input_size': self.size,
                'threshold': self.threshold, 'device': 'cuda', 'precision': 'float16',
                'cpu_threads': self.torch.get_num_threads(),
                'last_inference_seconds': self.last_seconds}
