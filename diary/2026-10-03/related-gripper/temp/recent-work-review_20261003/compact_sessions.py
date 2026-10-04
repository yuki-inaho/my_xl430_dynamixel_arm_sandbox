from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from audit_sources import END, HERE, ROOTS, START, save


def stamp(event):
    return event.get('ts') or event.get('timestamp') or ''


def in_window(ts):
    return START <= ts[:19] < END


def compact_native():
    records = []
    inventory = json.loads((HERE / 'session_inventory.json').read_text())
    for candidate in inventory['sessions']:
        source = Path(candidate['path'])
        if '01a10074-144c-7533-9b62-356427e7f92a' in source.name:
            records.append({'source': str(source), 'status': 'excluded_current_audit_session'})
            continue
        unrelated = {
            '01a0daf1-5d94-73c2-803c-b221022d8efd': 'statusline-only copied session',
            'cdf03f2c-582c-47dd-acbc-447d91220865': 'Claude statusline configuration',
            '01a07086-7984-79b3-bb84-2266cf6fa1ce': 'KiCad task only mentioning low_cost_robot as a CAD-tool reference',
        }
        exclusion = next((reason for sid, reason in unrelated.items() if sid in source.name), None)
        if exclusion:
            records.append({'source': str(source), 'status': 'excluded_unrelated_task', 'reason': exclusion})
            continue
        fmt = candidate['format']
        session_id = candidate.get('meta', {}).get('id') or source.stem
        name = f'{fmt}_{session_id}'
        stage = HERE / 'inputs' / f'{name}.jsonl'
        stage.parent.mkdir(exist_ok=True)
        supplement = []
        count = 0
        original_hash = hashlib.sha256()
        with source.open('rb') as f, stage.open('w') as out:
            for raw in f:
                original_hash.update(raw)
                event = json.loads(raw)
                ts = event.get('timestamp', '')
                is_meta = event.get('type') == 'session_meta'
                if not is_meta and not in_window(ts):
                    continue
                out.write(json.dumps(event, ensure_ascii=False) + '\n')
                if not is_meta:
                    count += 1
                payload = event.get('payload', {})
                if fmt == 'codex' and event.get('type') == 'response_item' and payload.get('type') in ('custom_tool_call', 'custom_tool_call_output'):
                    supplement.append({'ts': ts, 'kind': payload['type'], 'payload': payload, 'extractor': 'supplemental raw response_item; unsupported by agent-jsonl-compact 0.2.0'})
                if fmt == 'codex' and event.get('type') == 'event_msg' and payload.get('type') == 'item_completed' and payload.get('item', {}).get('type') == 'CommandExecution':
                    supplement.append({'ts': ts, 'kind': 'command_execution_detail', 'payload': payload['item'], 'extractor': 'supplemental terminal command detail; compact item_completed otherwise preserves only its type'})
        if not count:
            records.append({'source': str(source), 'status': 'excluded_no_in_window_work_events'})
            continue
        extracts = HERE / 'extracts'
        cmd = ['agent-jsonl-compact', '-i', str(stage), '-o', str(extracts), '--name', name, '--format', fmt]
        if fmt == 'codex':
            cmd.extend(['--channel', 'both'])
        result = subprocess.run(cmd, capture_output=True, text=True)
        (HERE / f'{name}.extractor.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            records.append({'source': str(source), 'status': 'extractor_error', 'exit_code': result.returncode})
            continue
        summary = json.loads((extracts / f'{name}.summary.json').read_text())
        events = [json.loads(line) for line in (extracts / f'{name}.clean.jsonl').read_text().splitlines() if line.strip()]
        events = [e for e in events if e.get('kind') != 'session' and in_window(stamp(e))]
        events.extend(supplement)
        events.sort(key=stamp)
        destination = HERE / f'{name}_clean.json'
        wrapper = {'schema_version': 1, 'source': {'path': str(source), 'sha256': original_hash.hexdigest(), 'session_id': session_id, 'format': fmt},
                   'window_jst': inventory['window_jst'],
                   'extraction': {'tool': 'agent-jsonl-compact 0.2.0', 'channel': 'both' if fmt == 'codex' else None,
                                  'message_char_limit': 0, 'tool_output_char_limit': 0, 'elide_outputs': False,
                                  'supplemental_custom_tool_events': len(supplement),
                                  'note': 'Period filtering removes older records; compactor noise removal/dedup remains enabled. This is a local transcript, not a publication artifact.'},
                   'summary': summary, 'event_count': len(events), 'events': events}
        destination.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2) + '\n')
        record = {'source': str(source), 'status': 'compacted', 'clean_json': str(destination), 'events': len(events),
                  'first': stamp(events[0]) if events else None, 'last': stamp(events[-1]) if events else None,
                  'kinds': dict(Counter(e.get('kind') for e in events)), 'supplemental_events': len(supplement)}
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    return records


def opencode_exports():
    database = Path('/home/inaho-omen/.local/share/opencode/opencode.db')
    if not database.exists():
        return []
    db = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
    records = []
    rows = db.execute("select id,directory,title from session where directory like '%low_cost_robot%' or directory like '%gripper%' or directory like '%onshape%' or directory like '%urdf_from_step%'").fetchall()
    for sid, directory, title in rows:
        if sid == 'ses_f2e8a0ee0ffeoHSAZsNimlOM6X':
            records.append({'source_session_id': sid, 'status': 'excluded_unrelated_ssd_task', 'title': title})
            continue
        events = []
        query = 'select m.id,m.time_created,m.data,p.data from message m join part p on p.message_id=m.id where m.session_id=? order by m.time_created,p.time_created,p.id'
        for mid, created, message_data, part_data in db.execute(query, (sid,)):
            ts = datetime.fromtimestamp(created / 1000, timezone.utc).isoformat()
            if not in_window(ts):
                continue
            message, part = json.loads(message_data), json.loads(part_data)
            kind = part.get('type')
            if kind == 'text':
                events.append({'ts': ts, 'kind': message.get('role'), 'text': part.get('text', ''), 'message_id': mid})
            elif kind == 'tool':
                events.append({'ts': ts, 'kind': 'tool', 'message_id': mid, 'payload': part})
        if not events:
            continue
        destination = HERE / f'opencode_{sid}_clean.json'
        save(destination.name, {'schema_version': 1, 'source': {'format': 'opencode_sqlite', 'database': str(database), 'session_id': sid, 'directory': directory, 'title': title},
                                'extraction': {'tool': 'read-only SQLite message/part export', 'note': 'agent-jsonl-compact 0.2.0 does not support the persisted SQLite store or opencode export single JSON. No synthetic run JSONL was invented.', 'included': ['user/assistant text', 'tool state'], 'excluded': ['reasoning', 'snapshot/step metadata']},
                                'event_count': len(events), 'events': events})
        record = {'source_session_id': sid, 'status': 'sqlite_read_only_export', 'clean_json': str(destination), 'events': len(events), 'first': stamp(events[0]), 'last': stamp(events[-1])}
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    return records


def saved_snapshot():
    source = ROOTS[1] / 'temp/session_extracts/2026-09-19_low_cost_robot_cad_activity/clean.json'
    wrapper = json.loads(source.read_text())
    events = [e for e in wrapper['events'] if in_window(stamp(e))]
    destination = HERE / 'codex_saved_20260919_cad_activity_clean.json'
    save(destination.name, {'schema_version': 1, 'source': {'format': 'existing_clean_json_snapshot', 'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'original': wrapper.get('source')},
                            'extraction': {'note': 'Existing compact visible-conversation snapshot retained with its recorded limitations. Broader explicit-prompt discovery also located its original May-start rollout, extracted separately.', 'original_scope': wrapper.get('scope')},
                            'event_count': len(events), 'events': events})
    return {'source': str(source), 'status': 'retained_existing_snapshot', 'clean_json': str(destination), 'events': len(events)}


if __name__ == '__main__':
    records = compact_native() + opencode_exports() + [saved_snapshot()]
    save('clean_index.json', {'window_jst': ['2026-09-03T00:00:00+09:00', '2026-10-04T00:00:00+09:00'], 'records': records})
