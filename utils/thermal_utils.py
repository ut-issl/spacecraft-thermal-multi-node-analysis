import numpy as np
from typing import Dict, List, Tuple, Optional
import os
from dataclasses import dataclass
from .dataclasses import MaterialProperties, SurfaceMaterial, HeatInputRecord, MLINode, ComponentProperties
from .satellite_config import SatelliteConfiguration
from .config_loader import load_constants, load_surface_properties, load_material_properties, load_panel_material_assignments
import pandas as pd
from .orbit_utils import calculate_earth_ir_view_factor, calculate_albedo_view_factor

@dataclass
class PanelProperties:
    """パネルの熱物性"""
    material: MaterialProperties  # パネル材料の熱物性
    thickness: float  # パネルの厚み [mm]

@dataclass
class SurfaceOpticalProperties:
    """面の表面光学特性"""
    outside: List[Tuple[SurfaceMaterial, float]]  # (光学特性, 割合)のリスト（外側）
    inside: List[Tuple[SurfaceMaterial, float]]   # (光学特性, 割合)のリスト（内側）

@dataclass
class Surface:
    """衛星の面"""
    name: str
    normal: np.ndarray
    area: float  # m^2
    panel: PanelProperties  # パネルの熱物性
    optical_properties: SurfaceOpticalProperties  # 表面光学特性
    initial_temp: float = None  # 初期温度 [K]
    has_mli: bool = False  # MLIが装着されているかどうか
    mli_node: Optional[MLINode] = None  # MLIノード（MLI装着時のみ使用）

    def __post_init__(self):
        """MLIの有無を判定し、MLIノードを初期化"""
        # 初期温度が設定されていない場合は設定ファイルから読み込む
        if self.initial_temp is None:
            constants = load_constants()
            # 設定ファイルにinitial_temperatureがない場合は293.15K（20℃）をデフォルト値として使用
            self.initial_temp = constants.get('initial_temperature', 293.15)
            
        # 外側の表面材にMLIが含まれているかチェック
        for optical_props, _ in self.optical_properties.outside:
            if optical_props.name == "MLI":
                self.has_mli = True
                # MLIの放射率と実効放射率を取得
                if optical_props.epsilon is None:
                    raise ValueError(f"MLIの放射率が設定されていません。surface_properties.yamlでMLIのepsilonを設定してください。")
                if optical_props.effective_emissivity is None:
                    raise ValueError(f"MLIの実効放射率が設定されていません。surface_properties.yamlでMLIのeffective_emissivityを設定してください。")
                
                self.mli_node = MLINode(
                    surface_name=self.name,
                    emissivity=optical_props.epsilon,  # 外側カバーフィルムの放射率
                    effective_emissivity=optical_props.effective_emissivity,  # 実効放射率
                    temperature=self.initial_temp,  # 初期温度は面と同じ
                    area=self.area,
                    heat_input=0.0,
                    heat_output=0.0
                )
                break

    def calculate_heat_capacity(self) -> float:
        """面の熱容量を計算 [J/K]"""
        # パネルの熱容量を計算
        volume = self.area * (self.panel.thickness * 1e-3)  # mm^3 to m^3
        mass = self.panel.material.density * volume
        heat_capacity = mass * self.panel.material.specific_heat
        return heat_capacity

    def calculate_solar_heat(self, sun_vector: np.ndarray, solar_constant: float, in_eclipse: bool = False) -> float:
        """太陽熱を計算 [W]"""
        if in_eclipse:
            return 0.0
        
        solar_heat = 0.0
        cos_theta = np.dot(self.normal, sun_vector)
        if cos_theta > 0:
            # 外側の表面光学特性のみが太陽熱を受ける
            for optical_props, ratio in self.optical_properties.outside:
                solar_heat += solar_constant * self.area * cos_theta * optical_props.alpha * ratio
        return solar_heat

    def calculate_earth_heat(self, earth_vector: np.ndarray,
                           solar_constant: float, earth_albedo: float, earth_ir: float,
                           altitude: float, sun_vector: np.ndarray, orbit_normal: np.ndarray) -> Tuple[float, float]:
        """
        地球からの熱（アルベドと赤外）を計算 [W]
        
        Args:
            earth_vector: 地球方向ベクトル
            solar_constant: 太陽定数 [W/m^2]
            earth_albedo: 地球アルベド
            earth_ir: 地球赤外線 [W/m^2]
            altitude: 軌道高度 [km]
            sun_vector: 太陽方向ベクトル（正規化済み）
            orbit_normal: 軌道面の法線ベクトル（同一座標系）
        
        Returns:
            albedo_heat: アルベド熱 [W]
            earth_ir_heat: 地球赤外熱 [W]
        """
        albedo_heat = 0.0
        earth_ir_heat = 0.0
        
        # 地球赤外は等方的な放射なので、面の向きに関係なく計算
        for optical_props, ratio in self.optical_properties.outside:
            ir_view_factor = calculate_earth_ir_view_factor(earth_vector, self.normal, altitude)
            earth_ir_heat += earth_ir * self.area * optical_props.epsilon * ir_view_factor * ratio
        
        # アルベドは太陽光の反射なので、新しいビューファクター計算を使用
        for optical_props, ratio in self.optical_properties.outside:
            albedo_view_factor = calculate_albedo_view_factor(earth_vector, sun_vector, self.normal, altitude, orbit_normal)
            albedo_heat += solar_constant * earth_albedo * self.area * optical_props.alpha * albedo_view_factor * ratio
        
        return albedo_heat, earth_ir_heat

@dataclass
class ViewFactorMatrix:
    """パネル間のビューファクター行列を管理するクラス"""
    matrix: np.ndarray  # ビューファクター行列
    surface_names: List[str]  # 面の名前リスト
    dimensions: Dict[str, float]  # 衛星の寸法

    def __init__(self, surfaces: Dict[str, Surface], dimensions: Dict[str, float]):
        self.surface_names = list(surfaces.keys())
        self.dimensions = dimensions
        n = len(self.surface_names)
        self.matrix = np.zeros((n, n))
        self._calculate_view_factors(surfaces)

    def _calculate_view_factors(self, surfaces: Dict[str, Surface]):
        """各面間のビューファクターを計算"""
        n = len(self.surface_names)
        
        for i, name_i in enumerate(self.surface_names):
            surface_i = surfaces[name_i]
            for j, name_j in enumerate(self.surface_names):
                if i == j:
                    continue  # 同じ面同士のビューファクターは0
                
                surface_j = surfaces[name_j]
                # 面iから面jへのビューファクターを計算
                self.matrix[i, j] = self._calculate_view_factor(surface_i, surface_j)

    def _calculate_view_factor(self, surface_i: Surface, surface_j: Surface) -> float:
        """
        2つの面間のビューファクターを解析解で計算
        
        Args:
            surface_i: 面i
            surface_j: 面j
        
        Returns:
            view_factor: 面iから面jへのビューファクター
        """
        # 面の法線ベクトル
        ni = surface_i.normal
        nj = surface_j.normal
        
        # 面の位置関係を判定
        dot_product = np.dot(ni, nj)
        
        if abs(dot_product) == 1.0:  # 対向面（平行）
            return self._calculate_parallel_view_factor(surface_i, surface_j)
        elif abs(dot_product) == 0.0:  # 隣接面（垂直）
            return self._calculate_perpendicular_view_factor(surface_i, surface_j)
        else:
            return 0.0  # その他の面は直接見えない


    def _calculate_perpendicular_view_factor(self, surface_i: Surface, surface_j: Surface) -> float:
        """
        直交し1辺を共有する長方形面間のビューファクター（厳密解）
        """
        dims = self.dimensions
        Lx = dims['length_x'] * 1e-3
        Ly = dims['length_y'] * 1e-3
        Lz = dims['length_z'] * 1e-3
        ni = surface_i.normal
        nj = surface_j.normal

        # 面i, 面jの組み合わせごとにw, h, lを割り当て
        if abs(ni[0]) == 1 and abs(nj[1]) == 1:  # X面とY面
            w = Ly
            h = Lx
            l = Lz
        elif abs(ni[0]) == 1 and abs(nj[2]) == 1:  # X面とZ面
            w = Lz
            h = Lx
            l = Ly
        elif abs(ni[1]) == 1 and abs(nj[0]) == 1:  # Y面とX面
            w = Lx
            h = Ly
            l = Lz
        elif abs(ni[1]) == 1 and abs(nj[2]) == 1:  # Y面とZ面
            w = Lz
            h = Ly
            l = Lx
        elif abs(ni[2]) == 1 and abs(nj[0]) == 1:  # Z面とX面
            w = Lx
            h = Lz
            l = Ly
        elif abs(ni[2]) == 1 and abs(nj[1]) == 1:  # Z面とY面
            w = Ly
            h = Lz
            l = Lx
        else:
            return 0.0

        H = h / l
        W = w / l
        # 画像の式を実装（logのべき乗部分をlogの和に分解）
        term1 = (
            W * np.arctan(1 / W)
            + H * np.arctan(1 / H)
            - np.sqrt(H**2 + W**2) * np.arctan(1 / np.sqrt(H**2 + W**2))
        )
        ln1 = np.log((1 + W**2) * (1 + H**2) / (1 + W**2 + H**2))
        ln2 = W**2 * np.log((W**2 * (1 + W**2 + H**2)) / ((1 + W**2) * (W**2 + H**2)))
        ln3 = H**2 * np.log((H**2 * (1 + W**2 + H**2)) / ((1 + H**2) * (W**2 + H**2)))
        term2 = (1/4) * (ln1 + ln2 + ln3)
        F12 = (1 / (np.pi * W)) * (term1 + term2)
        return max(0.0, F12)

    def _calculate_parallel_view_factor(self, surface_i: Surface, surface_j: Surface) -> float:
        """
        平行な長方形面間のビューファクターを計算
        
        Args:
            surface_i: 面i
            surface_j: 面j
        
        Returns:
            view_factor: 面iから面jへのビューファクター
        """
        # 衛星の寸法を取得
        Lx = self.dimensions['length_x'] * 1e-3  # mm to m
        Ly = self.dimensions['length_y'] * 1e-3
        Lz = self.dimensions['length_z'] * 1e-3
        
        # 面の寸法を決定
        if abs(surface_i.normal[0]) == 1:  # X面
            a = Ly
            b = Lz
        elif abs(surface_i.normal[1]) == 1:  # Y面
            a = Lx
            b = Lz
        else:  # Z面
            a = Lx
            b = Ly
        
        # 面間距離を計算
        if abs(surface_i.normal[0]) == 1:  # X面
            d = Lx
        elif abs(surface_i.normal[1]) == 1:  # Y面
            d = Ly
        else:  # Z面
            d = Lz
        
        # 無次元パラメータ
        X = a/d
        Y = b/d
        
        # デバッグ出力
        debug_flag = load_constants().get('debug', False)
        if debug_flag:
            print(f"Parallel View Factor Calculation for {surface_i.name}->{surface_j.name}:")
            print(f"  Dimensions: a={a:.3e}m, b={b:.3e}m, d={d:.3e}m")
            print(f"  Normal vectors: ni={surface_i.normal}, nj={surface_j.normal}")
            print(f"  Non-dimensional parameters: X={X:.3f}, Y={Y:.3f}")
        
        # 解析解によるビューファクター計算
        # F12 = (2/(πXY)) * (ln(sqrt((1+X^2)(1+Y^2)/(1+X^2+Y^2)) + X*sqrt(1+Y^2)arctan(X/sqrt(1+Y^2)) + Y*sqrt(1+X^2)arctan(Y/sqrt(1+X^2)) - X*arctan(X) - Y*arctan(Y))
        term1 = np.log(np.sqrt((1+X**2)*(1+Y**2)/(1+X**2+Y**2)))
        term2 = X*np.sqrt(1+Y**2)*np.arctan(X/np.sqrt(1+Y**2))
        term3 = Y*np.sqrt(1+X**2)*np.arctan(Y/np.sqrt(1+X**2))
        term4 = X*np.arctan(X)
        term5 = Y*np.arctan(Y)
        
        F12 = (2/(np.pi*X*Y)) * (term1 + term2 + term3 - term4 - term5)
        
        # デバッグ出力（計算過程）
        if debug_flag:
            print(f"  Terms: term1={term1:.3f}, term2={term2:.3f}, term3={term3:.3f}, term4={term4:.3f}, term5={term5:.3f}")
            print(f"  Final view factor: F12={F12:.3f}")
        
        return F12

    def get_view_factor(self, surface_i_name: str, surface_j_name: str) -> float:
        """特定の面間のビューファクターを取得"""
        i = self.surface_names.index(surface_i_name)
        j = self.surface_names.index(surface_j_name)
        return self.matrix[i, j]

    def to_csv(self, filepath: str):
        """
        ビューファクター行列をCSVファイルとして出力
        行・列ともに面名ラベル付き
        """
        df = pd.DataFrame(self.matrix, index=self.surface_names, columns=self.surface_names)
        df.to_csv(filepath)

@dataclass
class ThermalNode:
    def __init__(self, initial_temp: float):
        self.surfaces: Dict[str, Surface] = {}
        self.temperatures: Dict[str, float] = {}
        self.heat_input_records: List[HeatInputRecord] = []
        self.internal_heat: Dict[str, float] = {}
        self.view_factor_matrix: Optional[ViewFactorMatrix] = None
        self.dimensions: Dict[str, float] = {}
        self._rij_cache = None
        self._rij_names = None
        self.initial_temp = initial_temp
        self.conductance_matrix: Optional[pd.DataFrame] = None
        self.enable_conductance: bool = False
        # コンポーネント関連の属性を追加
        self.components: Dict[str, ComponentProperties] = {}
        self.component_temperatures: Dict[str, float] = {}
        # コンポーネント間の伝導リンク（comp_name -> (target_name, C[W/K]))
        self.component_links: Dict[str, tuple] = {}

    def add_surface(self, surface: Surface):
        """面を追加し、初期温度を設定"""
        self.surfaces[surface.name] = surface
        self.temperatures[surface.name] = self.initial_temp
        self.internal_heat[surface.name] = 0.0
        # 衛星の寸法を取得
        if not self.dimensions:
            self.dimensions = load_constants()['satellite_dimensions']
        # 面が追加されたらビューファクター行列を再計算
        self.view_factor_matrix = ViewFactorMatrix(self.surfaces, self.dimensions)
        # Rijキャッシュもリセット
        self._rij_cache = None
        self._rij_names = None
        if surface.has_mli:
            # MLIノードの温度も初期化
            surface.mli_node.temperature = self.initial_temp

    def set_internal_heat(self, surface_name: str, heat: float):
        """特定の面の内部発熱を設定"""
        if surface_name not in self.surfaces:
            raise ValueError(f"面 {surface_name} は存在しません")
        self.internal_heat[surface_name] = heat

    def calculate_total_heat_capacity(self, surface_name: str) -> float:
        """特定の面の熱容量を計算 [J/K]"""
        if surface_name not in self.surfaces:
            raise ValueError(f"面 {surface_name} は存在しません")
        return self.surfaces[surface_name].calculate_heat_capacity()

    def calculate_interpanel_radiation(self, stefan_boltzmann: float) -> Dict[str, float]:
        """
        Rij（放射伝達行列）を用いた厳密な熱輻射計算（宇宙放射含む）
        """
        # Rij, node_namesをキャッシュ
        if self._rij_cache is None or self._rij_names is None:
            from .thermal_utils import calculate_radiative_conductance_matrix
            self._rij_cache, self._rij_names = calculate_radiative_conductance_matrix(self.surfaces, self.dimensions)
        Rij = self._rij_cache
        node_names = self._rij_names
        n = len(self.surfaces)
        surface_names = list(self.surfaces.keys())
        # 温度配列（面＋宇宙）
        T = np.array([self.temperatures[name] for name in surface_names] + [2.73])
        E = stefan_boltzmann * T**4
        # 各面の輻射熱流入を計算
        interpanel_heat = {}
        for i, name in enumerate(surface_names):
            q = 0.0
            for j in range(n+1):
                if i == j:
                    continue
                q += Rij[i, j] * (E[j] - E[i])
            interpanel_heat[name] = q
        return interpanel_heat

    def set_conductance_matrix(self, matrix: pd.DataFrame, enable: bool):
        """コンダクタンス行列を設定"""
        self.conductance_matrix = matrix
        self.enable_conductance = enable

    def calculate_conductance_heat(self) -> Dict[str, float]:
        """
        コンダクタンスによる熱伝導を計算
        
        Returns:
            Dict[str, float]: 各面のコンダクタンスによる熱収支 [W]
        """
        if not self.enable_conductance or self.conductance_matrix is None:
            return {name: 0.0 for name in self.surfaces.keys()}
        
        conductance_heat = {}
        for surface_name in self.surfaces.keys():
            heat = 0.0
            for other_name in self.surfaces.keys():
                if surface_name != other_name:
                    # Cij * (Tj - Ti) の形式で計算
                    cij = self.conductance_matrix.loc[surface_name, other_name]
                    temp_diff = self.temperatures[other_name] - self.temperatures[surface_name]
                    heat += cij * temp_diff
            conductance_heat[surface_name] = heat
        
        return conductance_heat

    def calculate_heat_balance(self, sun_vector: np.ndarray, earth_vector: np.ndarray = None,
                             in_eclipse: bool = False, time: float = 0.0,
                             altitude: float = None, orbit_normal: np.ndarray = None) -> Dict[str, float]:
        """各面の熱収支を計算（パネル間輻射をRijで最適化）"""
        constants = load_constants()
        solar_constant = constants['physical_constants']['solar_constant']
        stefan_boltzmann = constants['physical_constants']['stefan_boltzmann']
        earth_albedo = constants['physical_constants']['earth_albedo']
        earth_ir = constants['physical_constants']['earth_ir']
        enable_albedo = constants['physical_constants']['enable_albedo']
        enable_earth_ir = constants['physical_constants']['enable_earth_ir']
        
        # パネル間輻射（Rij法、宇宙放射含む）を一度だけ計算
        interpanel_radiation = self.calculate_interpanel_radiation(stefan_boltzmann)
        
        # コンダクタンスによる熱伝導を計算
        conductance_heat = self.calculate_conductance_heat()
        
        heat_balances = {}
        
        # 各面の熱収支を計算
        for surface_name, surface in self.surfaces.items():
            if surface.has_mli:
                # MLIが装着されている場合、外部熱入力はMLIノードに入る
                solar_heat = surface.calculate_solar_heat(sun_vector, solar_constant, in_eclipse)
                albedo_heat = 0.0
                earth_ir_heat = 0.0
                if earth_vector is not None and (enable_albedo or enable_earth_ir):
                    albedo_heat, earth_ir_heat = surface.calculate_earth_heat(
                        earth_vector, solar_constant, earth_albedo, earth_ir,
                        altitude, sun_vector, orbit_normal
                    )
                
                # MLIノードの熱収支を計算
                mli_heat_input = solar_heat
                if enable_albedo:
                    mli_heat_input += albedo_heat
                if enable_earth_ir:
                    mli_heat_input += earth_ir_heat
                
                # MLIと宇宙との輻射熱交換を計算（通常の放射率を使用）
                mli_temp = surface.mli_node.temperature
                space_temp = 2.73  # 宇宙背景放射温度 [K]
                mli_space_radiation = stefan_boltzmann * surface.area * surface.mli_node.emissivity * (
                    mli_temp**4 - space_temp**4
                )
                
                # MLIと面の間の輻射熱交換を計算（実効放射率を使用）
                surface_temp = self.temperatures[surface_name]
                # 面の放射率を計算（内側の表面材の放射率の平均）
                surface_emissivity = sum(opt.epsilon * ratio for opt, ratio in surface.optical_properties.inside)
                # 輻射熱交換係数を計算（1/(1/ε1 + 1/ε2 - 1)の形式）
                radiation_coefficient = 1.0 / (1.0/surface.mli_node.effective_emissivity + 1.0/surface_emissivity - 1.0)
                mli_surface_radiation = stefan_boltzmann * surface.area * radiation_coefficient * (
                    mli_temp**4 - surface_temp**4
                )
                
                # MLIノードの熱収支を更新
                surface.mli_node.heat_input = mli_heat_input
                surface.mli_node.heat_output = mli_space_radiation + mli_surface_radiation
                
                # 面の熱収支（MLIとの輻射熱交換と内部発熱のみ）
                heat_balances[surface_name] = mli_surface_radiation + self.internal_heat.get(surface_name, 0.0)
            else:
                # MLIがない場合は従来通りの計算
                solar_heat = surface.calculate_solar_heat(sun_vector, solar_constant, in_eclipse)
                albedo_heat = 0.0
                earth_ir_heat = 0.0
                if earth_vector is not None and (enable_albedo or enable_earth_ir):
                    albedo_heat, earth_ir_heat = surface.calculate_earth_heat(
                        earth_vector, solar_constant, earth_albedo, earth_ir,
                        altitude, sun_vector, orbit_normal
                    )
                
                # 面の熱収支を計算
                heat_balances[surface_name] = (
                    solar_heat +
                    (albedo_heat if enable_albedo else 0.0) +
                    (earth_ir_heat if enable_earth_ir else 0.0) +
                    self.internal_heat.get(surface_name, 0.0)
                )
            
            # コンポーネントとの熱伝導を計算
            component_heat = 0.0
            for comp_key, component in self.components.items():
                if component.mounting_target in self.surfaces and component.mounting_target == surface_name:
                    # コンポーネントとパネル間の熱伝導
                    temp_diff = self.component_temperatures[comp_key] - self.temperatures[surface_name]
                    component_heat += component.thermal_conductance * temp_diff
            
            # コンポーネントとの熱伝導を熱収支に加算
            heat_balances[surface_name] += component_heat
            
            # 熱入力記録を追加
            self.heat_input_records.append(HeatInputRecord(
                time=time,
                surface_name=surface_name,
                solar_heat=solar_heat,
                albedo_heat=albedo_heat if enable_albedo else 0.0,
                earth_ir_heat=earth_ir_heat if enable_earth_ir else 0.0,
                interpanel_radiation=interpanel_radiation.get(surface_name, 0.0),
                conductance_heat=conductance_heat.get(surface_name, 0.0),
                total_heat=heat_balances[surface_name],
                temperature=self.temperatures[surface_name]
            ))
        
        # パネル間輻射とコンダクタンスの計算と加算
        for surface_name in self.surfaces.keys():
            heat_balances[surface_name] += (
                interpanel_radiation.get(surface_name, 0.0) +
                conductance_heat.get(surface_name, 0.0)
            )
        
        # コンポーネントの熱収支を計算（パネル⇔コンポ と コンポ⇔コンポ）
        component_heat_balances = {name: 0.0 for name in self.components.keys()}
        processed_pairs = set()
        for comp_name, component in self.components.items():
            target, C = self.component_links[comp_name]
            comp_temp = self.component_temperatures[comp_name]

            # パネルとの伝導（コンポ側）
            if target in self.surfaces:
                tgt_temp = self.temperatures[target]
                heat = C * (tgt_temp - comp_temp)
                component_heat_balances[comp_name] += heat
            # コンポ↔コンポ 伝導
            elif target in self.components:
                pair = tuple(sorted([comp_name, target]))
                if pair in processed_pairs:
                    continue  # 既に処理済み
                tgt_temp = self.component_temperatures[target]
                heat = C * (tgt_temp - comp_temp)
                component_heat_balances[comp_name] += heat
                component_heat_balances[target] -= heat  # 作用反作用
                processed_pairs.add(pair)
            
            # --- 内部発熱を加算 ---
            component_heat_balances[comp_name] += component.internal_heat
        
        # コンポーネントの熱収支を追加
        heat_balances.update(component_heat_balances)
        
        return heat_balances

    def update_temperature(self, heat_balances: Dict[str, float], time_step: float) -> Dict[str, float]:
        """各面とコンポーネントの温度を更新"""
        temperature_changes = {}
        
        # 面の温度更新（既存のコード）
        for surface_name, heat_balance in heat_balances.items():
            if surface_name in self.surfaces:
                surface = self.surfaces[surface_name]
                total_heat_capacity = self.calculate_total_heat_capacity(surface_name)
                
                if surface.has_mli:
                    # MLIノードの温度更新（既存のコード）
                    mli_heat_capacity = 1  # 0.1 J/K/m^2
                    mli_temp_change = (surface.mli_node.heat_input - surface.mli_node.heat_output) * time_step / mli_heat_capacity
                    # 温度変化が大きすぎる場合は制限
                    max_temp_change = 100.0  # 最大温度変化 [K/step]
                    mli_temp_change = np.clip(mli_temp_change, -max_temp_change, max_temp_change)
                    surface.mli_node.temperature += mli_temp_change
                
                # 面の温度更新
                temp_change = heat_balance * time_step / total_heat_capacity
                self.temperatures[surface_name] += temp_change
                temperature_changes[surface_name] = temp_change
        
        # コンポーネントの温度更新
        for component_name, heat_balance in heat_balances.items():
            if component_name in self.components:
                component = self.components[component_name]
                heat_capacity = component.heat_capacity
                temp_change = heat_balance * time_step / heat_capacity
                # 温度変化が大きすぎる場合は制限
                max_temp_change = 100.0  # 最大温度変化 [K/step]
                temp_change = np.clip(temp_change, -max_temp_change, max_temp_change)
                self.component_temperatures[component_name] += temp_change
                temperature_changes[component_name] = temp_change
        
        return temperature_changes

    def get_temperature(self, surface_name: str) -> float:
        """特定の面の温度を取得"""
        if surface_name not in self.temperatures:
            raise ValueError(f"面 {surface_name} は存在しません")
        return self.temperatures[surface_name]

    def get_all_temperatures(self) -> Dict[str, float]:
        """全面の温度を取得（MLIノードの温度も含む）"""
        temps = self.temperatures.copy()
        # MLIノードの温度も追加
        for surface_name, surface in self.surfaces.items():
            if surface.has_mli:
                temps[f"{surface_name}_MLI"] = surface.mli_node.temperature
        return temps

    def get_mli_temperature(self, surface_name: str) -> Optional[float]:
        """特定の面のMLIノードの温度を取得（MLIがない場合はNone）"""
        if surface_name not in self.surfaces:
            raise ValueError(f"面 {surface_name} は存在しません")
        surface = self.surfaces[surface_name]
        if surface.has_mli:
            return surface.mli_node.temperature
        return None

    def save_rij_matrix(self, output_dir: str, filename: str = 'rij_matrix.csv'):
        """
        Rij（放射伝達行列）をCSVで出力
        行・列ともに面名+SPACEラベル付き
        """
        from .thermal_utils import calculate_radiative_conductance_matrix
        Rij, node_names = calculate_radiative_conductance_matrix(self.surfaces, self.dimensions)
        df = pd.DataFrame(Rij, index=node_names, columns=node_names)
        os.makedirs(output_dir, exist_ok=True)
        df.to_csv(os.path.join(output_dir, filename))

    def add_component(self, comp_key: str, component: ComponentProperties):
        """コンポーネントを追加し、初期温度を設定

        comp_key: YAML でのキー（識別子）
        """
        # 取付ターゲットが存在するか簡易チェック（パネルまたは既登録のコンポ）
        if component.mounting_target not in self.surfaces and component.mounting_target not in self.components:
            import warnings
            warnings.warn(
                f"コンポーネント {comp_key} の取付ターゲット {component.mounting_target} がまだ存在しません。後で解決されることを想定します。",
                RuntimeWarning)

        # 登録
        self.components[comp_key] = component

        # 初期温度設定
        target = component.mounting_target
        if target in self.surfaces:
            self.component_temperatures[comp_key] = self.temperatures[target]
        elif target in self.component_temperatures:
            self.component_temperatures[comp_key] = self.component_temperatures[target]
        else:
            self.component_temperatures[comp_key] = self.initial_temp

        # 伝導リンク登録
        self.component_links[comp_key] = (target, component.thermal_conductance)

    def get_component_temperature(self, component_name: str) -> float:
        """特定のコンポーネントの温度を取得"""
        if component_name not in self.component_temperatures:
            raise ValueError(f"コンポーネント {component_name} は存在しません")
        return self.component_temperatures[component_name]

def create_satellite_surfaces(config: SatelliteConfiguration) -> List[Surface]:
    """衛星の各面を作成"""
    dims = config.dimensions
    surfaces = []
    
    # 各面の法線ベクトルと面積を定義
    surface_defs = [
        ('PX', np.array([1, 0, 0]), dims['length_y'] * dims['length_z']),  # +X
        ('MX', np.array([-1, 0, 0]), dims['length_y'] * dims['length_z']),  # -X
        ('PY', np.array([0, 1, 0]), dims['length_x'] * dims['length_z']),  # +Y
        ('MY', np.array([0, -1, 0]), dims['length_x'] * dims['length_z']),  # -Y
        ('PZ', np.array([0, 0, 1]), dims['length_x'] * dims['length_y']),  # +Z
        ('MZ', np.array([0, 0, -1]), dims['length_x'] * dims['length_y'])   # -Z
    ]
    
    for name, normal, area in surface_defs:
        # パネルの材料構成を読み込み
        panel_config = config.panel_material_assignments[name][0]  # パネルは単一材料
        panel_material = config.material_properties[panel_config['material']]
        panel_thickness = panel_config['thickness']
        
        # 表面光学特性を読み込み
        optical_configs = config.surface_optical_assignments[name]
        
        # 外側の表面光学特性
        outside_materials = []
        for opt_config in optical_configs['outside']:
            opt_name = opt_config['material']
            ratio = opt_config['ratio']
            outside_materials.append((
                config.surface_materials[opt_name],
                ratio
            ))
        
        # 内側の表面光学特性
        inside_materials = []
        for opt_config in optical_configs['inside']:
            opt_name = opt_config['material']
            ratio = opt_config['ratio']
            inside_materials.append((
                config.surface_materials[opt_name],
                ratio
            ))
        
        surfaces.append(Surface(
            name=name,
            normal=normal,
            area=area * 1e-6,  # mm^2 to m^2
            panel=PanelProperties(
                material=panel_material,
                thickness=panel_thickness
            ),
            optical_properties=SurfaceOpticalProperties(
                outside=outside_materials,
                inside=inside_materials
            )
        ))
    
    return surfaces 

def calculate_radiative_conductance_matrix(surfaces: Dict[str, Surface], dimensions: Dict[str, float]) -> Tuple[np.ndarray, List[str]]:
    """
    6面+宇宙ノードの7x7 Rij（放射伝達行列）を作成する。
    面ノード間のRijは「面積 x i面放射率 x Fij」で計算。
    面ノードと宇宙ノード間のRijも計算。
    MLIがついている面の場合、宇宙との輻射熱交換はMLIノードが行うため、
    その面の宇宙ノードとのRijは0とする。
    Rijは対称行列ではない（一般に非対称）、対角成分は0。
    宇宙ノードは最後（index=6）とする。
    Returns:
        Rij: 7x7の放射伝達行列
        node_names: ノード名リスト（6面+SPACE）
    """
    surface_names = list(surfaces.keys())
    n = len(surface_names)
    node_names = surface_names + ["SPACE"]
    Rij = np.zeros((n+1, n+1))

    vfm = ViewFactorMatrix(surfaces, dimensions)
    F = vfm.matrix  # shape=(n, n)
    A = np.array([surfaces[name].area for name in surface_names])
    epsilon_inside = np.array([
        sum(opt.epsilon * ratio for opt, ratio in surfaces[name].optical_properties.inside)
        for name in surface_names
    ])

    # 宇宙面を拡張
    F_space = 1.0 - np.sum(F, axis=1)
    F_ext = np.zeros((n+1, n+1))
    F_ext[:n, :n] = F
    F_ext[:n, n] = F_space

    # --- 面-面間Rij（工業ソフト互換：多重反射なし） ---
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            Rij[i, j] = A[i] * epsilon_inside[i] * F[i, j]

    # --- 面-宇宙ノード間Rij（MLIの有無を考慮） ---
    for i, name in enumerate(surface_names):
        surface = surfaces[name]
        if not surface.has_mli:
            # MLIがない面のみ宇宙との輻射熱交換を計算
            epsilon_out = sum(opt.epsilon * ratio for opt, ratio in surface.optical_properties.outside)
            area = surface.area
            value = epsilon_out * area
            Rij[i, n] = value
            Rij[n, i] = value
        else:
            # MLIがついている面は宇宙との輻射熱交換を0に
            Rij[i, n] = 0.0
            Rij[n, i] = 0.0

    # 対角成分は0（初期値のまま）
    return Rij, node_names 
