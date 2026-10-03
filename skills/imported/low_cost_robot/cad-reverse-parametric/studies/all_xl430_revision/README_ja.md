# 全6関節XL430静止組立 study

2026-09-19に受領した`low_cost_robot_all_XL430_CAD_20260919.zip`を、リポジトリの元STEPから再生成・再検証するstudyです。

受領物は、混在サーボ構成の形状改訂を基準に、元の4台のXL330サブアセンブリを、元STEP内にあるXL430サブアセンブリ形状へ剛体置換していました。本studyは固定された`/mnt/data/...`への依存と要素番号範囲による削除を廃止し、SHA-256で保護された元STEPとアセンブリパスから再生成します。

## 現在の判定

**未承認です。印刷・製造用に使用しません。**

- 6台のXL430構成と217末端要素への再構成は再現できた。
- 流用された7部品のSTEP/STLは、単一ソリッド・閉じたメッシュとして有効。
- 旧`current`は外部部品間の体積干渉54件。2026-09-22のJ4配置補正候補は46件であり、いずれも未承認（下記）。最大約9,608.8 mm³のJ3/J5ケース間干渉は残存する。
- 同一モーター参照形状の内部重複168件は別集計であり、外部干渉には含めない。
- 受領ZIPの干渉レポートは置換前の混在サーボ基準モデルに対するもので、全XL430置換後の組立検査ではない。
- 受領ZIPに「72穴軸」を裏付ける全XL430置換後の測定レポートはない。収録されているのは混在版の5締結パターン・18軸の検査結果である。

生成STEPは`outputs/all_xl430_revision/unaccepted/<run-id>/`へ隔離し、`accepted/`へ昇格しません。`source/study.py print-package`と`prepare_print_package.py`は、保存済みレポートを信用せず検証を毎回再実行し、外部干渉や未実施の工学検証が残る限り終了コード2で停止して印刷物を生成しません。

## 再生成と確認

```bash
cd skills/cad-reverse-parametric
rtk uv run python studies/all_xl430_revision/source/study.py rebuild --run-id review-run-001
rtk uv run python studies/all_xl430_revision/source/study.py validate --run-id review-run-001
rtk uv run python studies/all_xl430_revision/source/study.py print-package \
  --run-id review-run-001 --output /tmp/all_xl430_print.zip
rtk uv run pytest -q studies/all_xl430_revision/source/test_all_xl430.py
```

- `rebuild`は生成と検証を別プロセスで実行し、候補を`outputs/all_xl430_revision/unaccepted/<run-id>/`にだけ書き出す。
- run-idは未使用名を指定する。既存runを上書きしない。
- B-repスキャンは151ソリッドの全11,325組をbboxで評価し、候補をboolean検査する。旧381候補/約11分、J4補正版376候補/144.295秒。実行時間は形状・環境に依存し、タイムアウトも印刷を止める側に倒れる。
- `print-package`は毎回`validate`をやり直してから判定する。現在は終了コード2で停止する。
- 検証記録は各runの`reports/`の`validation.json`、`collisions.json`、`external_collision_pairs.csv`に残る。旧`current`の証跡を新runへ流用しない。

## J4配置バグの補正（2026-09-22）

J4（変換スクリプト内の識別子であり実機IDではない）は延長リンクの上流固定端にあるが、
全XL430変換時に下流側の並進(0.25, 9.65215945946, 0.532578228165) mmを誤って加えていた。
元idler円筒軸と置換idler円筒軸の径方向ずれは9.666841 mm。他の3交換モーターの軸は一致した。
J4のみ移動指定を削除し、35部品をまとめて正しい位置へ戻した。リンク・穴・supplier形状は変更しない。

- 実CADテスト: 修正前はJ4の軸/全leaf配置の2件がRED、修正後は既存を含め67 passed。
- 新run: `outputs/all_xl430_revision/unaccepted/j4-datum-20260922/`。
- 新STEP SHA-256: `4b0ecfd89411f11285ce7611f0b914bb7bc07515da7daff3f4460cfca9d7dee3`。
- 新完全走査: 217leaf、151solid、376boolean、errors=0、外部46、supplier内部168、CLI exit2（未承認）。
- 旧54件との差分: **11件解消、43件残存、3件新規**。単に8件を修復したという意味ではない。
- 新規はJ4のヘッダー/小部品と肩・延長リンクの干渉。肩リンクとJ4bodyは1306.545→2827.856 mm³へ増加。
- 再importの4idler実軸は元mixed baseline軸と一致（径方向残差最大6.70e-12 mm）。座面位置・ボルトパターン・締結成立の証明ではない。
- 全217leafの補正後bbox/面積/体積/面種/edge数を照合。これは書出し指標検査で、任意のB-rep同等性の完全証明とは区別する。

J4配置修正は残る大型モーターとリンクの寸法不整合を直さない。
肩支持候補・配線概念の別検査は旧`current`のSHAに紐づくため、新runの工程/配線検証として扱わない。
詳細: repoの`docs/all_xl430_assembly_wiring_review.md`。

## 次に必要なCAD作業

1. 各XL430の取付基準面・軸・ねじスタックを定義する。
2. 7部品のうち、XL430外形と衝突するブラケット、リンク、グリッパーを局所変更する。
3. 全XL430置換後に穴軸と締結を再測定し、基準姿勢の物理干渉を0件にする。
4. 離散姿勢だけでなく、関節間を補間した連続経路で掃引干渉を検査する。
5. その後に初めてOrcaSlicer用パッケージを生成する。

メッシュが印刷可能であること、モーター数が6台であること、静止STEPが開けることは、全XL430アームとして組み立て可能であることの証明ではありません。
