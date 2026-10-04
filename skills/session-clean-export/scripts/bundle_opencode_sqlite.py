"""Export one OpenCode SQLite session read-only; reasoning is explicitly omitted."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime
from pathlib import Path

from bundle_clean_json import redact


def read_session(database: Path, session_id: str) -> dict:
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')  # session/messages/parts share one consistent live snapshot
        session = db.execute(
            'SELECT id,title,directory,time_created,time_updated FROM session WHERE id=?',
            (session_id,),
        ).fetchone()
        if session is None:
            raise ValueError(f'session not found: {session_id}')
        rows = db.execute(
            'SELECT id,time_created,time_updated,data FROM message WHERE session_id=? '
            'ORDER BY time_created,id', (session_id,),
        ).fetchall()
        parts = db.execute(
            'SELECT id,message_id,time_created,time_updated,data FROM part WHERE session_id=? '
            'ORDER BY time_created,id', (session_id,),
        ).fetchall()
    by_message: dict[str, list] = {row['id']: [] for row in rows}
    excluded: Counter = Counter()
    for part in parts:
        data = json.loads(part['data'])
        if data.get('type') not in ('text', 'tool'):
            excluded[data.get('type', 'unknown')] += 1
            continue
        by_message[part['message_id']].append({
            'id': part['id'], 'created_ms': part['time_created'],
            'updated_ms': part['time_updated'], 'data': data,
        })
    messages = [{
        'id': row['id'], 'created_ms': row['time_created'], 'updated_ms': row['time_updated'],
        'data': json.loads(row['data']), 'parts': by_message[row['id']],
    } for row in rows]
    snapshot = {'session': dict(session), 'messages': messages}
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
    return {
        'schema': 'opencode-sqlite-clean-bundle/v1',
        'created_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'source': {'database': str(database.resolve()), 'session_id': session_id,
                   'selected_snapshot_sha256': hashlib.sha256(canonical).hexdigest(),
                   'message_count': len(messages),
                   'last_message_id': messages[-1]['id'] if messages else None},
        'extractor': 'read-only SQLite adapter (not agent-jsonl-compact)',
        'excluded_part_counts': dict(excluded),
        'user_coverage': {'source': sum(m['data']['role'] == 'user' for m in messages)},
        'coverage_notes': [
            'All selected message metadata and text/tool parts are preserved without truncation.',
            'reasoning and step metadata are omitted and counted explicitly.',
            'Hash covers selected metadata and retained parts before secret redaction, not the DB.',
            'The live database can grow after this transaction; later messages are not included.',
        ],
        **snapshot,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.name.endswith('_clean.json'):
        parser.error('output name must end with _clean.json')
    document = read_session(args.database, args.session_id)
    clean, redactions = redact(json.dumps(document, ensure_ascii=False))
    document = json.loads(clean)
    document['redactions'] = dict(redactions)
    observed = sum(m['data']['role'] == 'user' for m in document['messages'])
    assert observed == document['user_coverage']['source']
    document['user_coverage'].update({'output': observed, 'verified': True})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=1) + '\n')
    loaded = json.loads(args.output.read_text())
    assert len(loaded['messages']) == document['source']['message_count']
    print(json.dumps({'output': str(args.output), 'messages': len(loaded['messages']),
                      'users': observed, 'redactions': dict(redactions)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
