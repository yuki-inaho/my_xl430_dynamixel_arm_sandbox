# 同梱物の出所

新規の関節付き処理・カメラ・注釈・描画・試験・記録は、この依頼で作成したコードです。以下の第三者条件を上書きする一括ライセンスは付していません。

`third_party/acpd_cpp/` はユーザー添付の `acpd_filterreg_rs-main/cpp/` から再使用しています。格子処理はPhilipp Krähenbühl由来のBSD-3-Clause移植です。元の `THIRD_PARTY_NOTICES.md` と `LICENSES/` を未変更で同梱しています。Eigenは添付の未変更ヘッダーで、`COPYING.*` と個別表記を保持し、`EIGEN_MPL2_ONLY` でコンパイルしています。

`model/source_arm_XL430_R3.step`、R3関節・manifest・派生メッシュの元資料はユーザー添付 `3d-printed-dynamixel-gripper-main/references/arm-r3/` です。同梱されていたAlexander Koch氏のMIT表記を `model/source_LICENSE` に保存しています。`source_NOT_MANUFACTURING_APPROVED.txt` も必ず参照してください。画像位置合わせの成功は製造・強度・可動範囲の承認ではありません。

元FilterRegの関節付きソースは読んで式・符号・集約方法を照合しましたが、ライセンスの不明確な原プロジェクト全体は再配布していません。新しいC++集約処理は論文の式から独立した境界で実装しています。新規コードと借用コードの区別はディレクトリで保持しています。

画像・深度から得た観測配列は、この会話で提供されたものから作成しました。ユーザー添付の大きなZIP群、私的な日誌、未使用の他プロジェクト、学習済み重み、フォントファイルは同梱していません。PNG内の文字描画に使用したフォント本体も同梱していません。
