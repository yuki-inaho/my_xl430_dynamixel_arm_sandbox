# Onshape アーム＋PG3＋D405 作業成果

## 追加: 250 g条件の短縮候補とheadless操作

2026-09-26の比較候補は [設計レポート](optimization-250g/REPORT.md)、[画面付きマニュアル](optimization-250g/MANUAL.html)、[PDF](optimization-250g/MANUAL.pdf)、[headless・キャッシュ手順](optimization-250g/HEADLESS.md)、[逐次作業書](optimization-250g/WORKDOC.md) を参照。高さ−9.49 mm・カメラ周辺手首負荷振幅−6.8%と、質量＋0.18 g・手首片側4°減のトレードオフを記録した。最新版は [短縮候補のURDFと使い方](optimization-250g/robot/README.md)。新可動V2から12メッシュを再取得し、11姿勢のOnshape/FK一致と441点閉リンクを検証済み。以下の旧URDF・旧ZIPは元R5用として保持している。


2026-09-26。Onshape Freeの公開ドキュメントを2件作成し、元STEPの取り込みからリンク・関節定義、ネイティブ検証、URDF出力まで実施。

## 人間向け操作マニュアル

[スクリーンショット付きHTML版](manual/MANUAL.html)（画像クリックで拡大）／[PDF版・25ページ](manual/MANUAL.pdf)／[編集用Markdown](manual/MANUAL.md)。取り込みから再作成・URDF出力まで、操作位置・入力値・正常時の結果を順に記載。

## 開く

- [初回の公開モデル](https://cad.onshape.com/documents/1f8f316ef4f488303d1c1902/w/ac6b81ffda999cf35e941d15/e/282c9739d5fb8e5aa9a89f3f)
- [独立に作り直した公開モデル](https://cad.onshape.com/documents/531556789fcbb8dfdcac2689/w/f18636c9c4ee7993d5afbbaa/e/a0b147c03da145430a3c0bf1)
- [再作成モデルの検証済み固定Version](https://cad.onshape.com/documents/531556789fcbb8dfdcac2689/v/64249f2de6a8cce71fff923f/e/a0b147c03da145430a3c0bf1)
- [作業記録・Findings/Tips](WORKLOG.md)、[検証機能の使い方](VALIDATION_GUIDE.md)
- `robot/robot.urdf` は初回、`rebuild/robot/robot.urdf` は再作成からの出力。各フォルダのassetsと一緒に使用する。

「0から」は新規ドキュメントへ同じ元STEPを再アップロードして組み立て直す意味で実施。全形状をスケッチから描き直したものではない。

## 結果

|項目|結果|
|---|---|
|入力|D405 R5統合STEP、257 occurrence → 262 body（207 solids / 55 sheets）|
|剛体|12 closed composite links|
|Onshape Mate|13個、全てOK。11ツリー接続＋左右2閉ループ|
|URDF|16 links / 15 joints。形状リンク12＋閉ループ補助フレーム4。駆動5、受動4、固定6|
|Native Animate|両ドキュメントでCurrent valueの変化と機構動作を確認|
|Native Interference|全開・中間・全閉で各6件。ねじ取付部に対応する組合せ|
|URDF閉ループ|各出力を441角度で検査。最大位置残差 約0.23 µm|
|独立再作成比較|リンク/関節トポロジー一致、12メッシュの双方向最近傍頂点距離0、面積・三角形数一致。回転行列の差は書出し丸めの範囲|
|Free枠|有料機能・購入なし。Developer画面の確認時点で年間API 361 / 2,500回|

詳細な数値は `native-validation.json`、`robot/validation.json`、`rebuild/comparison.json`。原本SHAは `source-manifest.json`。

## 使う

```bash
python3 robot/pg3_states.py 25     # 全開、開口約48.90 mm
python3 robot/pg3_states.py 90     # 中間、開口約15.99 mm
python3 robot/pg3_states.py 135    # 全閉側、開口約0.93 mm
```

URDFのグリッパは木構造なので、`pg3_states.py`が返す5つのグリッパ関節値を同時に与える。driveだけを動かすと閉ループは維持されない。一般的なURDFの線形mimicではこの非線形関係を表現できない。

検証を再実行する場合は numpy / trimesh があるPythonで `python3 robot/validate_robot.py`。このPCでは元グリッパプロジェクトの `.venv/bin/python` で実行済み。ROS環境での実行試験は行っていない。メッシュ参照はURDFからの相対パスにしたポータブル版であり、ROS package URLが必要な場合は実際のパッケージ名へ変更する。

`robot.onshape-raw.urdf` がonshape-to-robot 1.8.3の未加工出力。利用版では参照パスを修正し、ゼロ質量・ゼロ慣性要素、固定関節に不要なlimit、補助link直下のoriginを除去した。原本は保持している。

## 適用範囲

これは運動学・可視化モデル。材料密度、質量、慣性、実機ホーム、トルク/速度制限は未確定。effort/velocityの0は未設定を明示するプレースホルダで、運転許可値ではない。J1〜3の±πはexporterの既定値。J4の範囲は既存CADの2°刻み干渉診断に基づく暫定値。

M01〜M04のメーカー形状は可動ホーンを独立分割しておらず、モーター一式を親側の粗い表示形状として保持。カメラlinkは取付物の剛体で、校正済み光学フレームではない。STLにはシート由来形状も含み、シミュレータ用の単純な衝突形状として検証したものではない。

6件の干渉は、同一入力SHAの既存レポートにある4本のタッピング取付部＋2本のD405背面ねじと整合する。ねじの実強度を確認したものではない。今回の検査はcomposite間の3姿勢で、composite内部や全アーム連続可動域を網羅しない。

## スキルと再現

`onshape-robot-workflow/` はインストール済みスキルの配布コピー。`$onshape-robot-workflow` で呼び出せる。初回で得たAPI制限値・軸・Reset・干渉解釈を記録し、2件目の再作成を通じて更新した。

`reproduce/` に今回使ったリンク分割・関節作成・姿勢指定のスクリプトを収録。鍵は含めない。読取・書込専用のタスク用APIキーを作成し、ローカルwork内の保護ファイルに保存して使用した。原本リポジトリは変更していない。

出典・権利表記は `robot/NOTICE.md` と `robot/licenses/`。取り込みやメッシュ化によって元形状のライセンスを置き換えるものではない。
