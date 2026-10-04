"""Audit the actual exported PDFs with Poppler and OpenCV; no hardware access.

Run from the repository root: uv run --no-sync python <this-file>.
Requires system pdftoppm (Poppler). Raster measurements allow two pixels of
quantization; this verifies the digital PDF, not a physical printout.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from arm_observer.apriltag.detector import detect_tags

ROOT = Path(__file__).resolve().parent
DPI = 150
PX_PER_MM = DPI / 25.4


def check_sheet(entry):
    path = ROOT / entry['file']
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry['sha256']
    box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]', data)
    assert box is not None
    dimensions = [float(value) for value in box.groups()]
    assert np.allclose(dimensions, [595.28, 841.89], atol=1.0, rtol=0)
    assert data.count(b'/MediaBox') == 1
    prefix = ROOT / f"pdf-sheet-{entry['index']}"
    subprocess.run(
        ['pdftoppm', '-r', str(DPI), '-singlefile', '-png', str(path), str(prefix)],
        check=True, capture_output=True,
    )
    image = cv2.imread(str(prefix.with_suffix('.png')), cv2.IMREAD_GRAYSCALE)
    assert image is not None
    detections = detect_tags(image)
    ids = sorted(d.tag_id for d in detections)
    assert ids == entry['ids']
    sizes = []
    for detection in detections:
        corners = np.asarray(detection.corners)
        edges = np.linalg.norm(corners - np.roll(corners, 1, axis=0), axis=1) / PX_PER_MM
        assert np.all(np.abs(edges - 40.0) <= 2 / PX_PER_MM)
        sizes.extend(edges.tolist())
    _, _, stats, _ = cv2.connectedComponentsWithStats((image < 128).astype(np.uint8))
    # The ruler with its ticks is the only wide, thin connected black component.
    bars = [s for s in stats[1:] if s[2] > 90 * PX_PER_MM and s[3] < 6 * PX_PER_MM]
    assert len(bars) == 1
    bar_mm = float(bars[0][2]) / PX_PER_MM
    assert abs(bar_mm - 100.0) <= 2 / PX_PER_MM
    return {
        'file': path.name, 'sha256': entry['sha256'], 'mediabox_pt': dimensions,
        'detected_ids': ids, 'detected_count': len(detections),
        'tag_edge_min_mm': min(sizes), 'tag_edge_max_mm': max(sizes),
        'reference_bar_raster_mm': bar_mm, 'passed': True,
    }


if __name__ == '__main__':
    manifest = json.loads((ROOT / 'sheets.json').read_text())
    report = {
        'dpi': DPI, 'pixel_quantization_tolerance_mm': 2 / PX_PER_MM,
        'opencv': cv2.__version__, 'physical_print_validated': False,
        'sheets': [check_sheet(entry) for entry in manifest['sheets']],
    }
    (ROOT / 'pdf_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
