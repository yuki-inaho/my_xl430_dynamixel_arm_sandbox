# Playwright優先・API使用記録

ユーザー追加指示: Onshapeはできるだけ通常UIをPlaywrightで操作し、API limitを節約する。2026-09-26 17:23 JSTから本方針を適用。

2026-09-26追加明確化: **直接APIゼロが第一目標**。下表のAPI例外は自動的な利用許可や必要性の結論ではない。UI機能なし、UI方法未確認、操作煩雑、UI+ローカル処理で代替可の4分類で確認する。既存exporterを使うだけの理由ではAPIへ移行しない。

## 開始状態

- 直接RESTクライアント `work/onshape_api.py` のカウンタ `work/api-count.txt` は **526**。これはこの作業場でそのクライアントを使った試行数であり、アカウント全体の年次使用数ではない。過去のexporter等、別経路は含まない。カウンタをリセットしない。
- 今回の低配置研究から本記録作成まで直接REST呼び出し **0**。ローカルCAD/VTK探索はOnshapeへ通信しない。
- Playwright named session `onshape-headless` を再利用。専用configは `work/cache/onshape/headless.config.json`、Chrome headless=true、1600×1000。profile `work/cache/onshape/profile`、認証state `work/cache/onshape/private/` は秘密情報として成果物/Gitから除外。
- tab0は既存Compact D405 Motion and URDF、tab1はローカル日本語マニュアル。既存Onshape版/別ブラウザセッションを保持する。現在のambient in-app signin表示と、この専用ログイン状態は別。
- 既存のschema・joint定義・版情報は `work/optimization/motion/` などにキャッシュ済み。新ドキュメントのIDを旧IDで代用しない。

## 限度の根拠

[Onshape公式API Limits](https://onshape-public.github.io/docs/auth/limits/)を2026-09-26に確認。Freeは年2,500 calls/user。API keyによる2xx/3xx呼び出しが算入され、通常のOnshapeブラウザからの呼び出しは年次API枠へ算入されない。エンドポイントごとのレート制限は別。ローカルカウンタ526を「年次残り1,974」と解釈しない。正確な年次使用数はMy Account > DeveloperでUI確認する。

## 操作規約

DOM取得→役割/名前/親領域で対象を一意に確認→通常UI操作→成功表示/部品数/関節名を照合→保存/再表示で確認、の順とする。古いe番号を再利用しない。クリックできたことだけで成功判定しない。画像はユーザー向け手順の証拠に利用する。

直接APIの代わりにpage.evaluate(fetch(...))等で内部エンドポイントを呼び出す方法は採用しない。UI操作に伴う通信と、RESTを直接呼ぶスクリプトを区別する。APIが必要な例外は下表に根拠と件数を記録し、同じversionへの読取りをキャッシュする。

## 実行記録

## UI操作経路と例外条件

|処理|第一選択の通常UI経路|成功確認|直接APIの例外条件|
|---|---|---|---|
|新public文書|Documents > Create > Document|文書名/URL/public設定|UIの再取得と限定再試行でも不可能な障害を記録した場合のみ|
|STEP取込|タブ追加メニュー > Import > ローカルファイル選択|翻訳完了、Part Studioの部品/面数|同上。処理中のAPI pollはしない|
|剛体群|Part StudioのComposite part、名前を確認して選択|12群に全ボディが一度ずつ含まれる|必要ならUIからFeature Studioへ再現可能なCADコードを入力する。内部REST直接呼出しはしない|
|Assembly/mate|タブ追加 > Assembly > Insert、Mate connector/Fastened/Revolute等の通常ダイアログ|固定基部、13mateの状態、関節名/軸/リミット|UI経路を試した結果と必要処理を記録して限定利用|
|角度/干渉|Mate編集/Animate、Analysis > Interference detection、Measure|実表示角、閉路、対象選択範囲、干渉結果|正確なpose行列がUIから取得できない場合の少数の読取だけ。中間姿勢はUIで動かす|
|Version|Versions and history > Create version|固有版名、version URL、保存状態|原則不要|
|URDF|最終版からUIでSTEP/STLを出力しローカルでURDFを構築する方法を先に検証|最終版一致、12新STL、関節/pose照合|UI+ローカルの代替経路を検証した後、なお取得できないデータがある場合に限り、必要endpointと最少件数を明記する|

APIを使う前にキャッシュの入力version/config一致を確認する。exporterのキャッシュは別文書/別版へ流用しない。必要な例外の際は、直接呼出しを記録するフックを付けて集計する。認証ヘッダ、cookie、secretはログに記録しない。

## 「画面から実行できない」の判定台帳

|処理|現時点の分類|APIを使わない代替|確定に必要な確認|
|CAD作成/取込/mate/干渉/角度/version|通常UIの機能あり|Playwrightで各ダイアログ操作|今回の画面で成功と保存を確認|
|直接URDF形式で保存|標準UIに機能あり。Free画面から実ZIP取得済み|Assemblyタブ > Export > URDF。指定のSTEP→Pixi変換も実行する|19links/18joints/261visuals。PG3_horn_bolt_1参照欠落、collision要素0、閉路/dynamics未検証。比較用として保持|
|native assemblyの正確な全part変換取得|UI+ローカルSTEP解析で取得可能。11姿勢の262部品を解析済み|各姿勢をMainで適用しUI STEP保存、XCAF配置解析|左右パッドの逆所属をUI修復し全11件を再出力。132剛体行列の内部差0、URDF FK照合PASS。versionの一時的な表示姿勢はexportへ反映されなかった|
|schema/part ID一覧|今回の作業で必須とは未確定|名前と実体CADで対応し、既存schemaを再利用|内部ID取得を目的化しない|
|API年次残量|My Account > DeveloperにUIあり|画面の数値を読む|ローカルカウンタとは別の値であることを記録|

現時点で「直接APIでしか実施できない」と確定した項目は **なし**。代替を試す前に例外件数を計上しない。

2026-09-26の再調査: [公式Exporting Files](https://cad.onshape.com/help/Content/File/exporting_files.htm)はAssemblyのURDF出力を記載しており、実際のFree/public文書のExportダイアログでもURDFを選択できた（`images/onshape-urdf-ui-option.png`）。標準UIの形式がないという前提は採用しない。STL/GLTF/GLB/OBJのGeometry formatと解像度を選べる。直接APIなしでの標準URDFも比較用に取得し、ユーザー指定のurdf_from_step整備を省略しない。

構築経路の確認: [公式Document Menu](https://cad.onshape.com/help/Content/Document/document_menu.htm)のCopy workspaceは別文書へ独立コピーを作成する。[公式Imported CAD](https://cad.onshape.com/help/Content/Document/working_with_imported_cad.htm)のImport feature > Updateは取込元の変更をPart Studioへ反映する。これをUIから実行し、12剛体/mateを再検証する。公式は取込Assembly自体のUpdate未対応も明記しているため、既存の独自native assemblyへ部品更新が伝わることを実表示と出力で検証する。参照切れをAPIで隠さない。

ユーザー指定により、最終URDF経路は **Onshape UI STEP export → yuki-inaho/urdf_from_step（Pixi、最新安定OCCT）→ ローカル検証** とする。標準UIにURDF項目がなくても直接APIを必要としない方針。変換器の整備を後半手順6とDoD D7へ追加済み。

## 実行記録（追記）

|段階|経路|直接API件数|結果|
|---|---|---:|---|
|追加指示までの低配置研究|ローカルCAD/VTK|0|探索継続中|
|開始状態確認|Playwright tab-list、config/counterのローカル読取り|0|既存専用headlessを確認|
|復帰テスト|Playwrightでalert内reconnectリンクをクリック|0|timeout表示消失、base_link一意、12instance/13mateのCAD画面維持|
|独立コピー|Document menu > Copy workspace > Create public document|0|29e8557c76e89bcf64f50566を作成。旧文書を保持|
|STEP更新|Part Studio > Import 1右クリック > Update > ファイル選択|0|新STEPのimport完了通知。カメラ11部品の所属外れを通常UIで修復。未所属Parts 0、Composite 12|
|関節修正|Part Studioのcamera connector編集、Assemblyのwrist Limits編集|0|camera Y165/Z235mm、wrist [-102,124]degを保存後の再読取で確認|
|姿勢/動作確認|Named positionsの5駆動列、mate context Animate|0|11姿勢適用、肩0→10と手首0→124のAnimate終点確認|
|版保存/中立STEP|Create version、Assembly Export AP242/mm/None|0|V1 4577cc931e9bc290e2b31032。262parts/207solid/55sheet、部品名/配置保持|
|標準URDF|Assembly Export URDF/STL Binary/Fine|0|ZIP実取得。比較用、内容の制約はEXPORT.md|
|姿勢STEPと所属診断|MainでNamed positions適用→Assembly Export|0|11件取得。能動軸最大誤差3.058e-6deg、ただし左右padの逆所属を部品行列で検出。V1証拠を保持し修復後に再出力|

更新時の注意: 取込成功の通知だけでは下流のcompositeが全ボディを含むとは限らない。今回、保持形状の対応は残ったが、大きく移動したカメラ部品は未所属になった。Parts欄の残存数と各グループの内容を確認する必要がある。

さらにParts 0 / Composite 12だけでも十分ではなかった。形が同じ左右パッドの旧参照が逆側へ対応し、中立では見分けられないまま、開閉時に逆のjawへ追従していた。UI STEP内の全構成部品の行列を比較して発見した。旧union選択を解除し、左右それぞれ12部品を名前で選び直して修復する。左側だけを直す途中には右側旧unionの重複エラーが現れるので、両方を完了し再出力するまで成功扱いにしない。

自動操作の失敗記録: 非同期run-codeの完了前に次の編集を開いた結果、後続クリックが別グループの選択へ混在した。復旧は通常UIの選択解除・再選択で行う。以後、ブラウザを変更するコマンドは前のexec sessionが終了するまで開始しない。各クリック前に `.ns-dialog-title` のtrimした文字列が目的の編集名と一致することを確認し、クリック後に選択項目が現れたことを待つ。正規表現でdialog全体のraw textに完全一致を要求すると周辺空白でtimeoutになるため、タイトル文字列をtrimして検査する。

姿勢指定のUI経路: [公式Named positions](https://cad.onshape.com/help/Content/Assembly/named_positions.htm)に従い、右端Named positions > Add named position > 駆動mateを選択 > Driving mate selectorのZ回転をチェックすると角度列が作れる。5つの能動関節を登録し、表の値を編集して名前セルを右クリック > Apply named positionで全5値を指定する。最初のcaptureでは過去の操作によるyaw=-27.711°が残っていたため、原点を推測せず全5値0の行を作った。

表の入力にはセル全体 `.os-td` のクリック/ダブルクリックを使う。非編集時のinputだけをクリックするとセルの保護レイヤーが遮る。行の `data-id` はDOMからその都度取得し、旧文書のIDを流用しない。名前/角度の保存、適用通知、モデルの動き、STEP実配置の数値検証は別の証拠として扱う。

今回の失敗と復旧: 肩10°の一括適用で `Mates could not be solved` が出た。1°ずつの中間姿勢は全て適用できた。一方、行名の保存直後に角度を編集すると旧角度へ戻る競合も発生したため、各編集・適用後の安定待ちと保存値再読取を追加した。既に現在姿勢と等しい行はcontext menuにApplyが出ない場合がある。メニュー不存在だけでsolver失敗とは判定しない。

AnimateではCurrent valueが終点10°へ到達したが、閉じると0°へ戻った。終点表示を保存姿勢の証拠として流用しない。101 stepsはこのheadless環境では数分かかり、30秒timeout中にも3.465→6.733→10°と進んでいた。時間切れだけで機構不動と判断せず、Current valueの変化とエラー表示を確認した。

姿勢出力の落とし穴: 読取り専用versionでもNamed positionsのApplyは使えるが、今回のSTEP exportは版に保存された中立姿勢を出した。yaw10表示のファイルとzeroはSTEP DATA全体が同一だった。Mainへ戻って適用・出力するとyawの回転行列が得られた。画面の成功/ファイルの存在/実配置を三段階で区別する。

復帰前 `headless-start.png`、復帰後 `headless-reconnected.png` を実画面で確認。最初にメッセージ全体をクリックしても復帰しなかった。DOMからリンク `a.osx-message-bubble-link` を特定し、正確なテキストで一意性を検証してクリックすると復帰した。「クリック成功」と「接続復帰成功」は別の確認が必要。APIカウンタは526のまま。

## 最終集計

低配置スタディの直接API呼出し **0件**。例外 **なし**、内部fetch/REST代用 **なし**、onshape-to-robot実行 **なし**。旧カウンタは開始526、終了確認も526。UI+ローカル処理で、独立public文書、import更新、Composite修復、mate/limits、11姿勢、Animate/Interference、V2保存、STEP/参考URDF出力まで実施できた。

V2 `f6162b4adc88af9d07f1194a` のSTEPをローカルのurdf_from_step/Pixi/OCCT8.0.1へ渡し、441閉路と11native姿勢の比較まで完了。Onshapeサーバーを照会せず、保存STEP・joint定義・画像・SHA付きレポートを再利用した。ダウンロードキャッシュは誤出力名修復にも使い、元のMain zero STEPをSHA照合して復元した。認証profile/stateは成果物とGitに含めない。アカウント全体の年次残量は取得しておらず、526から推算しない。

UIで実行できないと確定したCAD工程は今回なし。数千候補の光線評価、差分BRep検査、非線形閉路の数値回帰、今回の明示設定によるURDF生成はローカル処理で実施した。Freeの画面内に同等の一括処理があることは確認していないが、それをAPI必須という意味にはしない。材料/疲労/摩擦/実機性能の確認はAPIでも代替できない。
