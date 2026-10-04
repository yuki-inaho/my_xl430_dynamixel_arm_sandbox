# Onshape作業と作業書運用のスキル

ユーザー指示により、ローカルスキルだけでなく設計リポジトリ直下の `skills/` へ本体と参照ファイルを保存した。出典はユーザーの `skills`。今回追記したOnshapeの知見と、作業書運用に使った3スキルを一緒に追跡する。

- [onshape-robot-workflow](onshape-robot-workflow/SKILL.md)：今回更新。APIを節約するUI操作、パッド誤所属の検出、版/姿勢STEPの違い、Pixi/OCCT検証、手順書とGit保存の教訓。
- [write-workdoc-uv](write-workdoc-uv/SKILL.md)：日本語作業書の構造とテンプレート。元CAD側はuv。今回の変換器側では明示的なユーザー指定のPixiを優先し、作業書に環境を分離して記載した。
- [review-written-workdoc](review-written-workdoc/SKILL.md)：自己完結性・実行性・DoD・証跡をreview-rubricで確認する。
- [start-work-with-docs](start-work-with-docs/SKILL.md)：date、1項目ずつの開始/完了、即時記録、DoDを逐次実行する。

`onshape-workflow-snapshot.json` は13ソースファイルの出典とSHA256。本体だけではなくreferencesとagents設定も含む。既存の `cad-reverse-parametric` など他スキルを置換しない。利用者は必要なスキルのSKILL.mdと参照文書を読み、ユーザーの現在の要求を優先する。認証、browser profile、APIキーは含まない。
