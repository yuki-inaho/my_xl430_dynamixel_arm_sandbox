"""Build a static evidence gallery directly from scoped capture events, without motor access."""
import argparse
import html
import json
from datetime import datetime
from pathlib import Path


def build(root: Path, status: str):
    captures, notices = [], []
    for log in sorted(root.rglob("events.jsonl")):
        for number, line in enumerate(log.read_text().splitlines(), 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                notices.append(("", f"Incomplete event: {log.name}:{number}", log))
                continue
            if event.get("kind") == "capture":
                folder = log.parent / event["relative"]
                captures.append((event, folder, log))
            elif event.get("kind") in ("stop", "stop_hold_fault", "released_supported"):
                notices.append((event.get("at", ""), json.dumps(event, ensure_ascii=False), log))
    captures.sort(key=lambda item: item[0].get("at", ""))
    esc = html.escape

    def link(path, label):
        return f'<a href="{esc(path.relative_to(root).as_posix())}">{esc(label)}</a>'

    cards = []
    for event, folder, log in captures:
        observation = event.get("observation", {})
        image = folder / "color.png"
        if not image.is_file():
            notices.append((event.get("at", ""), f"Missing image: {image}", log))
            continue
        assets = [link(p, p.name) for p in sorted(folder.iterdir()) if p.is_file()]
        cards.append(
            '<article><h2>' + esc(f'{log.parent.name} / {event["label"]} / '
                                  f'{event["camera"]}') + '</h2><p>'
            + esc(event.get("at", "")) + '<br>実測count: '
            + esc(str(observation.get("positions", "未知"))) + '<br>active IDs: '
            + esc(str(observation.get("active_ids", "未知"))) + '</p>'
            + f'<a href="{esc(image.relative_to(root).as_posix())}">'
            + f'<img loading="lazy" src="{esc(image.relative_to(root).as_posix())}" '
              'alt="実機の撮影画像"></a><p class="assets">'
            + ' · '.join(assets) + '</p></article>'
        )
    rows = ''.join('<tr><td>' + esc(at) + '</td><td>' + esc(note)
                   + '</td><td>' + link(log, log.parent.name) + '</td></tr>'
                   for at, note, log in notices)
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>実機動作・二眼RGB-D記録</title><style>
body{margin:24px auto;padding:0 20px;max-width:1400px;background:#f4f1e9;color:#222;
font-family:system-ui,sans-serif;line-height:1.6}h1{font-size:1.6rem}
.status{border-left:5px solid #b44;padding:12px;background:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:16px}
article{background:white;padding:16px;border:1px solid #ccc;min-width:0}
h2{font-size:1rem;overflow-wrap:anywhere}img{width:100%;height:auto}
.assets{font-size:.85rem;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}
td{border:1px solid #ccc;padding:8px;overflow-wrap:anywhere;vertical-align:top}
td:nth-child(2){max-width:600px}a{color:#155b78}</style><h1>実機動作・二眼RGB-D記録</h1>'''
    page += '<p class="status">' + esc(status) + '</p><p>生成: '
    page += esc(datetime.now().astimezone().isoformat()) + '</p><p>'
    page += link(root / "WORKDOC.md", "作業書・判断・未達項目")
    page += '</p><p>指令角の達成、現物の姿勢、把持、支持復帰、脱力は別々に確認します。'
    page += '二眼はホスト時刻と前後READに対応し、ハード同期ではありません。'
    page += '画像をクリックすると保存された原寸画像を開きます。</p>'
    page += '<h2>停止・終了記録（途中の失敗を含む）</h2><table>' + rows + '</table>'
    page += '<h2>実測に対応する撮影</h2><div class="grid">' + ''.join(cards) + '</div></html>'
    (root / "REPORT.html").write_text(page)
    print(json.dumps({"captures": len(captures), "images": len(cards), "notices": len(notices),
                      "report": str(root / "REPORT.html")}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--status", required=True)
    args = parser.parse_args()
    build(args.root, args.status)


if __name__ == "__main__":
    main()
