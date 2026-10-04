# Source/SDK audit notes

- 保守対象16Python filesの取得/型/レジスタ/schema/CLI/bridge/ID3送信監視releaseを精読。SDKはlocked versionと実体に基づいて扱う。root viewerは手順4で追加監査する。
- ユーザーの22:37:49構造化回答をclean tool_outputで確認: 肘から肩は固定・重力で倒れ込まない、停止手段は電源OUTPUT OFF、方向はviewer2点、当初ID3だけ校正。22:38:19 encoder-only変更、23:33以降autonomy/就寝が後続。
- 公式一次資料: https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#secondaryshadow-id12 （同Secondary IDのRAM命令への複数応答、253以上で無効）。
- read_settingsはID3のみのsettingsを読んでおり、他IDのsecondary_idが3かを検査しない。トルクOFFの他IDでもID3 writeへ応答する構成を防げない。実機の過去secondary設定は別途保存recordで確認、実際の今回runで発生したとの主張はしない。
- CAD loaderはsourceファイルSHAの一致とrecord内sign二か所の一致だけ。CADを再解析・導出しない。folded_read.logも存在/hash/schemaを照合しない。反例probeを手順3へ。
- return stageのTrackerはsettle_limit=25、Outcome statusはopen error<=5だけで決まる。return_error=20でもsuccessとなる可能性。hold/followはID3 Torque ON維持を検査しない。
- release問題をOutcomeへ列挙するがexit_codeはrelease_problemsを見ず、settings復元失敗でもexit0の可能性。
- 仕様の無人/POWER OFF条件と汎用skillの推奨が矛盾。既往のuser自治指示と今後の一般条件を混同しない。
- 保存実測はmotion-log-audit.jsonで独立計算。motion2の110count=9.66796875°、開目標誤差-4count、他軸<=1count、終了TorqueOFF/port_closedと一致。past successは上記未検出境界の否定ではない。

