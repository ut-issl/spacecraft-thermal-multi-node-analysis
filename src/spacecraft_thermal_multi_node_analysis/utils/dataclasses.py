from dataclasses import dataclass


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
    effective_emissivity: float | None = None  # MLIの場合の実効放射率（オプション）


@dataclass
class HeatInputRecord:
    """熱入力の記録用クラス"""

    time: float  # 時刻 [秒]
    surface_name: str  # 面の名前
    solar_heat: float  # 太陽熱 [W]
    albedo_heat: float  # アルベド熱 [W]
    earth_ir_heat: float  # 地球赤外熱 [W]
    interpanel_radiation: float  # パネル間輻射による熱収支 [W]
    conductance_heat: float  # コンダクタンスによる熱伝導 [W]
    total_heat: float  # 合計熱量 [W]
    temperature: float  # 面の温度 [K]


@dataclass
class MLINode:
    """MLIノード（算術ノード）"""

    surface_name: str
    emissivity: float  # MLIの外側カバーフィルムの放射率
    effective_emissivity: float  # MLIと内部構造との間の実効放射率
    temperature: float  # 温度 [K]
    area: float  # 面積 [m^2]
    heat_input: float  # 熱入力 [W]
    heat_output: float  # 熱出力 [W]


@dataclass
class ComponentProperties:
    """コンポーネントの熱物性"""

    name: str  # コンポーネント名
    mass: float  # 質量 [kg]
    specific_heat: float  # 比熱 [J/kg/K]
    mounting_panel: str  # 取り付けパネル名
    thermal_conductance: float  # 締結部の熱コンダクタンス [W/K]

    @property
    def heat_capacity(self) -> float:
        """熱容量 [J/K]を計算"""
        return self.mass * self.specific_heat
