# Onshape作業の保存点（2026-09-26）

**取り込み注記:** 本文は元作業の履歴。今回のテキスト写しは個人の絶対パスを除去した。
元manifestは原本用として保持し、取り込み版は
[`verify_d405_intake.py`](../../../../../../3d-printed-dynamixel-gripper/scripts/verify_d405_intake.py) で照合する。
アカウント表示を含むUI画像とHTML/PDF/ZIPはローカル保持・Git対象外。
現在の候補と再現結果は [取り込みレビュー](../../docs/D405_LOW_PROFILE_INTAKE.md) を参照。

ユーザー指示「一旦commit & push」に基づき、爪延長・低位置カメラの再設計に入る前の成果を保存した。

- [最新版の短縮D405可動モデルとURDF](outputs/optimization-250g/robot/README.md)
- [設計比較レポート](outputs/optimization-250g/REPORT.md)
- [スクリーンショット付き操作マニュアル](outputs/optimization-250g/MANUAL.md) / [PDF](outputs/optimization-250g/MANUAL.pdf)
- [作業書と完了監査](outputs/optimization-250g/WORKDOC.md)
- [初回・独立再作成の成果物一覧](outputs/README.md)

この保存点は俯角75°の候補C_y185_z250_p75である。「最良」は当時の既存爪形状・中央40°以上の探索内での選定を指し、参考Robonineの30°や爪延長を含む全体最適を証明していない。新しいユーザー指示は爪延長も許可しており、その再設計は本保存点以降に別作業書で扱う。

## 保存範囲

outputsはユーザー向け成果物。workのPythonは実行時のコード、motion/onshapeのJSONは非秘密のAPI観測証跡。元CADリポジトリのコードや参照形状は上書きしていない。SNAPSHOT-MANIFEST.jsonに全保存ファイルのSHA256を記録した。APIキー、Cookie、ブラウザプロファイル、HTTPキャッシュ、ダウンロードしたメーカーPDF、bytecodeは収録しない。

この作業は元々Git外の独立ディレクトリで行われたため、スクリプトには当時の絶対パスと作業ディレクトリ構造が残る。読み取り専用の検証はnumpy/trimesh環境で `outputs/optimization-250g/robot/validate_robot.py` を実行できる。CAD再生成には本リポジトリのuv環境とPYTHONPATHが必要。Onshape更新には自分の認証設定と新規文書stateが必要であり、記録済みの公開版IDへ再度書き込まない。

旧robot bundle ZIPは旧R5用。最終短縮候補はoptimization-250g/robotであり、取り違えない。250g連続運転、実機耐久性、材料・造形・ホーム校正は未確認の運動学モデルである。

GitではSTEP/STLを生成CADデータとしてbinary扱いにし、原文ライセンスと旧マニュアルの末尾空行だけを個別に許容した。CADや原文のSHAを変える空白除去はせず、他の文書・コードは通常のgit diff --check対象とする。
