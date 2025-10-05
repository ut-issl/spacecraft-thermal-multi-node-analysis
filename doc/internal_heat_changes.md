# 内部発熱 (コンポーネント自励発熱) 機能 追加

## 概要
コンポーネント自身が発熱する定常パワーをシミュレーションに反映できるようになりました。YAML で `internal_heat` を指定すると、熱収支計算に [W] 単位で加算されます。

---
## 1. YAML 変更
`settings/component_properties.yaml`
```yaml
component_properties:
  BAT2:
    name: "Battery2"
    mass: 2.1
    specific_heat: 700.0
    internal_heat: 3.0           # ← 追加 (W)
    mounting:
      target: "BAT"
      thermal_conductance: 0.0
```
* `internal_heat` は **mounting と同じ階層** に記述すること。
* 未指定の場合は既定値 `0.0 W`。

---
## 2. コード変更点
| ファイル | 変更 | 備考 |
|----------|------|------|
| `utils/dataclasses.py` | `internal_heat: float = 0.0` を `ComponentProperties` に追加 | デフォルト 0 W |
| `utils/config_loader.py` | YAML から `internal_heat` を読み込み dataclass へ渡す | `props.get('internal_heat', 0.0)` |
| `utils/thermal_utils.py` | `calculate_heat_balance()` で `component.internal_heat` を熱収支へ加算 | 孤立コンポは温度が単調上昇 |

---
## 3. 動作確認例
* 例: 質量 2.1 kg, 比熱 700 J/kg/K, 発熱 3 W (BAT2)
  - 熱容量 `C = 1470 J/K`
  - 昇温速度 `dT/dt = 3 / 1470 ≈ 0.00204 K/s`
  - 1 K 上昇に約 490 s
  - 80 K 上昇に約 39200 s → 解析結果と一致

---
## 4. 注意点
1. `internal_heat` は **定常 (時間一定)** として扱われる。時間依存プロファイルは今後拡張予定。
2. 発熱はコンポーネント側にのみ加算し、パネル側には直接加えない (伝導経由で流入)。
3. 高発熱時は `analysis_parameters.time_step` を小さくして数値安定性を確保すること。
