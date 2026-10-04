**Verdict:** PASS_WITH_NOTES

**Mode:** review-and-fix、Codex単独自己レビュー

**Findings**
- Major：写真の掲載順では角度pairが確定しない。原本を再視認し、ユーザーが181.41閉/239.50開を明示確認。初期断定を撤回。
- Major：near stationaryをfar stallと混同していた。actual/error/statusを記録して区別し、40°の未達は未達として保持。
- Major：撮影の古いreadyを新goalに誤用し得た。latest write後のready、velocity0、actualからのdrift<=12を要求。
- Minor：mobileで長いhash文字列がoverflow。折返しを修正し390幅で再確認。
- Minor：camera移動後に旧ROIを使っていた。新視点のROI統計を無効化。旧seedも再利用しない。

**Applied Changes**
- 別ID5-only RAM controller、fresh全5identity/alias/OFF、transport拒否、有限profile、監視付きhold、OFF検証前restore禁止。
- 最小6件の異なる回帰。既存116件との初回確認を再利用し、後半は影響箇所だけ検証。
- 状態別の二眼RGB/Z16/IR/K/歪み/時刻とfailed runsを保全。日誌・仕様・技能へ同じ制約を反映。

**Residual Findings**
- 全機械範囲、把持力、絶対位相、65/75°holderの現物区別は未検証。
- 閉2091は2067から24count残差。観測開2486は40°goalではない。精密goal達成とはしない。
- 消灯後D435はtip上端crop/ノイズ。モニタ反射でD405黒部品が暗い。撮影前5状態が開閉の根拠。
- 全staged diffにはimmutable vendor/results/STEP空白が残り、保守対象だけPASS。原本hash保全を優先し無断正規化しない。

**Coverage Notes**
- SG/TR、single writer、相対角とクランク角namespace、停止/OFF/RAM復元、保存実体と未検証範囲は具体化済み。
- 保存/pushの最終一致だけは手順7の実結果でチェックする。未実行のpublishを本レビューで成功にしない。

**Open Questions**
- このDoDの完了に新たなユーザー回答は不要。

**Recommended Patch Scope**
- PRIVATE mainへ関連記録・コードを保存、push後remote HEADを確認して完了記録を追記。
