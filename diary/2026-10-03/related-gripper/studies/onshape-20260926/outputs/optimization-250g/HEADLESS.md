# Headless操作とキャッシュの再開手順

2026-09-26、作業書へ移行前の状態を保存してから、専用セッション `onshape-headless` に切り替えた。CLIの `headed: false` とブラウザの `--headless`、ログイン済み文書・12インスタンスの描画を確認済み。

![Headlessで取得したOnshapeの実画面](images/onshape-06-headless.png)

## 現在の状態

- 公開文書: [250 g Compact D405](https://cad.onshape.com/documents/7b85d8922959cbe564b6e0cb/w/caa6accdf3e72dd480cecc37/e/848ae15cd82797bd99cdc330)
- 現在は `Compact D405 - Motion and URDF`。基部のみ固定、13 mate OK、可動11姿勢を検証してV2/URDFを保存済み。12部品固定の静的V1も保持。
- 移行前は干渉6件確認・計測未完だった。移行後57 mmエッジ計測、さらに可動組立のAnimate/干渉まで完了した。経過は [WORKDOC](WORKDOC.md) を正本の閲覧用コピーとする。
- 元のウィンドウ付きセッション `onshape` は、別用途のタブもあるため残した。自動操作は以後 `onshape-headless` を使う。

## 起動・再接続

以下はこのPC用の実行例。作業ディレクトリを `studies/onshape-20260926/work` にして実行する。

```bash
rtk proxy npx --yes @playwright/cli list
rtk proxy npx --yes @playwright/cli -s=onshape-headless snapshot
```

セッションが閉じている場合だけ再起動する。既存プロファイルを同時に2つのブラウザで開かない。

```bash
rtk proxy npx --yes @playwright/cli -s=onshape-headless open about:blank --profile=studies/onshape-20260926/work/cache/onshape/profile --config=studies/onshape-20260926/work/cache/onshape/headless.config.json --idle-timeout=0
rtk proxy npx --yes @playwright/cli -s=onshape-headless goto https://cad.onshape.com/documents/7b85d8922959cbe564b6e0cb/w/caa6accdf3e72dd480cecc37/e/848ae15cd82797bd99cdc330
```

プロファイルの認証が失われ、保存済みセッションがまだ有効なら、次の操作後に `goto` をやり直す。`state-load` は保存時の状態を上書きするため、通常の起動では不要。期限切れならログインをやり直す。

```bash
rtk proxy npx --yes @playwright/cli -s=onshape-headless state-load studies/onshape-20260926/work/cache/onshape/private/onshape.auth-state.json
```

終了する場合は、このセッションだけを指定する。`close-all` は使用しない。

```bash
rtk proxy npx --yes @playwright/cli -s=onshape-headless close
```

## キャッシュ

基点は `work/cache/`。

| 保存先 | 内容・運用 |
|---|---|
| `onshape/profile/` | Cookie、ローカルストレージ、HTTPキャッシュの永続プロファイル。ディレクトリ権限700。初回確認でHTTPキャッシュ約15 MB。 |
| `onshape/private/onshape.auth-state.json` | Onshapeドメインだけに絞った認証状態。ファイル権限600、親700。Google等の状態は移行対象外。 |
| `onshape/headless.config.json` | Chrome、headless=true、画面1600×1000。 |
| `cad/<SHA256>.step` | 検証候補STEPの内容ハッシュ付きコピー。内容が変わったら別キーで保存。 |
| `cad/<SHA256>.pdf` | 取得済み公式D400データシートのローカルコピー。 |
| `manifest.json` | CAD/PDFの元パス・SHA256・サイズ。再利用時はハッシュ照合。 |

認証・ブラウザプロファイル・公式PDFキャッシュは成果物フォルダや公開ZIPへ含めない。初回3D描画とスクリーンショットには時間がかかったが、実際のモデルを保存できた。待機中のコマンドは終了コードを確認してから次の操作へ進む。

HTTPキャッシュはブラウザが管理する。検証結果JSONは対象STEPのSHAが一致する場合のみ参照でき、形状変更後の検証を省略する理由にはしない。
