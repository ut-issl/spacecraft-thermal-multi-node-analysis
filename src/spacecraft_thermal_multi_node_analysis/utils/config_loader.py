from __future__ import annotations

import os.path
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd
import yaml

from .dataclasses import ComponentProperties, InternalPanel, MaterialProperties, SurfaceMaterial

if TYPE_CHECKING:
    from .satellite_config import PanelOpticalConfig, PanelStructuralConfig


def load_constants(settings_dir: str) -> dict:
    """定数ファイルを読み込む"""
    with open(os.path.join(settings_dir, "constants.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_surface_properties(
    settings_dir: str,
) -> tuple[dict[str, SurfaceMaterial], dict[str, dict[Literal["outside", "inside"], list[PanelOpticalConfig]]]]:
    """表面光学特性を読み込む"""
    with open(
        os.path.join(settings_dir, "surface_properties.yaml"),
        encoding="utf-8",
    ) as f:
        data = yaml.safe_load(f)

    # 表面材料の定義を読み込み
    surface_materials = {}
    for name, props in data["surface_materials"].items():
        # MLIの場合は実効放射率も読み込む
        if name == "MLI":
            surface_materials[name] = SurfaceMaterial(
                name=name,
                alpha=props["alpha"],  # solar_absorptance -> alpha
                epsilon=props["epsilon"],  # infrared_emissivity -> epsilon
                effective_emissivity=props["effective_emissivity"],  # MLIの実効放射率
                description=props["description"],
            )
        else:
            surface_materials[name] = SurfaceMaterial(
                name=name,
                alpha=props["alpha"],  # solar_absorptance -> alpha
                epsilon=props["epsilon"],  # infrared_emissivity -> epsilon
                description=props["description"],
            )

    return surface_materials, data["surface_optical_assignments"]


def load_material_properties(settings_dir: str) -> dict[str, MaterialProperties]:
    """材料物性を読み込む"""
    with open(
        os.path.join(settings_dir, "material_properties.yaml"),
        encoding="utf-8",
    ) as f:
        data = yaml.safe_load(f)

    # 材料物性の定義を読み込み
    material_properties = {}
    for name, props in data["material_properties"].items():
        material_properties[name] = MaterialProperties(
            name=name,
            density=props["density"],
            specific_heat=props["specific_heat"],
            thermal_conductivity=props["thermal_conductivity"],
            description=props["description"],
        )

    return material_properties


def load_panel_material_assignments(settings_dir: str) -> dict[str, list[PanelStructuralConfig]]:
    """パネルの材料構成を読み込む"""
    with open(
        os.path.join(settings_dir, "material_properties.yaml"),
        encoding="utf-8",
    ) as f:
        data = yaml.safe_load(f)

    return data["panel_material_assignments"]


def load_conductance_matrix(settings_dir: str) -> pd.DataFrame:
    """パネル間の熱伝導率を定義するコンダクタンス行列を読み込む

    Returns:
        pd.DataFrame: コンダクタンス行列（ノード間の熱伝導率 [W/K]）

    """
    file_path = os.path.join(settings_dir, "cij_matrix.csv")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"コンダクタンス行列の設定ファイルが見つかりません: {file_path}")

    # CSVファイルを読み込み
    df = pd.read_csv(file_path, index_col=0)

    # インデックスとカラム名が一致することを確認
    if not all(df.index == df.columns):
        raise ValueError("コンダクタンス行列のインデックスとカラム名が一致していません")

    # 対角成分が0であることを確認
    if not np.allclose(np.diag(df.values), 0.0):
        raise ValueError("コンダクタンス行列の対角成分は0である必要があります")

    # 対称行列であることを確認
    if not np.allclose(df.values, df.values.T):
        raise ValueError("コンダクタンス行列は対称行列である必要があります")

    return df


def load_component_properties(settings_dir: str) -> dict[str, ComponentProperties]:
    """コンポーネントの熱物性値を読み込む"""
    with open(
        os.path.join(settings_dir, "component_properties.yaml"),
        encoding="utf-8",
    ) as f:
        data = yaml.safe_load(f)

    # コンポーネントの定義を読み込み
    component_properties = {}
    for name, props in data["component_properties"].items():
        # オプション: コンポーネント自身の発熱 / サーモスタット式ヒータ
        #   internal_heat: 定常発熱 [W]
        #   heater: {setpoint_K: 設定温度[K], power_W: 最大投入電力[W]}
        heater = props.get("heater", {}) or {}
        component_properties[name] = ComponentProperties(
            name=props["name"],
            mass=props["mass"],
            specific_heat=props["specific_heat"],
            mounting_panel=props["mounting"]["panel"],
            thermal_conductance=props["mounting"]["thermal_conductance"],
            internal_heat=props.get("internal_heat", 0.0),
            heater_setpoint_K=heater.get("setpoint_K"),
            heater_power_W=heater.get("power_W", 0.0),
        )

    return component_properties


def load_internal_panels(
    settings_dir: str,
    material_properties: dict[str, MaterialProperties],
) -> dict[str, InternalPanel]:
    """内部パネル(外部輻射を持たない内部ノード)を読み込む（任意・ファイルが無ければ空）。

    settings_dir/internal_panels.yaml の例:
        internal_panels:
          OPTICS:
            name: "Optics Panel (SiC)"
            material: "SiC"        # material_properties.yaml の材料名
            area: 0.09             # [m^2]
            thickness: 10.0        # [mm]
            internal_heat: 2.0     # [W]（任意）
            conductances:          # [W/K] 各構体パネルへの伝導結合
              PX: 0.25
              PZ: 0.30
    質量は material+寸法、または mass[kg]+specific_heat[J/kg/K] で定義可。
    """
    file_path = os.path.join(settings_dir, "internal_panels.yaml")
    if not os.path.exists(file_path):
        return {}

    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    internal_panels: dict[str, InternalPanel] = {}
    for key, props in (data.get("internal_panels") or {}).items():
        # 熱容量の決定: material+寸法 を優先、無ければ mass+specific_heat
        if "material" in props:
            mat_name = props["material"]
            if mat_name not in material_properties:
                raise ValueError(f"内部パネル {key} の材料 {mat_name} が material_properties に定義されていません")
            mat = material_properties[mat_name]
            volume = float(props["area"]) * (float(props["thickness"]) * 1e-3)  # area[m^2] x thickness[mm->m]
            heat_capacity = mat.density * volume * mat.specific_heat
        elif "mass" in props and "specific_heat" in props:
            heat_capacity = float(props["mass"]) * float(props["specific_heat"])
        else:
            raise ValueError(
                f"内部パネル {key} は material+area+thickness か mass+specific_heat のいずれかで熱容量を定義してください",
            )

        conductances = {str(p): float(g) for p, g in (props.get("conductances") or {}).items()}
        if not conductances:
            raise ValueError(f"内部パネル {key} には conductances（構体パネルへの伝導結合）が必要です")

        internal_panels[key] = InternalPanel(
            name=props.get("name", key),
            heat_capacity_J_K=heat_capacity,
            conductances=conductances,
            internal_heat=float(props.get("internal_heat", 0.0)),
        )

    return internal_panels
