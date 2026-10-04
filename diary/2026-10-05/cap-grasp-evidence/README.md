# キャップ把持調査・実機記録

**把持・持上げ・元姿勢復帰・脱力は未達です。** 最新観測では全5軸トルクONで保持しています。CURRENT_STATE.jsonの時刻を確認し、現物を支える前に電源を切らないでください。ID2の復帰は350および一度の395試行で停滞、395は350へ復元済み。更なる増力/同じ帰路の再試行は実行しません。

- [HTMLギャラリー](REPORT.html)：76画像、二眼RGB-Dと時刻/実測count、失敗/停止記録。
- [作業書](WORKDOC.md)：手順1完了、把持経路以降とDoD未達。
- [最終READ状態](CURRENT_STATE.json)：履歴のOFFと現在のONを区別。
- [有限READ-only監視](holding-watch-0229.jsonl)：約15分、WRITEなし。監視は支持/制御/脱力/電源停止を実行しません。
- [ブラウザ確認](report-browser-verification.json)：76画像decode、704リンク200、横溢れなし。暗さ・crop・ノイズは残り、表示成功だけを撮像品質や把持証拠とは扱いません。
- [会話の復元](../CONVERSATION_EXPORT.md)

各撮影ディレクトリにはcolor.png、生/整列深度、IR、metadata.json、calibration.toml、robot-before-capture.jsonがあります。二眼はホスト時刻/前後READで対応し、ハード同期ではありません。元のカメラ保存データは ~/data/xl430-arm/2026-10-05/cap-grasp-evidence 以下。JSONLと実画像が根拠であり、ファイル名のnominal角を達成角とみなしません。

物理支持は未確認。支えた実状態をユーザーが確認した後、fresh identity/alias/profile/goalを照合してD19用の `scripts/cap_supported_release.py` へ進みます。通常photo CLIは今回のjaw310/ID2窓に適合しません。D19入口は既存release算法を再利用し、全OFFまでpark/設定復元を拒否します。`--support-confirmed --execute` は現物の重さを支えた実状態の確認後だけ指定します。READ-only watcherの現在の実所有者を確認し、その所有者だけ終了してserialを明け、最後の `return-output395-once/events.jsonl` を `--resume-log` に使います。絶対ゼロ点・物理ID対応・全可動域衝突の認定は未完了です。

[03:00の現物再確認](continuation-audit-0259/RECOVERY_BLOCKER_AUDIT.json)と二眼RGB-Dを追加しました。これは保持状態の撮影で、キャップ把持の証拠ではありません。

[現在の停止監査](CURRENT_BLOCKER_AUDIT.md)に3goalターン継続の条件、全DoDの未達と再開手順を記録しています。[03:25の二眼再確認](final-blocker-audit-0324/captures.json)でもcapは箱上です。HTMLは合計80画像、途中の23停止/終了記録を保全。最新の会話snapshotと復元情報は [CONVERSATION_EXPORT](../CONVERSATION_EXPORT.md) を参照してください。
