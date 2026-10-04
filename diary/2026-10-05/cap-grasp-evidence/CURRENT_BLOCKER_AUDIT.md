# キャップ把持の未達・現在の停止条件

2026-10-05 03:24:17 JST+0900開始。旧照明BLOCKED_AUDITは歴史記録であり、本監査とは別です。

**キャップを掴んでいません。元姿勢に戻れず、脱力していません。全5軸トルクONで保持しています。**

## 現在状態と3ターンの確認

- 1ターン目：ID2復帰がPWM350で停滞。一度の395試行でも実測2852付近で止まり、350へ復元。`return-output395-once/events.jsonl` に失敗と5park/出力復元がある。支持未確認のためOFFを行わず、記録・画像・会話を保存してpush。
- 2ターン目：実プロセスと新しいREAD frameで保持を確認、03:00の二眼でもcapは箱上。支持後解除に必要なcontroller/profile/windowと停止log tailの不整合を修正。SDK確認と03:15:39の実機READ-only照合は成功したが、支持は未確認のまま。
- 3ターン目（現在）：親PID783803のcmdlineとage0.291sの03:24:18 READを確認。03:25:03二眼でもcapは箱上、D405には指先と机。撮影前後READは同じ `[1518,2841,1139,3372,2091]`、全ON/velocity0/error0。37..48℃、9.0..9.2V。重さを預ける支持や支持完了の回答は得られていない。

解除用コードの準備は済み、実際の持上げ・帰路・脱力へ進める独立のソフト修正は残っていません。READ-only監視の生存は確認しましたが、それは重力支持や安全な解除を提供しません。同じ失敗方向の再試行・更なる出力増加を行いません。原因が接触/配線/荷重/駆動部のどれかは未診断で、ソフトの出力上限だけから断定しません。

## 要求と証拠の照合

|要求|権威ある実体証拠|判定|
|---|---|---|
|fresh対象/アーム/二眼RGB-D|`final-blocker-audit-0324/{d435,d405}`、captures.json、watch-bracket.json。生/整列depth、IR、metadata、calibrationを保存。|対象キャップと現在姿勢の観測あり。暗所ノイズあり。絶対CAD校正/支持は未確定。|
|把持/持上げ/退避までの具体的実行可能経路|WORKDOCのD19段階、cap_grasp_stages.py、各実機JSONL。ID2の復帰と手首候補が停滞。|**未達**。局所的な動作記録を全経路の衝突/荷重承認へ置換しない。|
|限定制御・停止/解除準備|scoped controller、SDK拒否/往復/解除の試験、supported-release-readonly-preflight。|準備は検証済み。現物支持の確認前に解除を実行していない。|
|capを実際に挟み、支持面から離して保持|最新D435ではcapは箱上、D405ではcap保持を認めない。持上げ/保持記録なし。|**未達**。現在画像は把持成功に反する。|
|置戻し/安定支持姿勢復帰/脱力/設定復元|最後の失敗log、CURRENT_STATEとfresh全ON READ。|**未達**。過去の小probe復帰OFFを現在の終了証拠に使わない。電源装置OFFも未確認。|
|実画像・深度・params・HTML/作業書/技能・会話保存|diaryと~/dataの撮影実体、REPORT.html、WORKDOC、lessons、clean export manifest/parts。|未達過程を保存済み。要求全体の完了ではない。会話cutoffはmanifestを参照。|
|全DoDの達成|WORKDOC §6は全項目未チェック。|**未達**。goal completeを設定しない。|

## 再開条件と次の操作

1. 現物の腕・D405・グリッパの重さを手または受け台で支え、現在姿勢を大きく変えず「支えた」実状態を確認する。台座だけの固定は腕の重力支持と同一ではない。支持前に電源を切らない。
2. 現在のREAD-only serial所有者を実プロセスで確認し、その所有者だけを終了。D19 `scripts/cap_supported_release.py` に最新の `return-output395-once/events.jsonl` を渡し、fresh identity/alias/profile/raw goals/driftを照合する。
3. 実際の支持確認後だけ `--support-confirmed --execute` で全OFFを確認してからpark/RAM復元。通常photo CLIではD19 jaw310/window/tailを扱えない。帰路再試行/ON/395試行はこの解除の範囲外。
4. 支持解除後にID2の現物接触・ケーブル・駆動部・荷重を確認し、障害を除去してから、cap把持経路をfresh写真/READで設計し直す。目的は依然として実capの把持・分離・保持証憑と安全な終了。

READ-only watchは03:17:26開始/900秒で03:32頃に終了予定。終了してもモーターのトルクをOFFにしません。カメラownerは撮像用でモーターを制御しません。電源装置はPCから操作できません。

03:36:41 JST+0900監査追記：watchのterminal endと親process不在を確認。1771frames/900s、1.968Hz、deadline miss29、incomplete0、port_closed=true。最後の03:32:27.800 READでも全5ON/velocity0/error0、counts=[1518,2841,1139,3372,2091]、37..48℃。実JSONLをfinal-blocker-audit-0324へ保存。トルクOFF/電源OFFではありません。最新会話snapshotは03:28:55 JSTまでを119/119 coverageで保存し、8part連結/解凍のSHA256一致と圧縮前秘密検査を確認しています。以後の保存/push/goal状態更新はsnapshot外です。
