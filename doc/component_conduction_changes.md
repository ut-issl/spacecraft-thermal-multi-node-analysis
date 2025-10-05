# コンポーネント間熱伝導機能 追加

本ブランチで実装した **コンポーネント⇔コンポーネント熱伝導** 機能の概要と主な変更点をまとめます。

---
## 1. 設定ファイル (YAML) 拡張

### component_properties.yaml
```yaml
component_properties:
  BAT:
    name: "Battery"
    mass: 0.727
    specific_heat: 700.0
    mounting:
      target: "PZ"            # パネル名またはコンポ名
      thermal_conductance: 1.0 # W/K

  ELEC:
    name: "Electronics"
    mass: 0.5
    specific_heat: 800.0
    mounting:
      target: "BAT"           # BAT に直接取付
      thermal_conductance: 5.0 # W/K
```
* `mounting.target` で取付相手を指定。**YAML でのキー名** (PX, MY, BAT, …) を使用。  
  • 例: `target: "BAT"` とすると BAT2 ⇔ BAT の熱伝導。  
* 旧キー `panel` も読み込み時に自動的に `target` として解釈し、後方互換を確保。

---
## 2. dataclass の変更

`utils/dataclasses.py`
```python
@dataclass
class ComponentProperties:
    ...
    mounting_target: str  # ○○←new
    thermal_conductance: float

    # 旧 API 互換
    @property
    def mounting_panel(self) -> str:
        return self.mounting_target
```
* 新フィールド `mounting_target` を追加（YAML キー名を保持）。  
* 既存コードを壊さないよう `mounting_panel` プロパティで互換性維持。

---
## 3. コンフィグ・バリデーション

`utils/config_loader.py`
* `mounting.target` または旧 `panel` を取り込み `mounting_target` へ設定。

`utils/satellite_config.py`
* 取付ターゲットが **パネル** or **既存コンポ** かを判定。  
* 不正なターゲットの場合は例外を送出。

---
## 4. ThermalNode 拡張

`utils/thermal_utils.py`
* 追加属性
  * `self.component_links: Dict[str, Tuple[str, float]]` — `YAMLキー → (ターゲットYAMLキー, C)`
* `add_component()`
  * 取付ターゲットを確認し初期温度を設定。
  * `component_links` に登録。
* `calculate_heat_balance()`
  * **パネル⇔コンポ** 伝導 (従来) を `mounting_target` ベースで継続。
  * **コンポ⇔コンポ** 伝導を追加。
    * 1 本の C 値で双方向熱流を計算し、ペアを重複処理しないよう `processed_pairs` で管理。
* 既存 `mounting_panel` 参照をすべて置換。

---
## 5. 互換性
* 旧 YAML (`panel:` キー) や既存スクリプトはそのまま動作します。
* 新機能を使わない場合、挙動は従来と一致。

---
## 6. 使い方サンプル
1. `settings/component_properties.yaml` に `mounting.target` を記述。
2. 解析を実行すると、指定した **コンポ⇔コンポ** の伝導が熱収支に反映されます。
