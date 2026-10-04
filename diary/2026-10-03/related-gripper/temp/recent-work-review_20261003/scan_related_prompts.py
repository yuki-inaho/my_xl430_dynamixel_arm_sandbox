import json
from pathlib import Path
from audit_sources import HERE, START, END, RELATED, header, tail_time, save

inventory = json.loads((HERE / 'session_inventory.json').read_text())
known = {r['path'] for r in inventory['sessions']}
matches = []
scanned = 0
for base in [Path('/home/inaho-omen/.codex/sessions'), Path('/home/inaho-omen/.codex/archived_sessions')]:
    for p in base.rglob('*.jsonl'):
        if str(p) in known:
            continue
        try:
            meta = header(p)
            last = tail_time(p)
        except (OSError, ValueError):
            continue
        if last[:19] < START or meta.get('timestamp', '')[:19] >= END:
            continue
        scanned += 1
        reasons = []
        with p.open() as f:
            for line in f:
                # Avoid JSON parsing unrelated large tool outputs; relevant user/turn-context records still parse in full.
                if not any(word in line for word in ['user_message', '"role": "user"', '"role":"user"', 'turn_context']):
                    continue
                event = json.loads(line)
                if not START <= event.get('timestamp', '')[:19] < END:
                    continue
                payload = event.get('payload', {})
                if event.get('type') == 'turn_context' and RELATED.search(payload.get('cwd', '')):
                    reasons.append('in-window turn cwd: ' + payload['cwd'])
                text = ''
                if event.get('type') == 'event_msg' and payload.get('type') == 'user_message':
                    text = payload.get('message', '')
                elif event.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'user':
                    text = '\n'.join(c.get('text', '') for c in payload.get('content', []))
                if text and RELATED.search(text) and not text.startswith(('# AGENTS.md', '<environment_context>', '<INSTRUCTIONS>', '<skills_instructions>', '<recommended_plugins>', '<subagent_notification>')):
                    reasons.append('explicit related user text: ' + text[:250])
                if reasons:
                    break
        if reasons:
            candidate = {'path': str(p), 'format': 'codex', 'meta': meta, 'last_timestamp': last, 'reason': reasons, 'bytes': p.stat().st_size}
            matches.append(candidate)
            print(p, reasons, flush=True)
inventory['broader_recent_sessions_scanned'] = scanned
inventory['sessions'].extend(matches)
save('session_inventory.json', inventory)
save('broader_discovery.json', {'scanned': scanned, 'new_matches': matches})
print('SCANNED', scanned, 'NEW', len(matches), flush=True)
