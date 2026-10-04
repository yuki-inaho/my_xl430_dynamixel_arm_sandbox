"""Matched RGB/aligned metric depth/intrinsics for live and recorded observations."""

import json
import multiprocessing
import queue
import signal
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class Frame:
    rgb: np.ndarray
    depth_m: np.ndarray
    K: np.ndarray
    sequence: int
    received_monotonic: float
    metadata: dict


def prepare_frame(rgb, raw_depth, intrinsics, depth_scale, sequence, metadata,
                  width=640, received=None) -> Frame:
    if raw_depth.shape != rgb.shape[:2] or raw_depth.dtype != np.uint16:
        raise ValueError('depth must be uint16 and aligned to the same color frame')
    if not np.isfinite(depth_scale) or depth_scale <= 0:
        raise ValueError('invalid metric depth scale')
    K = np.array([[intrinsics['fx'], 0, intrinsics['ppx']],
                  [0, intrinsics['fy'], intrinsics['ppy']], [0, 0, 1]], dtype=float)
    coefficients = np.asarray(intrinsics['coeffs'], dtype=float)
    if np.any(coefficients != 0):
        model = intrinsics['model'].removeprefix('distortion.')
        if model not in ('brown_conrady', 'modified_brown_conrady'):
            raise ValueError(f'nonzero {model} distortion not supported; use a rectified source')
        size = (rgb.shape[1], rgb.shape[0])
        x, y = cv2.initUndistortRectifyMap(K, coefficients, None, K, size, cv2.CV_32FC1)
        rgb = cv2.remap(rgb, x, y, cv2.INTER_LINEAR)
        raw_depth = cv2.remap(raw_depth, x, y, cv2.INTER_NEAREST)
    scale = min(1.0, width / rgb.shape[1])
    size = (round(rgb.shape[1] * scale), round(rgb.shape[0] * scale))
    resized_rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
    depth = cv2.resize(raw_depth, size, interpolation=cv2.INTER_NEAREST)
    depth = depth.astype(np.float32)*depth_scale
    # OpenCV resize maps destination pixel centers to source pixel centers.
    K[0, 2] = (K[0, 2] + .5)*scale - .5
    K[1, 2] = (K[1, 2] + .5)*scale - .5
    K[0, 0] *= scale
    K[1, 1] *= scale
    details = dict(metadata, raw_depth_scale_m=depth_scale, intrinsics_original=intrinsics,
                   processed_resolution=list(size), rectified=bool(np.any(coefficients)))
    return Frame(resized_rgb, depth, K, sequence,
                 time.monotonic() if received is None else received, details)


def load_frame(directory: Path, sequence=0, width=640) -> Frame:
    meta = json.loads((directory / 'metadata.json').read_text())
    bgr = cv2.imread(str(directory / 'color.png'))
    depth = cv2.imread(str(directory / 'aligned_depth.png'), cv2.IMREAD_UNCHANGED)
    if bgr is None or depth is None:
        raise OSError(f'missing RGB/aligned depth at {directory}')
    return prepare_frame(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), depth,
                         meta['intrinsics']['color'], meta['depth_scale_m_per_count'],
                         sequence, dict(meta, recorded_source=str(directory)), width)


class RealSenseSource:
    """Camera-only SDK owner. No motor transport or hardware reset."""

    def __init__(self, serial: str, width=640):
        from pyrealsense2 import pyrealsense2 as rs

        self.rs = rs
        self.width = width
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_device(serial)
        config.enable_stream(rs.stream.color, 1280, 720, rs.format.rgb8, 30)
        config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 30)
        profile = self.pipeline.start(config)
        self.device = profile.get_device()
        self.depth_scale = self.device.first_depth_sensor().get_depth_scale()
        self.align = rs.align(rs.stream.color)

    def read(self) -> Frame:
        # The SDK's blocking wait can hold the Python GIL, starving the many
        # small CUDA launches in the inference thread. Poll briefly and yield.
        deadline = time.monotonic()+2
        frames = self.pipeline.poll_for_frames()
        while not frames:
            if time.monotonic() >= deadline:
                raise TimeoutError('camera frame timeout')
            time.sleep(.003)
            frames = self.pipeline.poll_for_frames()
        aligned = self.align.process(frames)
        received = time.monotonic()
        color, depth = aligned.get_color_frame(), aligned.get_depth_frame()
        if not color or not depth:
            raise RuntimeError('missing matched RGB-D frame')
        k = color.profile.as_video_stream_profile().get_intrinsics()
        intrinsics = dict(fx=k.fx, fy=k.fy, ppx=k.ppx, ppy=k.ppy,
                          coeffs=list(k.coeffs), model=str(k.model))
        meta = {
            'serial': self.device.get_info(self.rs.camera_info.serial_number),
            'device': self.device.get_info(self.rs.camera_info.name),
            'host_received_at': datetime.now(UTC).isoformat(),
            'color_timestamp_ms': color.get_timestamp(),
            'depth_timestamp_ms': depth.get_timestamp(),
            'timestamp_domain': str(color.get_frame_timestamp_domain()),
        }
        return prepare_frame(np.asanyarray(color.get_data()).copy(),
                             np.asanyarray(depth.get_data()).copy(), intrinsics,
                             self.depth_scale, color.get_frame_number(), meta,
                             self.width, received)

    def close(self) -> None:
        self.pipeline.stop()


def _camera_worker(serial, width, frames, stop):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    camera = None
    try:
        cv2.setNumThreads(1)
        camera = RealSenseSource(serial, width)
        while not stop.is_set():
            frame = camera.read()
            try:
                frames.put_nowait(frame)
            except queue.Full:
                try:
                    frames.get_nowait()
                    frames.put_nowait(frame)
                except (queue.Empty, queue.Full):
                    pass
    except Exception as error:
        frames.put(str(error), timeout=2)
    finally:
        if camera is not None:
            camera.close()


class ProcessCameraSource:
    """Keep native camera processing and its GIL ownership outside CUDA inference."""

    def __init__(self, serial: str, width=640):
        context = multiprocessing.get_context('spawn')
        self.frames = context.Queue(maxsize=1)
        self.stop = context.Event()
        self.process = context.Process(target=_camera_worker,
                                       args=(serial, width, self.frames, self.stop), daemon=True)
        self.started = False
        self.process.start()

    def read(self) -> Frame:
        try:
            item = self.frames.get(timeout=3 if self.started else 15)
        except queue.Empty as error:
            raise TimeoutError('camera worker produced no RGB-D frame') from error
        if isinstance(item, str):
            raise RuntimeError(item)
        self.started = True
        return item

    def close(self) -> None:
        self.stop.set()
        self.process.join(timeout=3)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=2)
        self.frames.close()
