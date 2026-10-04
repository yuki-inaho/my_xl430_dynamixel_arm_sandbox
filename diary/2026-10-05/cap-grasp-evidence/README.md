# キャップ把持調査・実機記録

**把持・持上げ・元姿勢復帰・脱力は未達です。** 最新観測では全5軸トルクONで保持しています。CURRENT_STATE.jsonの時刻を確認し、現物を支える前に電源を切らないでください。ID2の復帰は350および一度の395試行で停滞、395は350へ復元済み。更なる増力/同じ帰路の再試行は実行しません。

- [HTMLギャラリー](REPORT.html)：76画像、二眼RGB-Dと時刻/実測count、失敗/停止記録。
- [作業書](WORKDOC.md)：手順1完了、把持経路以降とDoD未達。
- [最終READ状態](CURRENT_STATE.json)：履歴のOFFと現在のONを区別。
- [有限READ-only監視](holding-watch-0229.jsonl)：約15分、WRITEなし。監視は支持/制御/脱力/電源停止を実行しません。
- [ブラウザ確認](report-browser-verification.json)：76画像decode、704リンク200、横溢れなし。暗さ・crop・ノイズは残り、表示成功だけを撮像品質や把持証拠とは扱いません。
- [会話の復元](../CONVERSATION_EXPORT.md)

各撮影ディレクトリにはcolor.png、生/整列深度、IR、metadata.json、calibration.toml、robot-before-capture.jsonがあります。二眼はホスト時刻/前後READで対応し、ハード同期ではありません。元のカメラ保存データは ~/data/xl430-arm/2026-10-05/cap-grasp-evidence 以下。JSONLと実画像が根拠であり、ファイル名のnominal角を達成角とみなしません。

物理支持は未確認。支えた実状態をユーザーが確認した後、fresh identity/alias/profile/goalを照合して既存supported-release経路へ進みます。絶対ゼロ点・物理ID対応・全可動域衝突の認定は未完了です。
