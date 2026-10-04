# D405付き待機姿勢・D435 RGB-D撮影

2026-10-04、Codex単独実行。ユーザーの指示：現折り畳みをカメラ付きneutral、
そのRGB-D/カメラパラメータ保存、20unique姿勢生成・実撮影、commit & push。
start-work-with-docs/bounded-servo-motion/git-commit-pushを使用。

開始18:27:23、基準実count[2102,3473,1147,3398,1951]、全OFFで安定。
外部D435 serial922612070196、SDK RGB/Depth/左右IRすべて1280x720@30fps、
USB3.2/FW5.17.3.10を観測。align/JPEGの実処理は約19.43Hzで、30Hz達成とは記載しない。
D405は長尺ホルダーに取付済み、USB未接続。名目D405外形と2本ねじをFKモデルへ追加、
29mesh/199occurrences/4DoF、実URDF→MuJoCo/FK・bounds5姿勢照合成功。

18:31:02から実機撮影開始。旧PhotoController/SDKguard/健康監視/停止を再利用し、
新runの小さいwindowとfresh referenceだけを専用クラスで選択。PV6/PA1/PWM350維持。
18:32:58に手首-5°がdeadline未達停止、全5現在count保持・port閉鎖。
失敗元表/原画像/eventsは残し、再試行や制限拡大をせず台座5方向×肘4段階へ変更。
元設定/保持goalをfresh READで照合し、torque再enableなしで再開した。
18:37:31に20unique取得完了。毎回2.5秒静止→RGB-D保存→実画像確認→次指令。

18:38:02に新neutralへ復帰、全5OFFとPWM885/PV0/PA0の復元を読戻し、終了0。
18:38:41の独立3sampleも全OFF/error0/速度0、34〜37℃、9.0〜9.1V、
counts[2112〜2113,3473,1153,3392,1951]で安定。電源装置OUTPUTはPCから操作していない。
開始/終了neutralと20姿勢、原寸PNG・uint16深度・カメラintrinsics/extrinsics/scale、
撮影前後の実telemetry・別時刻・SHAを保存。hardware同期/絶対CAD校正は未確定。
固定焦点で輪郭は見えるが低照度ノイズが残る。見えない接触の全域認証ではない。

必要最小限SDK offline検証20件PASS（既存18+newneutral/guard2）、対象lint PASS、
diff --check PASS。PlaywrightでHTML22組/44画像decode確認、画面PNG保存。
controller/支持解除をsrcへ移し、temp依存のテストをpackage importへ変更した。
スキルlessonsへ新neutral/取付後の制約/画質/fps区別/SDK単一所有を追記。

データ正本：~/data/xl430-arm/2026-10-04/d405-mounted-rgbd-1827/。
Gitコピー：diary/2026-10-04/d405-mounted-rgbd/。
モデル関連source/docs/仕様/URDF/MJCF/OBJはdiary/2026-10-04/current-arm-model/。
元gripperはPUBLICなので現物写真/記録を公開せず、既存PRIVATE sandboxへ保存する。
元gripper working treeのuntrackedファイルはそのまま残す。公開側へのpushは行わない。
2本の既存大容量動画は今回のGit保存対象に含めず、ローカルに保持する。
push結果は完了後に作業書へ追記する。
