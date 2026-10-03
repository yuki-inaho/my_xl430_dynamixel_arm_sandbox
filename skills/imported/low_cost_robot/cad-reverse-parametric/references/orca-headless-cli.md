# OrcaSlicerヘッドレスCLIスライス（システムプリセットの解決）

OrcaSlicerのGUIはプリセットの`inherits`を解決するが、CLIの`--load-settings`/`--load-filaments`は解決しない。展開済みシステムプリセット（例: `~/.config/OrcaSlicer/system/Creality/machine/Creality Ender-3 Pro 0.4 nozzle.json`）をそのまま渡すと、継承キーがC++デフォルトに落ちて検証に失敗するか、意図と違う設定でスライスされる。

2026-09-22、OrcaSlicer 2.4.2のCLIで実際に確認した挙動:

| 症状 | 原因 | 対策 |
|---|---|---|
| `file ...'s from  unsupported` で即終了 | `from`（`system`/`User`/`user`）がない | メタ情報`type`/`name`/`from`を残す |
| exit -51 `Add "G92 E0" to layer_gcode.` | 継承チェーン未解決で`before_layer_change_gcode`が空（`use_relative_e_distances`はデフォルトtrue） | 継承を展開し、基底が持つ`G92 E0`を含める |
| exit -17 `selected printer is not compatible with the process preset` | プロセスの`compatible_printers`が空 | プロセスの`compatible_printers`を残す（例: `["Creality Ender-3 Pro 0.4 nozzle"]`） |

解決自体は`cadre.orca_presets`（stdlibのみ）で行う。`inherits`を基底→葉の順にマージし、CLIが要求するメタ情報と`compatible_printers`を残しつつ、`inherits`/`setting_id`/`*_condition`等のプリセット管理キーを落としたフラットJSONを出力する。

## 手順

```bash
# 1. 継承を展開したフラットJSONを作る
uv run python -m cadre.orca_presets \
  "$HOME/.config/OrcaSlicer/system/Creality/machine/Creality Ender-3 Pro 0.4 nozzle.json" \
  "$HOME/.config/OrcaSlicer/system/Creality/process/0.20mm Standard @Creality Ender3 Pro 0.4.json" \
  "$HOME/.config/OrcaSlicer/system/OrcaFilamentLibrary/filament/Generic PLA @System.json" \
  --out-dir /tmp/orca-profiles

# 2. GUIを開かずスライス（offscreenで十分。xvfb-runは不要）
#    出力名は元プリセット名のまま（下記例ではCreality Ender-3 Pro 0.4 nozzle.json等）
timeout 240 env QT_QPA_PLATFORM=offscreen "$HOME/Applications/OrcaSlicer.AppImage" \
  --load-settings "/tmp/orca-profiles/Creality Ender-3 Pro 0.4 nozzle.json;/tmp/orca-profiles/0.20mm Standard @Creality Ender3 Pro 0.4.json" \
  --load-filaments "/tmp/orca-profiles/Generic PLA @System.json" \
  --arrange 1 --ensure-on-bed --slice 0 --outputdir /tmp/slice_out \
  ring.stl

# 3. 必ずresult.jsonとgcodeを検査する
#    result.json: return_code=0 かつ error_string=Success.
#    OUT/plate_N.gcode が生成されている
```

`--load-settings`は`"machine.json;process.json"`の順、`--load-filaments`は別引数である。`--arrange 1`を付けないとベッド外配置になることがある。

## Ender-3 Pro（stock Marlin）の注意

- K1C運用の`START_PRINT`/`END_PRINT`検査は使えない。stock Marlinの開始/終了G-codeは`G28`/`M104`/`M140`/`M109`/`M190`等なので、温度・`G92 E0`・レイヤー数を確認する
- `M191`（チャンバー待ち）と`M600`（フィラメント交換）が出ていないことを確認する
- SDカードへはASCIIの短いファイル名で保存する（stockファームウェアの表示都合。例: `ring_test.gcode`）
- コピー後に`sha256sum`で書き込み一致を確認してからsync/取り外しする
- SDカードのマウント先は`/media/$USER/<ボリュームラベル>`。旧G-codeや`EEPROM.DAT`を消さない

## 実例（2026-09-22）

薄い中抜き円（外径40/穴20/厚さ2mm）をEnder-3 Pro / 0.20mm Standard / Generic PLAで10層、`ring_test.gcode`としてスライスし、SDカードへsha256一致でコピーした。