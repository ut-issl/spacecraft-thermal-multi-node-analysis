from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

@dataclass
class MaterialProperties:
    """材料の熱物性値"""
    name: str
    density: float  # kg/m^3
    specific_heat: float  # J/kg/K
    thermal_conductivity: float  # W/m/K
    description: str

@dataclass
class SurfaceMaterial:
    """表面光学特性"""
    name: str
    alpha: float  # 太陽吸収率
    epsilon: float  # 放射率
    description: str

@dataclass
class HeatInputRecord:
    """熱入力の記録用クラス"""
    time: float  # 時刻 [秒]
    surface_name: str  # 面の名前
    solar_heat: float  # 太陽熱 [W]
    albedo_heat: float  # アルベド熱 [W]
    earth_ir_heat: float  # 地球赤外熱 [W]
    interpanel_radiation: float  # パネル間輻射による熱収支 [W]
    total_heat: float  # 合計熱量 [W]
    temperature: float  # 面の温度 [K] 