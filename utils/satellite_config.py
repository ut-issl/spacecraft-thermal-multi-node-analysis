from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd
from .dataclasses import SurfaceMaterial, MaterialProperties, ComponentProperties
from .config_loader import (
    load_constants, load_surface_properties, load_material_properties,
    load_panel_material_assignments, load_conductance_matrix, load_component_properties
)

@dataclass
class SatelliteConfiguration:
    """衛星の設定を管理するクラス"""
    dimensions: Dict[str, float]  # mm
    internal_heat: Dict[str, float]  # W（面ごとの内部発熱）
    surface_materials: Dict[str, SurfaceMaterial]  # 表面光学特性
    surface_optical_assignments: Dict[str, Dict[str, List[Dict[str, float]]]]  # 面の表面光学特性割り当て（outside/inside）
    material_properties: Dict[str, MaterialProperties]  # 材料物性
    panel_material_assignments: Dict[str, List[Dict[str, float]]]  # パネルの材料構成（材料名と厚み）
    conductance_matrix: Optional[pd.DataFrame]  # パネル間の熱伝導率 [W/K]（Noneの場合は無効）
    enable_conductance: bool  # パネル間の熱伝導（Cij）を有効にするかどうか
    components: Dict[str, ComponentProperties]  # コンポーネントの熱物性値

    @classmethod
    def from_config_files(cls) -> 'SatelliteConfiguration':
        """設定ファイルから設定を読み込む"""
        constants = load_constants()
        surface_materials, surface_optical_assignments = load_surface_properties()
        material_properties = load_material_properties()
        panel_material_assignments = load_panel_material_assignments()
        components = load_component_properties()
        
        # コンダクタンス行列の有効/無効を取得
        enable_conductance = constants['analysis_parameters'].get('enable_conductance', False)
        
        # コンダクタンスが有効な場合のみ行列を読み込む
        conductance_matrix = load_conductance_matrix() if enable_conductance else None
        
        # 各面のパネル材料構成を検証
        for surface_name, panel_configs in panel_material_assignments.items():
            if len(panel_configs) != 1:
                raise ValueError(f"面 {surface_name} のパネル材料構成は単一材料である必要があります")
            if 'material' not in panel_configs[0] or 'thickness' not in panel_configs[0]:
                raise ValueError(f"面 {surface_name} のパネル材料構成に material または thickness が指定されていません")
            if panel_configs[0]['material'] not in material_properties:
                raise ValueError(f"面 {surface_name} のパネル材料 {panel_configs[0]['material']} が定義されていません")
        
        # 各面の表面光学特性を検証
        for surface_name, optical_configs in surface_optical_assignments.items():
            if 'outside' not in optical_configs or 'inside' not in optical_configs:
                raise ValueError(f"面 {surface_name} の表面光学特性に outside または inside が指定されていません")
            
            # 外側の表面光学特性を検証
            outside_ratio_sum = sum(opt['ratio'] for opt in optical_configs['outside'])
            if abs(outside_ratio_sum - 1.0) > 1e-6:
                raise ValueError(f"面 {surface_name} の外側表面光学特性の割合の合計が1.0ではありません: {outside_ratio_sum}")
            
            # 内側の表面光学特性を検証
            inside_ratio_sum = sum(opt['ratio'] for opt in optical_configs['inside'])
            if abs(inside_ratio_sum - 1.0) > 1e-6:
                raise ValueError(f"面 {surface_name} の内側表面光学特性の割合の合計が1.0ではありません: {inside_ratio_sum}")
            
            # 材料の存在確認
            for side in ['outside', 'inside']:
                for opt in optical_configs[side]:
                    if opt['material'] not in surface_materials:
                        raise ValueError(f"面 {surface_name} の{side}表面光学特性の材料 {opt['material']} が定義されていません")
        
        # コンポーネントの設定を検証
        for name, component in components.items():
            # mounting_target がパネル名の場合のみ存在チェックを行う
            if component.mounting_target in panel_material_assignments:
                pass  # OK
            elif component.mounting_target in components:  # 取付相手が別コンポ
                pass  # 後段でリンクチェックや循環チェックは別処理
            else:
                raise ValueError(
                    f"コンポーネント {name} の取付ターゲット {component.mounting_target} がパネル名でも既存コンポ名でもありません")
        
        return cls(
            dimensions=constants['satellite_dimensions'],
            internal_heat=constants['internal_heat'],  # 面ごとの内部発熱をそのまま使用
            surface_materials=surface_materials,
            surface_optical_assignments=surface_optical_assignments,
            material_properties=material_properties,
            panel_material_assignments=panel_material_assignments,
            conductance_matrix=conductance_matrix,
            enable_conductance=enable_conductance,
            components=components
        ) 