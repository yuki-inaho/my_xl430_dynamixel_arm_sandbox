"""Latest-frame camera observation and a small browser viewer; no motor writes."""

import hashlib
import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
from articulated_filterreg.geometry import CadModel

from arm_observer.perception.renderer import CadRenderer
from arm_observer.perception.segmentation import BiRefNetSegmenter, registration_mask
from arm_observer.perception.tracker import Estimate, PoseTracker, RegistrationConfig

PAGE = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RGB-D / articulated FilterReg</title><style>
body{font:16px system-ui;background:#111b23;color:#e5edf5;margin:24px}
h1{font-size:24px} main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
img{width:100%;background:#26323d}pre{white-space:pre-wrap}#status{padding:14px;background:#26323d}
@media(max-width:700px){main{grid-template-columns:1fr}}</style>
<h1>RGB-D · articulated FilterReg</h1>
<p>水色の半透明部がCADです。関節角はCAD基準で、実機の校正角ではありません。</p>
<div id="status">読み込み中</div><main><section><h2>実画像とCAD</h2><img id="overlay"></section>
<section><h2>自動背景分離（登録用）</h2><img id="mask"></section></main><pre id="details"></pre>
<script>async function update(){try{const s=await(await fetch('/state.json')).json();
document.querySelector('#status').textContent=`${s.status} · pose ${s.pose_hz?.toFixed(1)??'—'} Hz ·
frame age ${s.frame_age_seconds?.toFixed(3)??'—'} s ·
mask age ${s.mask_age_seconds?.toFixed(3)??'—'} s`;
document.querySelector('#details').textContent=JSON.stringify(s,null,2);
for(const id of ['overlay','mask'])document.getElementById(id).src=`/${id}.jpg?v=${s.sequence}`;
}catch(e){document.querySelector('#status').textContent='接続待ち: '+e}
setTimeout(update,100)}update();
</script></html>'''


def propagate_mask(previous_rgb, previous_mask, rgb):
    height, width = rgb.shape[:2]
    small = (max(16, width//2), max(16, height//2))
    old = cv2.cvtColor(cv2.resize(previous_rgb, small), cv2.COLOR_RGB2GRAY)
    current = cv2.cvtColor(cv2.resize(rgb, small), cv2.COLOR_RGB2GRAY)
    # Backward flow: each current pixel samples the corresponding previous pixel.
    flow = np.empty((*current.shape, 2), np.float32)
    flow = cv2.calcOpticalFlowFarneback(current, old, flow, .5, 3, 15, 3, 5, 1.2, 0)
    flow = cv2.resize(flow, (width, height))
    flow[:, :, 0] *= width/small[0]
    flow[:, :, 1] *= height/small[1]
    y, x = np.indices((height, width), dtype=np.float32)
    return cv2.remap(previous_mask.astype(np.uint8), x+flow[:, :, 0], y+flow[:, :, 1],
                     cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT).astype(bool)


def jpeg(rgb):
    ok, encoded = cv2.imencode('.jpg', cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if not ok:
        raise OSError('JPEG encoding failed')
    return encoded.tobytes()


def save_image(path, pixels):
    if not cv2.imwrite(str(path), pixels):
        raise OSError(f'Image write failed: {path}')


def snapshot_bytes(snapshot):
    frame, mask, payload, mask_frame, raw_mask, images = snapshot
    stream = io.BytesIO()
    np.savez_compressed(stream, rgb=frame.rgb, depth_m=frame.depth_m, K=frame.K,
                        mask=mask, raw_mask=raw_mask, mask_rgb=mask_frame.rgb,
                        overlay_jpeg=np.frombuffer(images['overlay'], np.uint8),
                        metadata_json=json.dumps(dict(payload,
                                                     raw_mask_metadata=mask_frame.metadata,
                                                     raw_mask_sequence=mask_frame.sequence)))
    return stream.getvalue()


class LiveSession:
    def __init__(self, source, model_path: Path, output: Path, segmentation_size=768,
                 backend='native', initial_state=None):
        self.source = source
        self.model_path, self.output = model_path, output
        self.model_digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        self.segmentation_size = segmentation_size
        self.backend = backend
        self.initial_state = initial_state
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.frame = None
        self.segmented = None
        self.segmentation_provenance = {}
        self.segmentation_rejections = 0
        self.good_mask_area = None
        self.state = {'status': 'starting', 'sequence': 0}
        self.images = {}
        self.error = None
        self.snapshot = None
        self.writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix='pose-evidence')
        self.write_job = None
        self.skipped_evidence = 0
        self.threads = [threading.Thread(target=self.capture, daemon=True),
                        threading.Thread(target=self.segment, daemon=True),
                        threading.Thread(target=self.infer, daemon=True)]

    def start(self):
        self.output.mkdir(parents=True, exist_ok=True)
        for thread in self.threads:
            thread.start()

    def capture(self):
        try:
            while not self.stop.is_set():
                frame = self.source.read()
                with self.lock:
                    self.frame = frame
        except Exception as error:
            self.fail(error)

    def fail(self, error):
        if self.error is None:
            self.error = str(error)
        with self.lock:
            self.state = dict(self.state, status='error', reason=self.error, pose=None)
        self.stop.set()

    def segment(self):
        try:
            segmenter = BiRefNetSegmenter(self.segmentation_size)
            sequence = -1
            while not self.stop.is_set():
                frame = self.await_frame(sequence)
                mask = segmenter.predict(frame.rgb)
                with self.lock:
                    # Occasional neural masks drop most of a stationary arm.
                    # Reject the sudden collapse, retaining the old timestamp;
                    # prolonged missing geometry therefore still expires/losses.
                    area = int(np.count_nonzero(mask))
                    inconsistent = (self.good_mask_area is not None and
                                    not .5*self.good_mask_area <= area <= 2*self.good_mask_area)
                    if inconsistent:
                        self.segmentation_rejections += 1
                    else:
                        self.segmented = (frame, mask)
                    self.segmentation_provenance = segmenter.provenance
                sequence = frame.sequence
        except Exception as error:
            self.fail(error)

    def infer(self):
        renderer = None
        try:
            cv2.setNumThreads(1)
            model = CadModel.load(self.model_path)
            frame = self.await_frame(-1)
            renderer = CadRenderer(model, frame.rgb.shape[1], frame.rgb.shape[0])
            tracker = PoseTracker(model, renderer, RegistrationConfig(backend=self.backend),
                                  initial_state=self.initial_state)
            self.run_inference(tracker, frame)
        except Exception as error:
            self.fail(error)
        finally:
            if renderer is not None:
                renderer.close()

    def await_frame(self, sequence):
        while not self.stop.is_set():
            with self.lock:
                frame = self.frame
            if frame is not None and frame.sequence != sequence:
                return frame
            self.stop.wait(.005)
        raise RuntimeError('capture stopped')

    def run_inference(self, tracker, frame):
        counter, last_publish = 0, time.monotonic()
        with (self.output/'poses.jsonl').open('w') as journal:
            while not self.stop.is_set():
                with self.lock:
                    segmented = self.segmented
                    frame = self.frame
                if segmented is None or frame is None:
                    self.stop.wait(.005)
                    continue
                mask_frame, raw_mask = segmented
                mask_time = mask_frame.received_monotonic
                mask_start = time.monotonic()
                mask = raw_mask if frame.sequence == mask_frame.sequence else propagate_mask(
                    mask_frame.rgb, raw_mask, frame.rgb)
                opening = max(3, (round(7*frame.rgb.shape[1]/640)//2)*2+1)
                mask = registration_mask(mask, opening)
                mask_seconds = time.monotonic()-mask_start
                if tracker.state is None:
                    self.publish(frame, mask, Estimate('reacquiring', None, None, {}, 0),
                                 time.monotonic()-last_publish, mask_time)
                if frame.received_monotonic-mask_time > .5:
                    self.good_mask_area = None
                    estimate = Estimate('lost', None, None, {}, 0, 'segmentation mask is stale')
                else:
                    estimate = tracker.update(frame, mask)
                now = time.monotonic()
                payload = self.publish(frame, mask, estimate, now-last_publish, mask_time,
                                       {'mask_preparation': mask_seconds})
                with self.lock:
                    snapshot = (frame, mask, payload, mask_frame, raw_mask, dict(self.images))
                    self.snapshot = snapshot
                journal.write(json.dumps(payload, allow_nan=False)+'\n')
                journal.flush()
                if counter == 0 or counter % 30 == 0:
                    self.queue_evidence(snapshot)
                last_publish, counter = now, counter+1
                frame = self.await_frame(frame.sequence)

    def publish(self, frame, mask, estimate, interval, mask_time, timings=None):
        now = time.monotonic()
        age = now-frame.received_monotonic
        mask_age = now-mask_time
        fresh = max(age, mask_age) <= .5
        status = estimate.status if fresh else 'reacquiring'
        pose = estimate.state.to_dict() if fresh and estimate.state is not None else None
        payload = {
            'status': status, 'sequence': frame.sequence, 'pose': pose,
            'quality': estimate.quality, 'reason': estimate.reason,
            'pose_hz': 1/max(interval, .001) if status == 'tracking' else None,
            'frame_age_seconds': age,
            'frame_received_monotonic': frame.received_monotonic,
            'mask_age_seconds': mask_age, 'mask_received_monotonic': mask_time,
            'registration_seconds': estimate.elapsed_seconds,
            'model': self.model_path.name, 'model_sha256': self.model_digest,
            'gaussian_backend': self.backend,
            'metadata': frame.metadata,
            'segmentation_rejections': self.segmentation_rejections,
            'skipped_periodic_evidence': self.skipped_evidence,
            'segmentation': self.segmentation_provenance,
        }
        if status == 'tracking':
            self.good_mask_area = int(np.count_nonzero(mask))
        overlay = frame.rgb.copy()
        if fresh and estimate.rendering is not None:
            rendering = estimate.rendering
            tint = rendering.rgb[rendering.mask]*np.array([.3, .7, 1.]) + [20, 20, 40]
            overlay[rendering.mask] = (.5*overlay[rendering.mask] +
                                       .5*np.clip(tint, 0, 255)).astype(np.uint8)
        encode_start = time.monotonic()
        images = {'overlay': jpeg(overlay),
                  'mask': jpeg(np.where(mask[:, :, None], frame.rgb, frame.rgb//4))}
        payload['timings_seconds'] = dict(timings or {},
                                         registration=estimate.elapsed_seconds,
                                         jpeg=time.monotonic()-encode_start)
        with self.lock:
            self.state, self.images = payload, images
        return payload

    def queue_evidence(self, snapshot):
        if self.write_job is not None:
            if not self.write_job.done():
                self.skipped_evidence += 1
                return
            self.write_job.result()  # Disk errors remain visible and stop the session.
        self.write_job = self.writer.submit(self.save_evidence, *snapshot)

    def save_evidence(self, frame, mask, payload, mask_frame, raw_mask, images):
        prefix = self.output/f'frame-{frame.sequence:06d}'
        save_image(prefix.with_suffix('.png'), cv2.cvtColor(frame.rgb, cv2.COLOR_RGB2BGR))
        save_image(prefix.with_suffix('.mask.png'), mask.astype(np.uint8)*255)
        np.savez_compressed(prefix.with_suffix('.npz'), depth_m=frame.depth_m, K=frame.K)
        raw_prefix = self.output/f'segmentation-{mask_frame.sequence:06d}'
        save_image(raw_prefix.with_suffix('.png'), cv2.cvtColor(mask_frame.rgb, cv2.COLOR_RGB2BGR))
        save_image(raw_prefix.with_suffix('.raw-mask.png'), raw_mask.astype(np.uint8)*255)
        payload = dict(payload, raw_mask_rgb=raw_prefix.with_suffix('.png').name,
                       raw_mask_image=raw_prefix.with_suffix('.raw-mask.png').name,
                       raw_mask_metadata=mask_frame.metadata)
        prefix.with_suffix('.json').write_text(json.dumps(payload, indent=2, allow_nan=False))
        if payload['status'] == 'tracking' and payload['pose'] is not None:
            temporary = self.output/'last-good-pose.tmp'
            temporary.write_text(json.dumps(payload, indent=2, allow_nan=False))
            temporary.replace(self.output/'last-good-pose.json')
        (self.output/'segmentation.json').write_text(
            json.dumps(self.segmentation_provenance, indent=2))
        for key, data in images.items():
            (self.output/f'{key}.jpg').write_bytes(data)

    def close(self):
        self.stop.set()
        for thread in self.threads:
            if thread.ident is not None:
                thread.join(timeout=10)
        self.source.close()
        self.writer.shutdown(wait=True)
        if self.write_job is not None:
            self.write_job.result()


def view_state(state):
    received = state.get('frame_received_monotonic')
    if not isinstance(received, (int, float)):
        return state
    mask_received = state.get('mask_received_monotonic')
    if not isinstance(mask_received, (int, float)):
        mask_received = received
    now = time.monotonic()
    age, mask_age = now-received, now-mask_received
    state.update(frame_age_seconds=age, mask_age_seconds=mask_age)
    if max(age, mask_age) > .5 and state['status'] == 'tracking':
        state.update(status='lost', pose=None, pose_hz=None,
                     reason='published estimate or mask is stale')
    return state


def serve(session: LiveSession, port: int):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split('?')[0]
            if path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
                return
            with session.lock:
                state, images = dict(session.state), dict(session.images)
                frame = session.frame
                snapshot = session.snapshot
            state = view_state(state)
            if path == '/camera.jpg' and frame is not None:
                images['camera'] = jpeg(frame.rgb)
            if state['status'] != 'tracking' and frame is not None:
                images['overlay'] = jpeg(frame.rgb)
            if path == '/':
                data, content_type = PAGE.encode(), 'text/html; charset=utf-8'
            elif path == '/state.json':
                data, content_type = json.dumps(state, allow_nan=False).encode(), 'application/json'
            elif path == '/observation.npz' and snapshot is not None:
                if time.monotonic()-snapshot[0].received_monotonic > .5:
                    self.send_error(503, 'No fresh matched observation')
                    return
                data, content_type = snapshot_bytes(snapshot), 'application/octet-stream'
            elif path.removesuffix('.jpg').removeprefix('/') in images:
                data = images[path.removesuffix('.jpg').removeprefix('/')]
                content_type = 'image/jpeg'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args):
            pass

    server = None
    try:
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        session.start()
        print(f'viewer http://127.0.0.1:{port}', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        session.close()
