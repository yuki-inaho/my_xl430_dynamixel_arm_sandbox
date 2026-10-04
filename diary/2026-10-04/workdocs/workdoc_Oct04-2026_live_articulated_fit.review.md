# 作業書レビュー

**Verdict:** PASS_WITH_NOTES

**Mode:** review-and-fix（Codex単独、独立エージェントレビューではない）

**Findings**

- Minor: RGB歪み補正とCAD pinhole描画の前提が不足。SDK intrinsicsを取得して同一remapを明記。
- Minor: Python3.13とCUDA wheelの互換性を事前成功とみなせない。依存固定前に実確認する。
- Minor: リアルタイム定常速度と初期化時間の区別を追記。

**Applied Changes**

- §1.2へ歪み、依存、モデル版/時刻/初期化計測の補足を追記。目標や元の閾値は変更しない。

**Residual Findings**

- 実カメラの構図と自動背景分離の品質は実験で確認する。失敗を成功と記録しない。

**Coverage Notes**

- ゴール要求分析・対応サブゴール・DoD・検証・エラー対処・トレーサビリティ: adequate。
- 原子性: package取込、各機能境界、実行検査に分割。無意味な定数写しのテストは追加しない。

**Open Questions**

- なし。外部D435は実在確認済み。必要な構図調整は実際のframeを見て説明する。

**Recommended Patch Scope**

- 上記補足を反映済み。手順1から進める。

## 完了時の再照合（2026-10-04、Codex単独）

**Verdict:** PASS_WITH_NOTES。独立エージェントによるレビューではない。

- 添付の数値核・尺度・FKの再現をstatic-replayとnative14試験で照合。
- sourceのmetric/K境界、raw maskと登録用mask、freshness、内部候補と公開poseを照合。
- 最終ライブは60秒で1012成功/16.87Hz、publication age p95 0.114秒。
  HTTP99回のage p95 0.157秒。初期化を定常fpsと混同せず、失敗時間を含む集計CLIで確認。
- D15に基づく実機段階観察と、修正後20°追従・復帰・全5台OFF・RAM復元を記録から照合。
  画像の推定をmotor goalには使っていない。新しい安定referenceは各runの実SDK読み取りで確認。
- ソフトは入力/領域/登録/描画/状態の境界を維持。FK・モーターcontrollerをコピーせず再利用。
  root344件の初回後は影響試験だけ。最終空mask/欠損depth/再取得、viewer試験が成功。
  ruff/ty/複雑度10、技能形式検査成功。motor exchange契約は未変更。
- 記録とHTMLの要求対応を照合。最終HTMLの全30画像読込み・横overflowなしをPlaywrightで確認。

残る制約: カメラ/台座固定と、開いた姿勢の画像由来初期値を使った測定条件での完了。
完全な折り畳み画像からの初回探索、絶対実角度、65/75°の現物区別、全可動域の干渉は未保証。
RGB/depthは同じSDK framesetのalignで、完全同時露光の証明ではない。
これらを性能保証・実機校正・製造承認としては使わない。
