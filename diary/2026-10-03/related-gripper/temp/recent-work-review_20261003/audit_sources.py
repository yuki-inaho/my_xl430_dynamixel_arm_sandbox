from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOTS = [Path('/home/inaho-omen/Project/3d-printed-dynamixel-gripper'), Path('/home/inaho-omen/Project/low_cost_robot')]
START = '2026-09-02T15:00:00'
END = '2026-10-03T15:00:00'
SKIP = {'.git', '.venv', 'node_modules', '.pixi', 'target', 'site-packages', '__pycache__'}
EXT = {'.md', '.txt', '.rst', '.adoc', '.org', '.html'}
RELATED = re.compile(r'low[-_]cost[-_]robot|3d-printed-dynamixel-gripper|onshape|urdf_from_step', re.I)


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def document_inventory():
    records = []
    seen = {}
    for root in ROOTS:
        paths = set()
        for section in ['docs', 'temp', 'studies', 'skills', 'diary', '.codex/skills']:
            base = root / section
            if base.exists():
                paths.update(p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in EXT)
                if section == '.codex/skills':
                    paths.update(base.glob('*/SKILL.md'))
        paths.update(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in EXT)
        for p in sorted(paths):
            if any(x in SKIP for x in p.parts) or HERE in p.parents:
                continue
            raw = p.read_bytes()
            body = raw.decode('utf-8', errors='replace')
            digest = hashlib.sha256(raw).hexdigest()
            lines = body.splitlines()
            headings = [{'line': i + 1, 'text': line} for i, line in enumerate(lines) if re.match(r'^#{1,6} ', line)]
            record = {'path': str(p), 'repo': root.name, 'bytes': len(raw), 'sha256': digest,
                      'mtime': datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                      'lines': len(lines), 'headings': headings,
                      'checkboxes': dict(Counter(re.findall(r'- \[([ xX])\]', body))),
                      'duplicate_of': seen.get(digest)}
            seen.setdefault(digest, str(p))
            # Full bytes are read; these excerpts are a navigation index, not a claim of an LLM full-text review.
            excerpts = []
            for i, h in enumerate(headings):
                a = h['line']
                b = headings[i + 1]['line'] - 1 if i + 1 < len(headings) else len(lines)
                section = [s for s in lines[a:b] if s.strip()]
                text = '\n'.join(section)
                excerpts.append({'heading': h['text'], 'line': h['line'], 'start': text[:650], 'end': text[-750:] if len(text) > 1000 else ''})
            record['excerpts'] = excerpts if headings else [{'heading': '', 'line': 1, 'start': body[:1000], 'end': body[-1000:]}]
            records.append(record)
    save('document_inventory.json', {'scope': 'all text documentation in named trees; dependency/build trees excluded', 'documents': records})
    print('DOCUMENTS', len(records), 'UNIQUE', len(seen), 'BY_REPO', dict(Counter(r['repo'] for r in records)))


def header(p):
    with p.open() as f:
        for i, line in enumerate(f):
            v = json.loads(line)
            if v.get('type') == 'session_meta':
                return v.get('payload', {})
            if i >= 12:
                return {}
    return {}


def tail_time(p):
    with p.open('rb') as f:
        f.seek(max(0, p.stat().st_size - 200000))
        lines = f.read().decode('utf-8', errors='replace').splitlines()
    stamps = []
    for line in lines[1:]:
        try:
            v = json.loads(line)
            if v.get('timestamp'):
                stamps.append(v['timestamp'])
        except ValueError:
            pass
    return max(stamps, default='')


def session_inventory():
    candidates = []
    inspected = 0
    for base in [Path('/home/inaho-omen/.codex/sessions'), Path('/home/inaho-omen/.codex/archived_sessions')]:
        for p in sorted(base.rglob('*.jsonl')):
            inspected += 1
            try:
                meta = header(p)
            except (OSError, ValueError):
                continue
            cwd = meta.get('cwd', '')
            last = tail_time(p)
            if last[:19] < START or meta.get('timestamp', '')[:19] >= END:
                continue
            reason = 'related working directory' if RELATED.search(cwd) else ''
            if cwd in ['/home/inaho-omen', '/home/inaho-omen/Project'] and not reason:
                with p.open() as f:
                    for line in f:
                        v = json.loads(line)
                        payload = v.get('payload', {})
                        if v.get('type') == 'event_msg' and payload.get('type') == 'user_message' and START <= v.get('timestamp', '')[:19] < END:
                            msg = payload.get('message', '')
                            if RELATED.search(msg) and not msg.startswith(('# AGENTS.md', '<environment_context>', '<INSTRUCTIONS>')):
                                reason = 'related explicit user message in generic working directory'
                                break
            if reason:
                candidates.append({'path': str(p), 'format': 'codex', 'meta': meta, 'last_timestamp': last, 'reason': reason, 'bytes': p.stat().st_size})
    for base in Path('/home/inaho-omen/.claude/projects').glob('*'):
        if not RELATED.search(base.name):
            continue
        for p in sorted(base.rglob('*.jsonl')):
            stamps = []
            with p.open() as f:
                for line in f:
                    try:
                        v = json.loads(line)
                        if v.get('timestamp'):
                            stamps.append(v['timestamp'])
                    except ValueError:
                        pass
            if any(START <= s[:19] < END for s in stamps):
                candidates.append({'path': str(p), 'format': 'claude_code', 'meta': {}, 'last_timestamp': max(stamps), 'reason': 'related Claude project and in-window event', 'bytes': p.stat().st_size})
    save('session_inventory.json', {'window_jst': ['2026-09-03T00:00:00+09:00', '2026-10-04T00:00:00+09:00'],
                                   'codex_headers_inspected': inspected, 'sessions': candidates})
    print('SESSIONS', len(candidates))
    for c in candidates:
        print(c['format'], c['path'], c['bytes'], c['last_timestamp'])


if __name__ == '__main__':
    document_inventory()
    session_inventory()
