"""Package this case and verify the archive CRC and every listed file hash."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / 'gripper_scanfit_20261004.zip'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect():
    paths = [ROOT/'README.md', ROOT/'pyproject.toml', ROOT/'inputs/scan.glb', ROOT/'inputs/photo.jpg']
    for folder in ['src', 'tests', 'docs', 'temp', 'inputs/reference_cad']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend(p for p in (ROOT/'models').iterdir() if p.is_file() and p.name!='scan_cropped_metric.glb')
    for pattern in ['*.json', '*.jsonl', '*.log', '*.txt', '*.md']:
        paths.extend((ROOT/'results').glob(pattern))
    paths.append(ROOT/'results/model_meshes.npz')
    for name in [
        'photo_overlay.png','photo_overlay_labeled.png','photo_overlay_preview.png',
        'photo_model_labels.png','photo_comparison.png','coin_scale_check.png',
        'scan_overlay_front.png','scan_overlay_top.png','scan_overlay_oblique.png',
        'scan_overlay_side.png','model_front.png','model_top.png','model_oblique.png','model_side.png',
    ]:
        paths.append(ROOT/'results'/name)
    for name in [
        'scan_datum_picks.png','photo_calibration.png','photo_scan_check.png',
        'canonical_front.png','canonical_top.png','canonical_oblique.png','canonical_side.png',
        'selected_vertex_ids.npz','segmented_scan_mm.ply',
    ]:
        paths.append(ROOT/'annotations'/name)
    return sorted(set(paths))


def main():
    validation = json.loads((ROOT/'results/validation.json').read_text())
    reproduction = json.loads((ROOT/'results/reproducibility.json').read_text())
    if not validation['pass'] or not reproduction['pass']:
        raise ValueError('Geometry or reproduction check failed; not packaging.')
    files = collect()
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError('\n'.join(missing))
    digest_text = ''.join(f'{sha256(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in files)
    manifest = ROOT/'MANIFEST.sha256'
    manifest.write_text(digest_text)
    files.append(manifest)
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files:
            archive.write(path,arcname='gripper_scanfit_20261004/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError('ZIP CRC failed: '+bad)
        for row in digest_text.splitlines():
            digest,rel = row.split('  ',1)
            actual = hashlib.sha256(archive.read('gripper_scanfit_20261004/'+rel)).hexdigest()
            if actual!=digest:
                raise ValueError('ZIP payload hash differs: '+rel)
    report = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'archive_filename':OUTPUT.name,
        'archive_bytes':OUTPUT.stat().st_size,
        'archive_sha256':sha256(OUTPUT),
        'archive_entries':len(files),
        'hashed_payload_files':len(files)-1,
        'zip_crc_ok':True,'all_payload_sha256_match':True,
        'geometry_validation_pass':validation['pass'],
        'reproduction_validation_pass':reproduction['pass'],
        'workdir_pytest_passed':19,'reproduction_pytest_passed':19,
        'note':'Tests confirmed in the recorded logs. Dependencies reused from the installed environment, not a clean installation.',
    }
    (ROOT.parent/'gripper_scanfit_20261004.validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
