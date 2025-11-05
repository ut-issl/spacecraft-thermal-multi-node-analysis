# 多節点衛星熱解析プログラム

このプログラムは、衛星の多節点熱解析を行うPythonスクリプトです。
地球周回軌道・深宇宙探査の両方に対応し、非定常（時間発展）解析が可能です。

## 主な機能

- 地球周回軌道・深宇宙の**非定常熱解析**
- ベータ角・軌道高度・太陽方向ベクトル等のパラメータ指定
- アルベド・地球赤外の有効/無効切替（`settings/constants.yaml`）
- コンダクタンス行列による熱伝導計算（`settings/cij_matrix.csv`）
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

### 一括解析実行機能

複数の解析条件を一括実行するには、`batch-analysis`コマンドを使用します。

1. 解析設定のテンプレートファイルを作成：
```bash
uv run batch-analysis create-template
```

2. 作成された`analysis_config_template.csv`を編集して、実行したい解析条件を記述：
```csv
mode,altitude,beta,sun_x,sun_y,sun_z,duration,num_orbits,temp_grid_interval,output_dir
earth,500.0,60.0,,,40010.0,,5.0,output/earth_orbit_alt500.0_beta60.0
earth,300.0,45.0,,,40010.0,,5.0,output/earth_orbit_alt300.0_beta45.0
deep_space,,,,1.0,0.0,0.0,40010.0,,5.0,output/deep_space_sun_x1.0_y0.0_z0.0
```

3. 設定ファイルを使って一括解析を実行：
```bash
uv run batch-analysis batch analysis_config_template.csv
```

#### 設定ファイルの項目
- `mode`: 解析モード（'earth' または 'deep_space'）
- `altitude`: 軌道高度 [km]（地球周回軌道の場合のみ）
- `beta`: ベータ角 [度]（地球周回軌道の場合のみ）
- `sun_x`, `sun_y`, `sun_z`: 太陽方向ベクトル（深宇宙の場合のみ）
- `duration`: 解析時間 [秒]
- `num_orbits`: 周回数（指定時はdurationより優先）
- `temp_grid_interval`: 温度プロファイルの等温線の間隔 [°C]（デフォルト: 5.0）
  - 温度プロファイルグラフの縦軸（温度軸）の目盛り間隔を指定
  - 小さい値を指定すると細かい温度変化が見やすくなる
  - 大きい値を指定すると全体的な温度傾向が把握しやすくなる
- `output_dir`: 出力ディレクトリ

#### ログファイル
- ファイル名：`analysis_log.log`
- 内容：
  - 解析実行時刻
  - 各解析の設定パラメータ
  - 実行状態（成功/エラー）
  - エラーが発生した場合はエラーメッセージ
- 特徴：
  - 追記モードで記録（既存のログを保持）
  - 解析を実行するたびに新しい結果が追加
  - 時系列での解析実行履歴を追跡可能

### 地球周回軌道の非定常解析

```bash
uv run multi-node-analysis --mode earth --altitude 600 --beta 0 --duration 40010 --output_dir output --temp-grid-interval 5.0
```
- `--altitude`：軌道高度 [km]
- `--beta`：ベータ角 [度]
- `--num_orbits`：解析する周回数（デフォルト1）
- `--duration`：解析時間 [秒]（指定時はnum_orbitsより優先度低、両方指定時はnum_orbits優先）
- `--output_dir`：出力ディレクトリ
- `--temp-grid-interval`：温度プロファイルの等温線の間隔 [°C]（デフォルト: 5.0）

### 深宇宙探査機の非定常解析

```bash
uv run multi-node-analysis --mode deep_space --sun_x 1 --sun_y 0 --sun_z 0 --duration 10010 --output_dir output --temp-grid-interval 5.0
```
- `--sun_x`, `--sun_y`, `--sun_z`：太陽方向ベクトル（衛星機体座標系、正規化不要）
- `--duration`：解析時間 [秒]（省略時は6000秒）
- `--output_dir`：出力ディレクトリ
- `--temp-grid-interval`：温度プロファイルの等温線の間隔 [°C]（デフォルト: 5.0）

## 出力ファイル
- `temperature_data.csv`：各面の温度履歴（摂氏）
- `heat_input_data.csv`：各面・各時刻の熱入力履歴
- `view_factor_matrix.csv`：ビューファクター行列
- `rij_matrix.csv`：放射伝達行列
- 温度プロファイルグラフ（3種類）：
  - `temperature_panel.png`：パネル温度のみ（PX, MX, PY, MY, PZ, MZ）
  - `temperature_components.png`：コンポーネント温度のみ
  - `temperature_all.png`：全温度（パネルとコンポーネント）
  - 特徴：
    - パネルは固定の色で表示（視覚的に区別しやすい色を選択）
    - コンポーネントはパネルと異なる色で自動的に割り当て
    - 等温線の間隔はデフォルトで5°C
- `heat_balance.png`：熱収支グラフ
- `heat_input_by_surface.png`：面ごとの熱入力グラフ
- `orbit_visualization.png`：軌道3D可視化（地球周回のみ）
- `settings/`：解析に使用した設定ファイルのコピー
  - `constants.yaml`：物理定数、衛星寸法、内部発熱、軌道・解析パラメータ
  - `surface_properties.yaml`：各面の表面材・割合・光学特性
  - `material_properties.yaml`：材料の熱物性値・パネル材料構成
  - `component_properties.yaml`：コンポーネントの熱物性値・取り付け情報
  - `cij_matrix.csv`：コンダクタンス行列を定義するCSVファイル

## 設定ファイル

### `settings/constants.yaml`
- 物理定数、衛星寸法、内部発熱、軌道・解析パラメータなどを定義
- `enable_albedo`/`enable_earth_ir`でアルベド・地球赤外の有効/無効を切替
- `enable_conductance`でコンダクタンス行列の有効/無効を切替

### `settings/surface_properties.yaml`
- 各面の表面材・割合・光学特性を定義

### `settings/material_properties.yaml`
- 材料の熱物性値・パネル材料構成を定義

### `settings/cij_matrix.csv`
- コンダクタンス行列を定義するCSVファイル
- 形式：
  - 1行目：面の名前（PX, MX, PY, MY, PZ, MZ）
  - 2行目以降：各面間のコンダクタンス値 [W/K]
  - 例：
    ```csv
    ,PX,MX,PY,MY,PZ,MZ
    PX,0,0.1,0.2,0,0.3,0
    MX,0.1,0,0,0.2,0,0.3
    PY,0.2,0,0,0.1,0.2,0
    MY,0,0.2,0.1,0,0,0.2
    PZ,0.3,0,0.2,0,0,0.1
    MZ,0,0.3,0,0.2,0.1,0
    ```
- 注意：
  - 対角成分は0（自身との熱伝導は考慮しない）
  - 対称行列である必要はない（方向性のある熱伝導を表現可能）
  - 値は正の実数（負の値は無効）

### `settings/component_properties.yaml`
- コンポーネントの熱物性値と取り付け情報を定義
- 各コンポーネントの定義項目：
  - `name`: コンポーネントの表示名
  - `mass`: 質量 [kg]
  - `specific_heat`: 比熱 [J/kg/K]
  - `mounting`: 取り付け情報
    - `panel`: 取り付け面（PX, MX, PY, MY, PZ, MZ）
    - `thermal_conductance`: 締結部の熱コンダクタンス [W/K]
- 例：
  ```yaml
  component_properties:
    BAT:  # バッテリ
      name: "Battery"
      mass: 2.1  # 質量 [kg]
      specific_heat: 700.0  # 比熱 [J/kg/K]
      mounting:
        panel: "MY"  # +Y面に取り付け
        thermal_conductance: 1.0  # 締結部の熱コンダクタンス
  ```
- 注意：
  - コンポーネントの追加は、このファイルに新しいエントリを追加するだけで可能
  - 温度プロファイルグラフでは、コンポーネントは自動的に色分けされる
  - 締結部の熱コンダクタンスが0の場合は、コンポーネントは取り付け面と熱的に絶縁

## 物理モデル・アルゴリズム
- 地球赤外・アルベドのビューファクターは球体モデル・Banister近似等を用いて厳密に計算
- 面間輻射はRij法で厳密に計算
- コンダクタンス行列による熱伝導計算（Cij * (Tj - Ti)の形式）
- 姿勢・軌道パラメータは設定ファイルまたはコマンドラインで柔軟に指定可能

## 温度データ比較機能

`compare-temperature-data`コマンドを使用して、異なる解析結果間の温度データを比較できます。
想定は、ThermalDesktopのWrite Results Data to Text機能で出力したCSVと、本プログラムの出力データの比較です。

### 単一の比較を実行

```bash
uv run compare-temperature-data single <comparison/td/のCSVファイル> <output/配下のtemperature_data.csvファイル>
```

例：
```bash
uv run compare-temperature-data single comparison/td/test.csv output/earth_orbit_alt500.0_beta60.0/temperature_data.csv
```

### 複数の比較を一括実行

1. 比較設定のテンプレートファイルを作成：
```bash
uv run compare-temperature-data create-template
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
uv run compare-temperature-data batch comparison_config_template.csv
```

### 出力ファイル

比較結果は`comparison/`ディレクトリに以下の形式で保存されます：

1. 差分データCSVファイル
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

2. RMSEログファイル
- ファイル名：`comparison/comparison_rmse.log`
- 内容：
  - 比較実行時刻
  - 比較元ファイルと比較先ファイルのパス
  - 各ノードの時間平均RMSE（二乗平均平方根誤差）
- 特徴：
  - 追記モードで記録（既存のログを保持）
  - 比較を実行するたびに新しい結果が追加
  - 時系列での比較結果の推移を追跡可能

ログファイルの例：
```
=== 比較実行時刻: 2024-03-21 15:30:45 ===
比較元: comparison/td/test.csv
比較先: output/earth_orbit_alt500.0_beta60.0/temperature_data.csv
各ノードの時間平均RMSE [°C]:
  PX [°C]: 1.234567
  MX [°C]: 2.345678
  PY [°C]: 1.876543
  MY [°C]: 2.123456
  PZ [°C]: 1.987654
  MZ [°C]: 2.234567
  MY_MLI [°C]: 1.765432
--------------------------------------------------
```

### オプション

- `--output-dir`: 出力先ディレクトリを指定（デフォルト: `comparison`）
```bash
uv run compare-temperature-data single <td_file> <output_file> --output-dir custom_output
uv run compare-temperature-data batch <config_file> --output-dir custom_output
```
