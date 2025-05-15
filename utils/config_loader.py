import yaml
import os
from typing import Dict, List, Tuple
from .dataclasses import SurfaceMaterial, MaterialProperties

def load_constants() -> dict:
    """定数ファイルを読み込む"""
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings', 'constants.yaml'), 'r') as f:
        return yaml.safe_load(f)

def load_surface_properties() -> Tuple[Dict[str, SurfaceMaterial], Dict[str, List[Dict[str, float]]]]:
    """表面光学特性を読み込む"""
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings', 'surface_properties.yaml'), 'r') as f:
        data = yaml.safe_load(f)
    
    # 表面材料の定義を読み込み
    surface_materials = {}
    for name, props in data['surface_materials'].items():
        surface_materials[name] = SurfaceMaterial(
            name=name,
            alpha=props['alpha'],  # solar_absorptance -> alpha
            epsilon=props['epsilon'],  # infrared_emissivity -> epsilon
            description=props['description']
        )
    
    return surface_materials, data['surface_optical_assignments']

def load_material_properties() -> Dict[str, MaterialProperties]:
    """材料物性を読み込む"""
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings', 'material_properties.yaml'), 'r') as f:
        data = yaml.safe_load(f)
    
    # 材料物性の定義を読み込み
    material_properties = {}
    for name, props in data['material_properties'].items():
        material_properties[name] = MaterialProperties(
            name=name,
            density=props['density'],
            specific_heat=props['specific_heat'],
            thermal_conductivity=props['thermal_conductivity'],
            description=props['description']
        )
    
    return material_properties

def load_panel_material_assignments() -> Dict[str, List[Dict[str, float]]]:
    """パネルの材料構成を読み込む"""
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings', 'material_properties.yaml'), 'r') as f:
        data = yaml.safe_load(f)
    
    return data['panel_material_assignments'] 