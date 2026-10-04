# 会話のfaithful clean JSONスナップショット

agent-jsonl-compact 0.2.0とsession-clean-exportを使用。
元の `2026-10-04_codex_session_01a10159_pose_review_clean.json` は親ディレクトリにローカル保存。
149.53MBのため、Gitにはlossless gzipを25MB以下のpartsとして保存している。
本文・画像付きtool記録は切り捨てていない。元JSONとの復元SHA256一致を確認済み。
107ユーザー発言のcoverageを照合。23:38 JSTのsnapshotでカメラ微調整の発言までを保持。
AWS形式の文字列1件を伏字、ほかの形式は0件。
暗号化されたreasoningは復元していない。会話は保存時点のsnapshotで、この後のcommit/push結果や
最終回答は含まれない。時刻・元のsnapshot hash・順序とpart hashは [manifest.json](manifest.json)。
snapshot後の「寝るので消灯」の1ユーザー発言は、原sessionのAPI recordから
[別記録](post-snapshot-user-messages.json)に保存した。これは後続tool全体の書き出しではない。

このディレクトリで次を実行するとJSONを復元できる。

```bash
rtk proxy sh -c 'cat 2026-10-04_codex_session_01a10159_pose_review_clean.json.gz.part-* | gzip -dc > restored_clean.json'
rtk proxy sha256sum restored_clean.json
```

manifestの `original_sha256` と比較する。機密伏字処理後のJSONを圧縮しており、圧縮で秘密を隠す
手順ではない。ユーザーの会話保存・push依頼に基づきPRIVATEリポジトリだけに格納する。
