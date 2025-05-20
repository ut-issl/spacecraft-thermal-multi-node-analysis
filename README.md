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

## 温度データ比較機能

`compare_temperature_data.py`を使用して、異なる解析結果間の温度データを比較できます。
想定は、ThermalDesktopのWrite Results Data to Text機能で出力したCSVと、本プログラムの出力データの比較です。

### 単一の比較を実行

```bash
python compare_temperature_data.py single <comparison/td/のCSVファイル> <output/配下のtemperature_data.csvファイル>
```

例：
```bash
python compare_temperature_data.py single comparison/td/test.csv output/earth_orbit_alt500.0_beta60.0/temperature_data.csv
```

### 複数の比較を一括実行

1. 比較設定のテンプレートファイルを作成：
```bash
python compare_temperature_data.py create-template
```

2. 作成された`comparison_config_template.csv`を編集して、比較したいファイルの組み合わせを記述：
```csv
td_file,output_file
comparison/td/test1.csv,output/earth_orbit_alt500.0_beta60.0/temperature_data.csv
comparison/td/test2.csv,output/earth_orbit_alt300.0_beta45.0/temperature_data.csv
comparison/td/test3.csv,output/earth_orbit_alt700.0_beta75.0/temperature_data.csv
```

3. 設定ファイルを使って一括比較を実行：
```bash
python compare_temperature_data.py batch comparison_config_template.csv
```

### 出力ファイル

比較結果は`comparison/`ディレクトリに以下の形式で保存されます：
- ファイル名：`diff_<tdファイル名>_vs_<outputフォルダ名>.csv`
- 内容：
  - `Time [s]`: 時間
  - `PX [°C]_diff`: PXノードの温度差分
  - `MX [°C]_diff`: MXノードの温度差分
  - `PY [°C]_diff`: PYノードの温度差分
  - `MY [°C]_diff`: MYノードの温度差分
  - `PZ [°C]_diff`: PZノードの温度差分
  - `MZ [°C]_diff`: MZノードの温度差分
  - `MY_MLI [°C]_diff`: MY_MLIノードの温度差分

### オプション

- `--output-dir`: 出力先ディレクトリを指定（デフォルト: `comparison`）
```bash
python compare_temperature_data.py single <td_file> <output_file> --output-dir custom_output
python compare_temperature_data.py batch <config_file> --output-dir custom_output
```