# 低位置D405・爪延長スタディ

**今回の取り込み:** [レビュー・Pixi/OCCT 8再実行](../../docs/D405_LOW_PROFILE_INTAKE.md)。
固定lockからwheelを再ビルド・再変換し、保存V2との全バイト一致を確認した。
個人パスを除いたテキストと新しいSHA一覧は `integration/` を参照。
以下の「今回」は受領した各記録の実行時点を指す。

**引き継ぎ継続:** [検証器改善・実STEP再検証](revalidation/README.md)。
旧D6/D7を保存証跡として監査し、52試験と独立STEP再読込を追加した。
CAD/URDF形状は未変更。以下の35試験は前回の記録であり、今回の52件と混同しない。
`revalidation/` を保存範囲に追加した。元の327件一覧は同ディレクトリのINPUT-SNAPSHOT-MANIFESTに保持する。

2026-09-26、俯角30°、爪+20 mm、D405ガラス中心(-0.2,165,235) mmを選定。旧75°候補に比べカメラ高さは12.40 mm低い一方、250 gとカメラ等の部分モーメントは9.45%増える。V2から新規URDFを生成し、441閉路と11native姿勢を検証した。実物の耐久性・材料・造形・校正は未確認。

- [20ページ操作マニュアルPDF](outputs/low-profile-250g/MANUAL.pdf) / [画像拡大可能なHTML](outputs/low-profile-250g/MANUAL.html) / [設計比較レポート](outputs/low-profile-250g/REPORT.md)。
- [最終URDFと再現方法](outputs/low-profile-250g/robot/README.md)、[作業書](outputs/low-profile-250g/WORKDOC.md)、[保存情報](outputs/low-profile-250g/DELIVERY.md)。
- [公開Onshape V2](https://cad.onshape.com/documents/29e8557c76e89bcf64f50566/v/f6162b4adc88af9d07f1194a/e/d5415bf725ba822741b01703)：左右パッドの所属を修正した版。
- [設計選定](outputs/low-profile-250g/SELECTION.md)、[UI検証](outputs/low-profile-250g/NATIVE-VALIDATION.md)、[出力記録](outputs/low-profile-250g/EXPORT.md)。
- [変換器](https://github.com/yuki-inaho/urdf_from_step/tree/codex/pixi-occt8)：commit `1b2cea3`、Pixi + OCCT 8.0.1、13回帰試験PASS。新モデルのFK/負対照4件とCAD18件を合わせ35試験PASS。
- [リポジトリ直下skills/の4スキル](../../skills/ONSHAPE-WORKFLOW.md)：Onshapeの実証知見、write/review/startと全参照ファイルを保存。

`CAD/final-version.step` が修正版V2の入力。`diagnostics/v1-pad-misassigned` は負の証拠として保存した旧失敗例であり、製作用データではない。標準UI URDF ZIPも旧V1の参考出力である。

保存範囲は `outputs/low-profile-250g` と `work/low-profile` のみ。SHA256は `SNAPSHOT-MANIFEST.json`。秘密情報の既知パターンをZIP内も含め検査し、ブラウザプロファイル、認証状態、HTTPキャッシュ、bytecodeは含めない。スクリプトは当時のディレクトリ構造と元リポジトリのuv環境に依存するため、コピーだけで全操作を再実行できる独立パッケージとはしていない。UI更新スクリプトを公開保存版へ無条件に再実行しない。
