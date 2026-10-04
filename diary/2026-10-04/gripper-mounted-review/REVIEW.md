# 装着グリッパの開閉・二眼撮影レビュー

Codex単独、2026-10-04。実機開→閉、状態別RGB-D、終了OFF/RAM復元を確認。
証拠は[HTML](REPORT.html)、[独立集計](motion-summary.json)、[仕様](../../../docs/GRIPPER_ID5_CONSTRAINTS.md)。
他IDへのWRITEなし、全runの最大他軸変化1count、独立最終READでは1〜2countの差でガード15内。
最終全5台OFF、error0、ID5 2091 stable。電源装置の物理OUTPUT OFFは操作していない。

初回150・再試行250のPWM飽和/停滞は失敗として保持した。写真の掲載順だけから
符号を確定した初稿は撤回。ユーザーの181.41°閉/239.50°開の明示確認と、提供写真の
PWM35.03%を根拠に別run310で開を観測。摩擦原因を解明したとはしていない。
20°指令は2281（14count残差）、40°指令は2487（35count残差）で停止。
観測開2486の画像に隙間、再閉2091に指サック接触を視認した。
閉基準2067への24count残差を消していない。実際の開閉がDoDで、全域/精密角/力は未検証。

near静止とfar stallを分離し、実countと残差をreadyへ記録。softtipでの追加押込みは禁止。
保持はaccepted actualからのdriftを監視。未準備/古いreadyの撮影を拒否する回帰を追加。
新テスト6件、共通ID3との初回116件PASS。後続は変わった6件だけ再実行。
保守コードとnative SDK環境を分けてRuff/tyを確認した。新規大規模テストは追加していない。

5実状態×2眼と2停止状態、ユーザー微調整後の現在状態を別viewとして保存。
RGB/Z16/IR/K/歪み/depthscale/前後host観測を保持。逐次撮影でhardware同期ではない。
カメラ調整後のフレームを旧seed/外部camera poseに自動対応させない。
D435暗所ノイズ・D405逆光、矩形ROIの背景混在と近距離欠損は制約として残す。
元SDKパラメータを落とさず、ROIを距離校正や把持幅と扱わない。

提供ZIPのCRC、96manifest entries、6STEP valid solids、STL/GLB座標/単位を独立確認。
元fitの4点残差はin-sample。softtipは中実占有モデルで機構・中空・弾性ではない。
現在のR3+D405 perceptionモデルにjawはなく、今回のjaw認識や全域干渉検証には使えない。
65/75°holder、厳密な印刷版、絶対ゼロ/クランク位相は未確定。

Playwrightで33画像decode、リンク200、1280×900と390×844のoverflowなしを確認。
初回mobileは長いhash文字列がはみ出したため折返しを修正。元データ再撮影はしていない。
写真・ZIP・失敗試行は保存し、表示と生成脚本を同じ記録から再生成できる形とした。

23:52の配信停止時、元camera ownerはSIGINTをnative処理で受けD435 exit130、
D405 exit134（free(): corrupted unsorted chunks）となった。保存済み記録は保全。
SIGINT/SIGTERMを終了要求だけにし、現在frame完了後HTTP/pipelineを終了する方式へ修正。
D405だけの有限camera-only再確認はframe15取得後、SIGTERMでexit0、stderr空。
これは1回の停止回帰であり、native library全race解消の証明ではない。motorにはアクセスしていない。
