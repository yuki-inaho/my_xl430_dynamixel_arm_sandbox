# 関節付きFilterRegと本実装の位置づけ

## 読んだ一次資料
Wei Gao and Russ Tedrake, **FilterReg: Robust and Efficient Probabilistic Point-Set Registration using Gaussian Filter and Twist Parameterization**, CVPR 2019. arXiv:1811.10136, https://arxiv.org/pdf/1811.10136 。本文§3–5、式6/7/12/20、Algorithm 1を確認しました。原添付コード `kinematic/articulated/articulated_point2point_cpu.cpp` および `articulated_twist2joint.cpp` と照合しました。原実装のarticulatedは旧Drake依存で、添付READMEでも既定ビルド対象外です。ここではFKと関節Jacobianを独立実装します。原コードをそのまま現行nanobindに包んだものではありません。

## E段階
固定観測Yが混合Gaussianの中心で、動くCAD点Xを問い合わせます。CPDの標準的な固定/移動の解釈と取り違えません。

M0_i=Σ_j exp(-||x_i-y_j||²/(2σ²))、M1_i=Σ_j exp(…)*y_j、μ_i=M1_i/M0_i。外れ値重みは α_i=M0_i/(M0_i+c)、c=(2πσ²)^(3/2)・w/(1-w)・N/M と定義します。本コードのkernelは正規化定数を含まないためc側へ移しています。M0=0の点は重み0とします。近傍1点に置換するICPとは異なります。

添付 `acpd_filterreg_rs-main/cpp` の検証済みではない入力コードから、BSD系permutohedral格子実装を出所付きで再使用します。固定観測のsplatを再利用するno-blur経路と、厳密Gaussian総和の対照経路を別名で用意します。格子はGaussianの近似であり厳密値と一致するとは主張しません。試験では定数再現・有限性・局所平均・正規方程式などを分けて検証します。

## M段階と関節構造
左作用する空間twist ξ=(ω,v) に対し δp=ω×p+v。点JacobianはA=[-skew(p),I]です。各リンク内でH_b=Σ α AᵀA、g_b=Σ α Aᵀ(μ-p)を集約し、関節空間へH=Σ S_bᵀH_bS_b、g=Σ S_bᵀg_bと写像します。これが原論文Algorithm 1の中心部分です。符号は原C++の残差xの行(0,z,-y,1,0,0)とも一致します。

追加する一様尺度sはCAD部品を個別に変形するものではなく、X=s R FK(q)+tというカメラ座標へのsimilarityです。log(s)で正を保証します。7列のA=[-skew(p),I,p]に拡張し、尺度列のSの並進成分を-tとしてδp=(p-t)δlog(s)を実現します。全体姿勢6自由度、一様尺度1、観測形状を動かすJ1–J4の4自由度を推定します。J5は末端未装着で下流の可視形状が無く、この画像から求めた値を出しません。

## 今回の観測への追加
単一視点の可視表面だけを対象とし、CAD自身の奥行き判定と外部遮蔽注釈を扱います。背景、ケーブル、台座手前の布、黄色テープはCADの形状と区別します。手動の特徴点と輪郭を初期化・正則化・比較に使います。これらは画像補助付き拡張であり、元論文そのままの純粋な点群目的関数とは明確に区別します。Gaussianデータ項を実行せず単に画像だけを合わせてFilterRegと呼ぶことはしません。

## 座標と意味
STEPはmmを一回だけ1000で割りmにします。保存STEPは中立形状が既に組立姿勢にあるため、joints.jsonのzero_rotationを再度掛けません。関節中心・軸の情報で保存姿勢からの変位を構成し、派生URDFを独立に書き出します。旧URDFの寸法をR3へ流用しません。

EXRのOpenCV読取り順はBGRなのでpoints.exrのチャンネルを反転してx/y/zへ戻します。PLYはOpenGL風のy上/z後なのでdiag(1,-1,-1)が必要です。EXR固有Kは約fx=fy=695.2165ですが、主試行では指定画角51/30度のKを使ってdepthから再投影します。深度は単眼推定の任意単位です。推定尺度によるm換算はCAD寸法・画像モデルに依存し、D405実測精度、カメラ校正、エンコーダ校正の代わりになりません。

## 出所と実行上の制約
補助コード・Eigenのライセンスをthird_partyに保持します。新規処理はC++数値核、PythonのFK/カメラ/最適化/描画/評価に分けます。nanobind境界と標準uvビルドを提供しますが、今回の実行環境ではnanobindの取得が通信エラーとなっています。C ABIの別経路を実行してもnanobindのビルド確認の代替とは扱いません。最終レビューで実行済み経路を明示します。
