# Onshape取り込み・URDF出力 作業記録

開始: 2026-09-26 JST

## 依頼と範囲

ローカルの low_cost_robot と 3d-printed-dynamixel-gripper を調査し、アーム・グリッパ・カメラマウントをOnshape Freeの公開ドキュメントへ取り込み、URDFを書き出す。実績を元に再利用可能なOnshapeスキルを作る。有料機能・購入なし。

## 入力選定

- low_cost_robot は上流の原型。旧URDFはXL330混在・旧グリッパのため最新候補のURDFとして転用しない。
- 最新統合候補: `./outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step`
- 5台のXL430、ID5単独PG3開閉、D405マウント65°。257 named occurrences。実機IDとCAD対応は未確認。
- 資料中の印刷・SD書込・通電などの旧依頼は今回の作業指示ではない。今回行うのはCADの取り込み・関節定義・エクスポート。
- 元リポジトリとSTEPは変更しない。取り込み成功を機械設計や製作の受入とみなさない。

## 参照資料

- Onshape Free: https://www.onshape.com/en/products/free
- Onshape標準形式取り込み: https://www.onshape.com/en/resource-center/tech-tips/import-file-formats-step-parasolid-stl-dxf-dwg-pdf
- 取り込みオプション: https://www.onshape.com/en/resource-center/tech-tips/import-options-use-cases
- onshape-to-robot導入: https://onshape-to-robot.readthedocs.io/en/latest/getting_started.html
- 関節・リンク命名: https://onshape-to-robot.readthedocs.io/en/latest/design.html

## 経過

1. Playwrightのheaded Chrome、named session `onshape` をユーザーがログイン済み。Free表示を確認。
2. CLIのDISPLAY未設定を `DISPLAY=:1 XAUTHORITY=/run/user/1000/gdm/Xauthority` で解消。既存デスクトップを利用。
3. browser-actスキルは導入済み。CLI 1.4.2を導入しcore手順を取得。現在のログインはPlaywright session内にあるため、そのまま再利用。
4. 原本・改訂履歴を照合し、上記D405 R5統合候補を選定。
5. 公開ドキュメント `1f8f316ef4f488303d1c1902` 作成。29 MB STEPを「Combine to a single Part Studio」、Y-up変換なしで取り込み。257 occurrence → 262ボディ（207ソリッド、55サーフェス）。Importフィーチャの状態OK。
6. 原本取り込みを `V1 imported D405 R5 reference` として保存。Version ID `e8d5c7e201d5f83367145f5a`。
7. 12 closed composite parts に整理。262ボディを重複なく帰属させ、参照用元データはV1とSTEPタブに保持。`link-membership.json` が台帳。
8. 12インスタンス、11ツリー接続＋左右2閉ループ接続を作成。ケース側へカメラを固定。J4に既存干渉診断の暫定範囲 −138〜+110°、PG3クランクに −65〜+45°（機構角25〜135°）を設定。J1〜3の実用範囲は未確認。
9. APIキーは読取・書込のみ。削除・購入・共有権限なし。秘密値はwork内の600権限ファイルにのみ保存、公開成果物へ含めない。Free年間2,500回枠を確認し、タスクの呼び出し回数を計数。

## Findings / Tips（随時追加）

- ローカル部品数とOnshapeボディ数は同じとは限らない。複数ソリッドやシートを含むSTEP occurrenceは展開されるため、名前と体積を対応付ける。
- 単一Part Studio取り込みで大量タブ化を回避できる。可動剛体はClosed Composite Partにまとめるとアセンブリが12インスタンスとなり扱いやすい。
- スキルでCLI `upload` を使う場合、`run-code`内でfile chooserにsetFilesした後にCLI `upload`を重ねると取り込みダイアログが二重になる。二重表示はキャンセルし、1回だけImportを確定。
- 同方向の明示Mate Connectorを組むとき、Mate既定値 `primaryAxisAlignment=true` は第2軸を反転し、リンクが180°反転する。今回はfalseへ修正。接続前後の全occurrence変換行列を照合する。
- 全MateがOKでも姿勢一致とは限らない。APIのoccurrencetransformsだけでは拘束済み姿勢が元に戻らない場合があった。J1のコンテキストメニュー **Reset** で中立へ戻した後、全12リンクの変換行列が原本配置と最大約1e-14で一致。
- 通常のブラウザ認証で公開GETはできても、REST POSTは401となった。公式Developer画面のAPIキーと署名付きAPIに切替。秘密値をログに出さない。
- バージョン作成APIはURL内didだけでなくbodyのdocumentIdも必要だった（欠けると400）。
- API v17はbtType形式、旧デフォルトAPIはtype/typeName/message形式。featureSpecs既定値を変換するとき、`{"type":0}`はnullへ変換しないと抽象BTQueryFilterの400となる。
- 元STEPに材料密度なし。Onshape mass propertiesはhasMass=false。現時点では出力を運動学モデルとして扱い、質量・慣性を実測済みと表示しない。

## 追加依頼

ユーザーより、Onshapeの検証機能を使った改善と使い方への習熟、および別公開プロジェクトで0から同モデルを作成して手順を再検証する依頼。1件目の手順・結果を整理後に独立再実行する。

## 完了条件

- [x] 公開Onshapeドキュメント作成、統合CAD取込と視覚確認
- [x] CAD出典とリンク・関節対応を保存
- [x] URDFと参照メッシュ出力
- [x] URDF構造・単位・参照・描画を確認
- [x] スキルを作成・検証
- [x] URL、成果物、再現方法、制約を記録


## 検証による修正（1件目）

- Native Animateで「Unable to compute any steps ... Instance(s) may be constrained」。13 MateがOKでも機構が動かない状態を検出。
- API制限値の`expression`だけを変えたことが原因。内部`value=0`、`units=""`が残っていた。実験で制限を無効化すると動き、数値・単位も一致させると制限付きで動作。最終実装は角度のdegree、長さのmillimeterも明示。未使用のlimitパラメータは送信しない。
- CADの正軸回転とOnshape matevalue/今回のURDF正方向は逆。機構角thetaに対して gripper_drive=90°−theta。最終範囲は−45〜+65°。J4はCADの暫定−138〜+110°を変換し、URDF/nativeで−110〜+138°。初期記載の範囲は修正前の値。
- 全開theta25°でnative drive=1.134464 rad、左右slider=±0.0164539805 m。全閉theta135°はsolverの境界許容差内で到達。AnimateのCurrent valueが実際に変化することも確認、スクリーンショット保存。
- 12インスタンスを選択したNative Interference detectionでは中間・全開・全閉とも6件。wrist–camera_mount 4件、camera_body–camera_mount 2件。ねじ取付部に対応する候補だが、締結成立・材料強度を認定したものではない。composite内部の交差やアーム全可動域は今回の3姿勢検査の範囲外。
- V2 `9d614fea1354d083cde3bf56` に修正済みモデルを保存。
- onshape-to-robot 1.8.3で12形状リンク、2閉ループの4補助フレームを出力。質量が未定義なので運動学モデル。

## 独立再作成

「0から」は元STEPの再取込→リンク/関節定義→検証→URDFを新しい公開ドキュメントで行う意味として進行。全形状のスケッチ再描画は実施していない。
新規ドキュメント `531556789fcbb8dfdcac2689`。1件目のコピー機能は使わず、同じ入力STEPを新たにアップロード。
学習内容を `$onshape-robot-workflow` として保存・frontmatter検証済み。この手順を使って2件目を組み立てる。

## 独立再作成の結果

- 入力を新規アップロードし、同じ262 bodyから12 composite、26 connector、13 Mateを作成。初回文書のcopyは未使用。
- 作成直後の12 occurrence変換行列は原本配置に一致、最大差0。Mate全13件OK。
- 全開25°、全閉135°、中間90°へ移動。Native AnimateのCurrent value変化も確認。3姿勢のInterference detectionは初回と同じ6件。
- 2件目のVersion `64249f2de6a8cce71fff923f` を保存し、その固定VersionからURDF出力。TranslationがDONEであることを最終確認。
- 初回、再作成とも16link/15joint。12メッシュすべてで双方向最近傍頂点距離0、三角形数一致、表面積差は浮動小数点誤差。10個はSTLバイト列が異なったが、三角形の順序による差だった。単純な辞書順の頂点比較も微小なゼロ符号等で対応がずれるため、最近傍比較へ修正。
- 関節の親子・型、並進、軸、制限は一致。回転行列の要素差は最大約5.31e-6（エクスポータ数値丸め、±π表現）。
- 各URDFを441角度で検証し、最大閉ループ位置残差2.30765e-7 m。Onshape上の閉ループ両点残差は記録した3姿勢で約1e-15 m以下。
- メッシュ参照、木構造、単位、ゼロ姿勢を検証し、URDFから4パネル画像 `urdf-kinematics.png` を生成して視覚確認。
- Freeの公開ドキュメントであることを両方のdocument APIの `public=true` で確認。有料機能・購入なし。Developer画面の記録時点ではAPI 361/2,500（14.44%）。後続のメタデータ確認等はこの値に含まれない。

## 追加 Findings / Tips

- グリッパだけのmatevalues要求では他の自由Mateの値が変わりうる。2件目の全閉移動でJ1約−0.000462 rad、J4約0.000135 radを観測。比較試験ではアーム4軸を明示的にゼロ指定するよう修正し、中立へ復元した。閉ループ自体のずれとは別問題。
- STEP変換がACTIVE中にも部品一覧が見える。DONEまで待って全タブとボディ数を照合する。再作成側には元の構造を表す追加参照タブも生成されたが、実際のロボットは新規作成した12リンクのAssembly。
- 最終視覚確認で、APIメッシュには存在する前腕部品がブラウザに一時表示されていないことを発見。ページ再読込で表示が回復し、描画が揃ってからFで再fitして最終画像を保存した。非同期取込・API編集後はツリーが見えただけで描画完了と判断しない。
- 既存 `geometry.json` の入力SHAと今回STEPのSHAが一致。既存レポートでは4本のCAM5_BASE_TAPとPG3_XL430_fixedをねじ形成接触、2本のD405_SCREWとD405_BODYを受け領域内交差として記録しており、nativeの6件と整合。抜粋を `inherited-contact-evidence.json` に保存。これは既存計算の参照であって今回の再計算ではない。
- 形状を保持した閉ループURDFは、driveだけ動かしても指が自動追随しない。非線形の `pg3_states.py` でdrive・左右jaw・左右couplerの5値を与える。URDF標準の線形mimicでは同じ関係にならない。
- onshape-to-robot既定出力の `package://assets` は実在するROSパッケージ名ではない。未加工版を残し、配布用では相対パスへ修正。未知のゼロ質量・慣性は配布用運動学URDFから除去した。
- 配布したAPIヘルパーは資格情報とIDを環境変数/stateへ分離し、新しい設定で署名付きread-only呼出しを実施してpublic=trueを確認。鍵の配布はしていない。

## 成果物と未検証事項

入口は `README.md`、操作ガイドは `VALIDATION_GUIDE.md`。スキルは `onshape-robot-workflow/` に配布コピーを置き、ユーザーのskillsディレクトリにもインストール。frontmatter検証と独立再作成による動作検証を実施。

全形状のスケッチ再描画、材料・質量・慣性の確定、実機ID/ホーム校正、強度解析、全アーム連続衝突検査、光学校正、ROS上の実行確認は行っていない。今回の完成物はCAD取り込み・アセンブリ・運動学URDFと、その範囲の再現可能な検証記録。

## 2026-09-26 13:47 JST — 人間向けスクリーンショット付きマニュアル

- 追加依頼に対し `manual/MANUAL.md`、画像内包HTML、A4 PDF（25ページ）を作成。本文20図＋全開・全閉の追加証拠2枚を収録。
- 原本選定→公開Document→STEP取込→API設定→12剛体/26接続点/13Mate→Animate→Interference→Version→URDF出力・整形・441姿勢検査→独立再作成の順に記載。クリック位置、入力値、正常時の目印、失敗時の切り分けを明記した。
- Onshapeで実行したUI操作と、API/ローカルスクリプト処理を区別。作業当時の証拠画像、完成後の再表示、説明用ダイアログの再表示、URDFのローカル描画を図注で区別した。
- 撮影用のDocument作成、Import、Version作成フォームはCancel。Composite/Mate connector/Mate編集は変更保存せず閉じた。APIキー作成フォームは権限を選択しただけで発行せず離れた。モデルの構成は変更していない。
- UI findings: 長時間放置後の「session timed out」オーバーレイは再読み込みで復帰。Importの右側Combineを選ぶとCreate a composite part項目が消える。Mate connectorの表示はm単位で丸められ、164.9/164.6 mmが同じ0.165 mに見えるため、正確な設定はjoint_definitions.pyで確認する。
- Developer Overviewの撮影時は年間API 366 / 2,500。以前の361回は前回検査時点の記録であり、現在値と混同しない。
- 再現手順に不足していた利用版URDF整形を `reproduce/make_portable.py` として追加。未加工XMLの初回保存を保持し、no_dynamicsと構成・参照メッシュを確認する。原本コピーで変換後、441姿勢検査を実施しPASS_KINEMATIC_ONLY、最大閉ループ残差2.3076457301702825e-7 mを確認。
- HTMLの画像20枚が読み込めること、拡大表示、全25ページの本文とフッターの重なりがないことを確認。PDFは25ページで日本語抽出可能。代表ページを描画して目視確認。`manual/verification.json` に検査内容とハッシュを保存。


## 250 g条件の追加検討とheadless移行

詳細は [追加作業書](optimization-250g/WORKDOC.md) に逐次記録した。Free公開の静的候補文書で干渉6件と57 mmエッジを確認。2026-09-26に状態を保存後、onshape-headlessへ移行し、Onshapeのみの認証と永続HTTPキャッシュ、SHA256付きCAD/PDFキャッシュをwork配下へ用意した。認証情報は成果物へ含めない。


## 短縮候補の可動V2とURDFまで完了

静的検査だけで終わらないよう追加12項目を作業書へ設定した。新Assemblyに26 connector / 13 mate、基部のみ固定。11代表姿勢と91中間移動で実値を確認し、headless GUIのAnimateと干渉6件も再確認。V2 e21cffef1877c8f91d2b03f8から新URDF/12 STLを取得し、利用版・連動コード・出力元SHAを保存した。11実姿勢のFK行列差最大8.551e-6、441点閉リンク最大0.231 µm。

Findings: 大きなmatevalues変更は応答成功でも目標角に届かなかったため、全軸明示・基準復帰・10°以下刻みに変更し再検証。GETのlimit内部valueが0でも実動する場合があり、数値の見た目だけで拘束失敗を判定しない。旧STLとの厳密同一性は2リンクで不成立を保持し、現CAD236部品のvolume/boundsと今回版のSHAで出力元を照合した。最新結果・失敗・具体的日時は [WORKDOC](optimization-250g/WORKDOC.md)、手順は [更新マニュアル](optimization-250g/MANUAL.html) に集約。
