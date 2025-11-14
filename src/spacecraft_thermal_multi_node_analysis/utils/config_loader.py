import os.path

import numpy as np
import pandas as pd
import yaml

from .dataclasses import ComponentProperties, MaterialProperties, SurfaceMaterial


def load_constants(settings_dir: str) -> dict:
    """定数ファイルを読み込む"""
    with open(os.path.join(settings_dir, "constants.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_surface_properties(settings_dir: str) -> tuple[dict[str, SurfaceMaterial], dict[str, list[dict[str, float]]]]:
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


def load_panel_material_assignments(settings_dir: str) -> dict[str, list[dict[str, float]]]:
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
        component_properties[name] = ComponentProperties(
            name=props["name"],
            mass=props["mass"],
            specific_heat=props["specific_heat"],
            mounting_panel=props["mounting"]["panel"],
            thermal_conductance=props["mounting"]["thermal_conductance"],
        )

    return component_properties
