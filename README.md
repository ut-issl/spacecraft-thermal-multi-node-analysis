# 多節点衛星熱解析プログラム

このプログラムは、衛星の多節点熱解析を行うPythonスクリプトです。
地球周回軌道・深宇宙探査の両方に対応し、非定常（時間発展）解析が可能です。

## 主な機能

- 地球周回軌道・深宇宙の**非定常熱解析**
- ベータ角・軌道高度・太陽方向ベクトル等のパラメータ指定
- アルベド・地球赤外の有効/無効切替（`settings/constants.yaml`）
- 各面の温度履歴・熱収支・入力のCSV/グラフ出力
- ビューファクター行列・Rij行列のCSV出力
- コマンドラインから柔軟に計算条件を指定可能

## インストール

このプロジェクトは [uv](https://github.com/astral-sh/uv) で管理されています。

```bash
# uvのインストール
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係のインストール
uv sync
```

## 使い方

### 地球周回軌道の非定常解析

```bash
python multi-node_analysis.py --mode earth --altitude 600 --beta 0 --num_orbits 5 --output_dir output
```
- `--altitude`：軌道高度 [km]
- `--beta`：ベータ角 [度]
- `--num_orbits`：解析する周回数（デフォルト1）
- `--duration`：解析時間 [秒]（指定時はnum_orbitsより優先度低、両方指定時はnum_orbits優先）
- `--output_dir`：出力ディレクトリ

### 深宇宙探査機の非定常解析

```bash
python multi-node_analysis.py --mode deep_space --sun_x 1 --sun_y 0 --sun_z 0 --duration 10000 --output_dir output
```
- `--sun_x`, `--sun_y`, `--sun_z`：太陽方向ベクトル（衛星機体座標系、正規化不要）
- `--duration`：解析時間 [秒]（省略時は6000秒）
- `--output_dir`：出力ディレクトリ

## 出力ファイル
- `temperature_data.csv`：各面の温度履歴（摂氏）
- `heat_input_data.csv`：各面・各時刻の熱入力履歴
- `view_factor_matrix.csv`：ビューファクター行列
- `rij_matrix.csv`：放射伝達行列
- `temperature_profile.png`：温度履歴グラフ
- `heat_balance.png`：熱収支グラフ
- `heat_input_by_surface.png`：面ごとの熱入力グラフ
- `orbit_visualization.png`：軌道3D可視化（地球周回のみ）

## 設定ファイル

### `settings/constants.yaml`
- 物理定数、衛星寸法、内部発熱、軌道・解析パラメータなどを定義
- `enable_albedo`/`enable_earth_ir`でアルベド・地球赤外の有効/無効を切替

### `settings/surface_properties.yaml`
- 各面の表面材・割合・光学特性を定義

### `settings/material_properties.yaml`
- 材料の熱物性値・パネル材料構成を定義

## 物理モデル・アルゴリズム
- 地球赤外・アルベドのビューファクターは球体モデル・Banister近似等を用いて厳密に計算
- 面間輻射はRij法で厳密に計算
- 姿勢・軌道パラメータは設定ファイルまたはコマンドラインで柔軟に指定可能