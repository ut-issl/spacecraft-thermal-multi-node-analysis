import numpy as np
from typing import Tuple, List, Dict, Union
import yaml
import os
import math

def load_constants() -> dict:
    """定数ファイルを読み込む"""
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings', 'constants.yaml'), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def calculate_orbit_parameters(altitude: float, beta_angle: float) -> Tuple[float, float, float, np.ndarray, np.ndarray, np.ndarray]:
    """
    軌道パラメータを計算
    
    Args:
        altitude: 軌道高度 [km]
        beta_angle: ベータ角 [度]
    
    Returns:
        period: 軌道周期 [秒]
        eclipse_fraction: 蝕の割合
        beta_rad: ベータ角 [rad]
        orbit_normal: 軌道面の法線ベクトル
        e1: 軌道面内の第1基底ベクトル
        e2: 軌道面内の第2基底ベクトル
    """
    earth_radius = 6378.0  # 地球半径 [km]
    mu = 3.986e5  # 地球の重力定数 [km^3/s^2]
    
    # 軌道周期の計算
    a = earth_radius + altitude  # 軌道長半径 [km]
    period = 2 * np.pi * np.sqrt(a**3 / mu)  # 軌道周期 [秒]
    
    # ベータ角をラジアンに変換
    beta_rad = np.radians(beta_angle)
    
    # 太陽方向ベクトル（慣性座標系で固定）
    sun_dir = np.array([1.0, 0.0, 0.0])
    s_hat = sun_dir / np.linalg.norm(sun_dir)
    
    # 軌道面の法線ベクトル（ベータ角に基づいて回転）
    orbit_normal = np.array([np.sin(beta_rad), 0.0, np.cos(beta_rad)])
    
    # 軌道面内の基底ベクトルを計算
    if np.isclose(abs(np.dot(s_hat, orbit_normal)), 1.0):
        # 軌道面が太陽方向に垂直な場合
        e1 = np.array([0.0, 1.0, 0.0])
    else:
        # 太陽方向ベクトルを軌道面に投影
        e1 = s_hat - np.dot(s_hat, orbit_normal) * orbit_normal
        e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(orbit_normal, e1)
    
    # 蝕の割合の計算
    # 円筒形の地球影モデルを使用
    shadow_angle = np.arccos(earth_radius / a)
    if abs(beta_rad) >= np.pi/2:
        eclipse_fraction = 0.0
    else:
        # 軌道面内での太陽方向と衛星位置の角度を計算
        cos_beta = np.cos(beta_rad)
    # 蝕の割合の計算
    # 円筒形の地球影モデルを使用
    shadow_angle = np.arccos(earth_radius / a)
    if abs(beta_rad) >= np.pi/2:
        eclipse_fraction = 0.0
    else:
        # 軌道面内での太陽方向と衛星位置の角度を計算
        cos_beta = np.cos(beta_rad)
        # arccosの引数を[-1, 1]の範囲に制限
        arg = np.clip(np.sqrt(1 - (earth_radius/a)**2) / cos_beta, -1.0, 1.0)
        eclipse_fraction = np.arccos(arg) / np.pi

    return period, eclipse_fraction, beta_rad, orbit_normal, e1, e2

def calculate_earth_parameters(altitude: float, time: float, period: float) -> Tuple[np.ndarray, float]:
    """
    地球の位置とビューファクターを計算
    
    Args:
        altitude: 軌道高度 [km]
        time: 経過時間 [秒]
        period: 軌道周期 [秒]
    
    Returns:
        earth_vector: 地球方向ベクトル
        view_factor: 地球のビューファクター
    """
    earth_radius = 6378.0  # 地球半径 [km]
    a = earth_radius + altitude  # 軌道長半径 [km]
    
    # 地球方向ベクトルの計算
    theta = 2 * np.pi * time / period
    earth_vector = np.array([-np.cos(theta), 0, -np.sin(theta)])
    
    # ビューファクターの計算
    view_factor = (earth_radius / a)**2
    
    return earth_vector, view_factor

def calculate_satellite_position(time: float, period: float, altitude: float, 
                               orbit_normal: np.ndarray, e1: np.ndarray, e2: np.ndarray) -> Tuple[np.ndarray, np.ndarray, bool]:
    """
    衛星の位置ベクトル・速度ベクトルと蝕の状態を計算
    Returns:
        position: 衛星の位置ベクトル [km]
        velocity: 衛星の速度ベクトル [km/s]
        in_eclipse: 蝕の状態（True: 蝕中）
    """
    earth_radius = 6378.0  # 地球半径 [km]
    mu = 3.986e5  # 地球の重力定数 [km^3/s^2]
    orbit_radius = earth_radius + altitude
    theta = 2 * np.pi * time / period
    # 位置ベクトル
    r_vec = orbit_radius * (np.cos(theta) * e1 + np.sin(theta) * e2)
    # 速度ベクトル
    v_mag = np.sqrt(mu / orbit_radius)
    v_vec = v_mag * (-np.sin(theta) * e1 + np.cos(theta) * e2)
    # 太陽方向ベクトル（慣性座標系で固定）
    sun_dir = np.array([1.0, 0.0, 0.0])
    s_hat = sun_dir / np.linalg.norm(sun_dir)
    # 蝕の判定
    r_dot_s = np.dot(r_vec, s_hat)
    perp = r_vec - r_dot_s * s_hat
    d_perp = np.linalg.norm(perp)
    in_eclipse = (r_dot_s < 0) & (d_perp < earth_radius)
    return r_vec, v_vec, in_eclipse

def calculate_satellite_attitude(position: np.ndarray, velocity: np.ndarray, 
                               attitude_config: dict = None) -> np.ndarray:
    """
    LVLH基準で衛星の姿勢行列を構築
    
    Args:
        position: 衛星の位置ベクトル
        velocity: 衛星の速度ベクトル
        attitude_config: 姿勢制御の設定（Noneの場合はデフォルトのLVLH姿勢）
    
    Returns:
        rotation_matrix: 姿勢行列
    """
    # 基準となるベクトルを計算
    nadir = -position / np.linalg.norm(position)  # 地球方向
    orbit_normal = np.cross(position, velocity)  # 軌道面法線
    orbit_normal = orbit_normal / np.linalg.norm(orbit_normal)
    velocity_dir = velocity / np.linalg.norm(velocity)  # 進行方向
    
    # 太陽方向ベクトル（慣性座標系で固定）
    sun_dir = np.array([1.0, 0.0, 0.0])
    
    if attitude_config is None:
        # デフォルトのLVLH姿勢
        pz = nadir
        py = orbit_normal
        px = np.cross(py, pz)
    else:
        # ---------------------------------------------
        # 設定に基づいて姿勢を決定（新フォーマット／旧フォーマット両対応）
        # ---------------------------------------------
        # 方向ベクトル候補
        direction_map = {
            "sun_pointing": sun_dir,
            "nadir_pointing": nadir,
            "velocity_vector": velocity_dir,
            "orbit_normal": orbit_normal,
        }

        # ---- Primary axis ----
        prim_cfg = attitude_config.get("primary_axis")
        if isinstance(prim_cfg, dict):
            primary_axis_label = prim_cfg.get("axis", "PZ")
            primary_mode = prim_cfg.get("direction", "nadir_pointing")
        else:
            # 旧形式: 軸はPZ固定で方向だけ指定
            primary_axis_label = "PZ"
            primary_mode = prim_cfg

        primary_vec_raw = direction_map.get(primary_mode, nadir)
        primary_vec_raw = primary_vec_raw / np.linalg.norm(primary_vec_raw)

        # ---- Secondary axis ----
        sec_cfg = attitude_config.get("secondary_axis", {})
        if isinstance(sec_cfg, dict):
            secondary_axis_label = sec_cfg.get("axis", "PY")
            secondary_mode = sec_cfg.get("direction", "orbit_normal")
        else:
            secondary_axis_label = "PY"
            secondary_mode = sec_cfg

        secondary_vec_raw = direction_map.get(secondary_mode, orbit_normal)
        # 第1軸に直交化
        secondary_vec_raw = secondary_vec_raw - np.dot(secondary_vec_raw, primary_vec_raw) * primary_vec_raw
        secondary_vec_raw = secondary_vec_raw / np.linalg.norm(secondary_vec_raw)

        # ---- 各ボディ正方向軸に割り当て ----
        body_axes = {"PX": None, "PY": None, "PZ": None}

        def assign(axis_label: str, vec: np.ndarray):
            if axis_label.startswith("P"):
                body_axes["P" + axis_label[1]] = vec
            else:  # M* → 正方向へ符号反転
                body_axes["P" + axis_label[1]] = -vec

        assign(primary_axis_label, primary_vec_raw)
        assign(secondary_axis_label, secondary_vec_raw)

        # ---- 残り 1 軸をクロス積で決定 ----
        if body_axes["PX"] is None:
            body_axes["PX"] = np.cross(body_axes["PY"], body_axes["PZ"])
            body_axes["PX"] /= np.linalg.norm(body_axes["PX"])
        elif body_axes["PY"] is None:
            body_axes["PY"] = np.cross(body_axes["PZ"], body_axes["PX"])
            body_axes["PY"] /= np.linalg.norm(body_axes["PY"])
        elif body_axes["PZ"] is None:
            body_axes["PZ"] = np.cross(body_axes["PX"], body_axes["PY"])
            body_axes["PZ"] /= np.linalg.norm(body_axes["PZ"])

        px = body_axes["PX"]
        py = body_axes["PY"]
        pz = body_axes["PZ"]
    
    # 正規化
    px = px / np.linalg.norm(px)
    py = py / np.linalg.norm(py)
    pz = pz / np.linalg.norm(pz)
    
    # 姿勢行列を構築
    rotation_matrix = np.column_stack([px, py, pz])
    
    # デバッグ
    debug_flag = load_constants().get('debug', False)
    if debug_flag:
        print(f"[DEBUG_ATT] PX: {px}, PY: {py}, PZ: {pz}")
        print(f"[DEBUG_ATT] 直交性: PX・PY={np.dot(px,py):.3e}, PY・PZ={np.dot(py,pz):.3e}, PZ・PX={np.dot(pz,px):.3e}")
        print(f"[DEBUG_ATT] det(R): {np.linalg.det(rotation_matrix):.6f}")
    
    return rotation_matrix

def calculate_sun_vector_in_satellite_frame(
    time: float,
    period: float,
    beta_angle: float,
    rotation_matrix: np.ndarray
) -> np.ndarray:
    """
    衛星固定座標系での太陽方向ベクトルを計算
    """
    # 軌道座標系での太陽方向ベクトル（ベータ角90度ならX方向）
    sun_vector_orbit = np.array([1.0, 0.0, 0.0])
    # 姿勢行列の転置で衛星固定座標系へ
    sun_vector = rotation_matrix.T @ sun_vector_orbit
    return sun_vector / np.linalg.norm(sun_vector)

def calculate_earth_ir_view_factor(earth_vector: np.ndarray, normal_vector: np.ndarray, altitude: float) -> float:
    """
    地球赤外用のビューファクターを計算
    
    Args:
        earth_vector: 地球方向ベクトル（正規化されていない）
        normal_vector: 面の法線ベクトル
        altitude: 軌道高度 [km]
    
    Returns:
        view_factor: 地球赤外用のビューファクター
    """
    earth_radius = 6378.0  # 地球半径 [km]
    
    # 地球方向ベクトルを正規化
    earth_direction = earth_vector
    
    # パラメータの計算
    lamda = np.arccos(np.clip(np.dot(earth_direction, normal_vector), -1.0, 1.0))
    h = altitude  # 高度 [km]
    H = (earth_radius + h) / earth_radius
    phi_m = np.arcsin(1.0 / H)
    b = np.sqrt(H * H - 1.0)
    
    # ビューファクターの計算
    # ref) POWER INPUT TO A SMALL FLAT PLATE FROM A DIFFUSELY RADIATING SPHERE WITH APPLICATION TO EARTH SATELLITES: THE SPINNING PLATE
    if h < 1732.0:  # 1732 km未満の場合
        if lamda <= np.pi/2.0 - phi_m:
            view_factor = np.cos(lamda) / (H * H)
        elif lamda <= np.pi/2.0 + phi_m:
            view_factor = (0.5 - 
                          (1.0/np.pi) * np.arcsin(b/(H * np.sin(lamda))) +
                          (1.0/(np.pi * H * H)) * (np.cos(lamda) * np.arccos(-b/np.tan(lamda)) - 
                                                  b * np.sqrt(1.0 - (H * np.cos(lamda))**2)))
        else:
            view_factor = 0.0
    else:  # 1732 km以上の場合
        if lamda < np.pi/2.0:
            # 立体角として考慮
            view_factor = 0.25 / (H * H)
        else:
            view_factor = 0.0
    
    return view_factor

def calculate_albedo_view_factor(earth_vector: np.ndarray, sun_vector: np.ndarray, normal_vector: np.ndarray, altitude: float, orbit_normal: np.ndarray) -> float:
    """
    アルベド用のビューファクターを計算
    
    Args:
        earth_vector: 地球方向ベクトル（正規化されていない）
        sun_vector: 太陽方向ベクトル（正規化済み）
        normal_vector: 面の法線ベクトル
        altitude: 軌道高度 [km]
        orbit_normal: 軌道面の法線ベクトル（同一座標系）
    
    Returns:
        view_factor: アルベド用のビューファクター
    """
    earth_radius = 6378.0  # 地球半径 [km]
    
    # 地球方向ベクトルを正規化
    earth_direction = earth_vector
    
    # 太陽と地球の方向ベクトルから反射方向を計算
    vec_a = -earth_direction
    vec_b = (sun_vector - earth_direction)
    vec_b = vec_b / np.linalg.norm(vec_b)
    
    # パラメータの計算
    cos_theta = np.dot(vec_a, vec_b)
    lamda = np.arccos(np.clip(np.dot(earth_direction, normal_vector), -1.0, 1.0))
    h = altitude  # 高度 [km]
    H = (earth_radius + h) / earth_radius
    phi_m = np.arcsin(1.0 / H)
    b = np.sqrt(H * H - 1.0)
    
    # 軌道面の法線ベクトルを参照可能
    # 例: beta_angle = np.arccos(np.clip(np.dot(orbit_normal, sun_vector), -1.0, 1.0))
    # 必要に応じてこの中で利用可能
    
    # ビューファクターの計算
    # ref) POWER INPUT TO A SMALL FLAT PLATE FROM A DIFFUSELY RADIATING SPHERE WITH APPLICATION TO EARTH SATELLITES: THE SPINNING PLATE
    if h < 1732.0:  # 1732 km未満の場合
        if lamda <= np.pi/2.0 - phi_m:
            view_factor = np.cos(lamda) / (H * H)
        elif lamda <= np.pi/2.0 + phi_m:
            view_factor = (0.5 - 
                          (1.0/np.pi) * np.arcsin(b/(H * np.sin(lamda))) +
                          (1.0/(np.pi * H * H)) * (np.cos(lamda) * np.arccos(-b/np.tan(lamda)) - 
                                                  b * np.sqrt(1.0 - (H * np.cos(lamda))**2)))
        else:
            view_factor = 0.0
    else:  # 1732 km以上の場合
        if lamda < np.pi/2.0:
            # 立体角として考慮
            view_factor = 0.25 / (H * H)
        else:
            view_factor = 0.0
    
    # β角の計算（ラジアン）
    beta_angle = np.arccos(np.clip(np.dot(orbit_normal, sun_vector), -1.0, 1.0))
    # β角の計算（度）
    beta_angle_deg = np.degrees(beta_angle)

    # Banisterの近似
    # ref) RADIATION GEOMETRY FACTOR BETWEEN THE EARTH AND A SATELLITE
    if cos_theta > 0.0:
        # TODO: 指数の値はビューファクターと相関させる必要がある
        if beta_angle_deg > 68.0:
            view_factor *= np.power(cos_theta, 8.0)
        else:
            view_factor *= np.power(cos_theta, 5.0)
    else:
        view_factor = 0.0
    
    return view_factor 