import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .orbit_utils import calculate_orbit_parameters
from .thermal_utils import HeatInputRecord

logger = logging.getLogger(__name__)

# フォントの設定
plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.sans-serif"] = ["Arial"]
plt.rcParams["axes.unicode_minus"] = False  # マイナス記号の文字化け防止

# パネルの色マッピング（固定）
# 視覚的に区別しやすい色を選択
PANEL_COLORS = {
    "PX": "#FF0000",  # 赤
    "MX": "#FFA500",  # オレンジ
    "PY": "#0000FF",  # 青
    "MY": "#800080",  # 紫
    "PZ": "#008000",  # 緑
    "MZ": "#FF1493",  # ピンク
}


def plot_temperature_profile(
    times: list[float],
    temperatures: dict[str, list[float]],
    output_dir: str,
    eclipse_flags: list[bool] | None = None,
    temp_grid_interval: float = 5.0,
):
    """Plot and save temperature history
    eclipse_flags: 各時刻で蝕中かどうかのリスト（Trueならグレー背景）
    MLIノードの温度はグラフには表示しない
    temp_grid_interval: 等温線の間隔 [°C]

    以下の3種類のプロファイルを出力:
    1. temperature_panel.png: パネル温度のみ
    2. temperature_components.png: コンポーネント温度のみ
    3. temperature_all.png: 全温度（パネルとコンポーネント）
    """
    # パネルとコンポーネントの温度データを分離
    panel_temps = {}
    component_temps = {}

    for name, temp_history in temperatures.items():
        # MLIノードの温度は除外
        if name.endswith("_MLI"):
            continue
        # 温度履歴がリストでない場合はリストに変換
        if not isinstance(temp_history, list):
            temp_history = [temp_history]

        # パネルとコンポーネントを分類
        if name in ["PX", "MX", "PY", "MY", "PZ", "MZ"]:
            panel_temps[name] = temp_history
        else:
            component_temps[name] = temp_history

    # コンポーネントの色を動的に割り当てる関数
    def get_component_colors(component_names: list[str]) -> dict[str, str]:
        # matplotlibのデフォルトの色サイクルを取得
        default_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        # パネルで使用している色を除外
        used_colors = set(PANEL_COLORS.values())
        available_colors = [c for c in default_colors if c not in used_colors]

        # コンポーネント名をソートして一貫性のある色割り当てを保証
        sorted_components = sorted(component_names)
        # 利用可能な色を循環して使用
        return {name: available_colors[i % len(available_colors)] for i, name in enumerate(sorted_components)}

    # 共通のプロット設定関数
    def plot_temperature_subplot(
        temp_dict: dict[str, list[float]],
        title: str,
        filename: str,
    ):
        plt.figure(figsize=(10, 6))

        # 温度の範囲を取得（ケルビンから摂氏に変換）
        all_temps = []
        for temp_history in temp_dict.values():
            all_temps.extend([temp - 273.15 for temp in temp_history])

        if not all_temps:  # 温度データが空の場合のエラー処理
            raise ValueError(
                f"有効な温度データが見つかりません。{title}の温度データが必要です。",
            )

        min_temp = np.floor(min(all_temps) / temp_grid_interval) * temp_grid_interval
        max_temp = np.ceil(max(all_temps) / temp_grid_interval) * temp_grid_interval

        # 等温線のグリッドを描画
        plt.grid(True, which="major", axis="y", linestyle="-", alpha=0.3)
        plt.yticks(
            np.arange(min_temp, max_temp + temp_grid_interval, temp_grid_interval),
        )

        # コンポーネントの色を取得
        component_names = [name for name in temp_dict if name not in PANEL_COLORS]
        component_colors = get_component_colors(component_names)

        # プロット順序を制御（パネル→コンポーネント）
        plot_order = sorted(
            temp_dict.keys(),
            key=lambda x: (x not in ["PX", "MX", "PY", "MY", "PZ", "MZ"], x),
        )

        for name in plot_order:
            temp_history = temp_dict[name]
            # Convert Kelvin to Celsius
            temp_celsius = [temp - 273.15 for temp in temp_history]
            # 時間と温度の長さが一致することを確認
            if len(times) != len(temp_celsius):
                raise ValueError(
                    f"時間と温度のデータ長が一致しません。name: {name}, times: {len(times)}, temperatures: {len(temp_celsius)}",
                )

            # 色の設定
            if name in PANEL_COLORS:
                color = PANEL_COLORS[name]
            else:
                color = component_colors[name]

            plt.plot(times, temp_celsius, label=name, color=color)

        # 蝕中の時間帯にグレー背景を描画
        if eclipse_flags is not None and len(eclipse_flags) == len(times):
            in_eclipse = False
            start = None
            for i, flag in enumerate(eclipse_flags):
                if flag and not in_eclipse:
                    start = times[i]
                    in_eclipse = True
                elif not flag and in_eclipse:
                    end = times[i]
                    plt.axvspan(start, end, color="gray", alpha=0.2, zorder=0)
                    in_eclipse = False
            # 最後が蝕中で終わる場合
            if in_eclipse and start is not None:
                plt.axvspan(start, times[-1], color="gray", alpha=0.2, zorder=0)

        plt.xlabel("Time [s]")
        plt.ylabel("Temperature [°C]")
        plt.title(title)
        plt.legend()

        # Save and close the plot
        plt.savefig(os.path.join(output_dir, filename))
        plt.close()

    # パネル温度のプロット
    if panel_temps:
        plot_temperature_subplot(
            panel_temps,
            "Temperature History of Satellite Panels",
            "temperature_panel.png",
        )

    # コンポーネント温度のプロット
    if component_temps:
        plot_temperature_subplot(
            component_temps,
            "Temperature History of Components",
            "temperature_components.png",
        )

    # 全温度のプロット
    all_temps = {**panel_temps, **component_temps}
    if all_temps:
        plot_temperature_subplot(
            all_temps,
            "Temperature History of All Elements",
            "temperature_all.png",
        )


def save_temperature_data(times: list[float], temperatures: dict[str, list[float]], output_dir: str):
    """Save temperature data to CSV file

    Args:
        times: Time list [s]
        temperatures: Temperature history for each surface (key: surface name)
        output_dir: Output directory

    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create dataframe
    data = {"Time [s]": np.array(times)}
    for surface_name, temp_history in temperatures.items():
        # Convert Kelvin to Celsius
        temp_celsius = [temp - 273.15 for temp in temp_history]
        data[f"{surface_name} [°C]"] = temp_celsius

    df = pd.DataFrame(data)
    df.to_csv(os.path.join(output_dir, "temperature_data.csv"), index=False)


def plot_heat_balance(heat_input_records: list[HeatInputRecord], output_dir: str):
    """Plot and save heat balance (total heat balance per surface over time)"""
    # 各面ごとに時系列とTotal Heat Balanceを抽出
    surface_names = sorted({record.surface_name for record in heat_input_records})
    plt.figure(figsize=(12, 6))
    for surface_name in surface_names:
        surface_records = [r for r in heat_input_records if r.surface_name == surface_name]
        times = [r.time for r in surface_records]
        total_heat = [r.total_heat for r in surface_records]
        plt.plot(times, total_heat, label=surface_name)
    plt.xlabel("Time [s]")
    plt.ylabel("Heat Balance [W]")
    plt.title("Heat Balance of Satellite Surfaces")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "heat_balance.png"))
    plt.close()


def plot_heat_input_by_surface(
    heat_input_records: list[HeatInputRecord],
    output_dir: str,
):
    """Plot and save heat input by surface"""
    surface_names = sorted({record.surface_name for record in heat_input_records})

    for surface_name in surface_names:
        surface_records = [r for r in heat_input_records if r.surface_name == surface_name]
        times = [r.time for r in surface_records]

        plt.figure(figsize=(12, 6))
        # Solar Heat: red
        plt.plot(
            times,
            [r.solar_heat for r in surface_records],
            label="Solar Heat",
            color="red",
            linestyle="-",
        )
        # Albedo Heat: orange
        plt.plot(
            times,
            [r.albedo_heat for r in surface_records],
            label="Albedo Heat",
            color="orange",
            linestyle="-",
        )
        # Earth IR Heat: green
        plt.plot(
            times,
            [r.earth_ir_heat for r in surface_records],
            label="Earth IR Heat",
            color="green",
            linestyle="-",
        )
        # Interpanel Radiation: cyan
        plt.plot(
            times,
            [r.interpanel_radiation for r in surface_records],
            label="Interpanel Radiation",
            color="cyan",
            linestyle="-",
        )
        # Internal Heat: purple dashed
        if hasattr(surface_records[0], "internal_heat"):
            plt.plot(
                times,
                [getattr(r, "internal_heat", 0) for r in surface_records],
                label="Internal Heat",
                color="purple",
                linestyle="--",
            )
        # Total Heat Balance: black, thick
        plt.plot(
            times,
            [r.total_heat for r in surface_records],
            label="Total Heat Balance",
            color="black",
            linestyle="-",
            linewidth=3,
        )

        plt.xlabel("Time [s]")
        plt.ylabel("Heat Input [W]")
        plt.title(f"Heat Input Breakdown for Surface {surface_name}")
        plt.grid(True)
        plt.legend()

        # Save and close the plot
        plt.savefig(os.path.join(output_dir, f"heat_input_{surface_name}.png"))
        plt.close()


def save_heat_input_data(
    records: list[HeatInputRecord],
    output_dir: str | None = None,
    filename: str = "heat_input_data.csv",
):
    """熱入力データをCSVファイルに保存

    Args:
        records: 熱入力記録のリスト
        output_dir: 出力ディレクトリ
        filename: 出力ファイル名

    """
    # データフレームの作成
    data = []
    for record in records:
        data.append(
            {
                "Time [hours]": record.time / 3600,
                "Surface": record.surface_name,
                "Solar Heat [W]": record.solar_heat,
                "Albedo Heat [W]": record.albedo_heat,
                "Earth IR Heat [W]": record.earth_ir_heat,
                "Interpanel Radiation [W]": record.interpanel_radiation,
                "Conductance Heat [W]": record.conductance_heat,
                "Total Heat [W]": record.total_heat,
            },
        )

    df = pd.DataFrame(data)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        df.to_csv(os.path.join(output_dir, filename), index=False)
    else:
        df.to_csv(filename, index=False)


def plot_orbit_visualization(
    altitude: float,
    beta_angle: float,
    output_dir: str | None = None,
    filename: str = "orbit_visualization.png",
) -> None:
    """Visualize satellite orbit in 3D

    Args:
        altitude: Orbit altitude [km]
        beta_angle: Beta angle [deg] (angle between orbit normal and sun direction)
        output_dir: Output directory (None for display only)
        filename: Output filename

    """
    # Earth parameters
    earth_radius = 6371.0  # Earth radius [km]
    orbit_radius = earth_radius + altitude

    logger.debug("\n=== Detailed Debug Information ===")
    logger.debug("\n[1] Input Parameters")
    logger.debug(f"Beta angle: {beta_angle} degrees")
    logger.debug(f"Orbit radius: {orbit_radius} km")
    logger.debug(f"Earth radius: {earth_radius} km")

    # 3D plot setup
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")

    # 軌道パラメータの計算
    _, _, _beta_rad, orbit_normal, e1, e2 = calculate_orbit_parameters(
        altitude,
        beta_angle,
    )

    # 軌道の計算（200点でサンプリング）
    num_points = 200
    theta = np.linspace(0, 2 * np.pi, num_points)
    r_vecs = np.outer(np.cos(theta), e1) * orbit_radius + np.outer(np.sin(theta), e2) * orbit_radius

    # 太陽方向ベクトル（慣性座標系で固定）
    sun_dir = np.array([1.0, 0.0, 0.0])
    s_hat = sun_dir / np.linalg.norm(sun_dir)

    # 蝕の判定
    r_dot_s = r_vecs @ s_hat
    perp = r_vecs - np.outer(r_dot_s, s_hat)
    d_perp = np.linalg.norm(perp, axis=1)
    eclipse_mask = (r_dot_s < 0) & (d_perp < earth_radius)

    logger.debug("\n[2] Orbit Analysis")
    logger.debug(f"Orbit normal: {orbit_normal}")
    logger.debug(f"Basis vector e1: {e1}")
    logger.debug(f"Basis vector e2: {e2}")
    logger.debug(f"Sun direction: {s_hat}")
    logger.debug(
        f"Angle between sun and orbit normal: {np.degrees(np.arccos(np.clip(np.dot(orbit_normal, s_hat), -1.0, 1.0))):.2f} degrees",
    )

    logger.debug("\n[3] Eclipse Statistics")
    logger.debug(f"Total points: {len(eclipse_mask)}")
    logger.debug(f"Eclipse points: {np.sum(eclipse_mask)}")
    logger.debug(f"Eclipse fraction: {np.sum(eclipse_mask) / len(eclipse_mask):.2%}")

    # Plot orbit
    ax.plot(r_vecs[:, 0], r_vecs[:, 1], r_vecs[:, 2], "r-", label="Orbit", linewidth=2)

    # Plot eclipse region
    ax.plot(
        r_vecs[eclipse_mask, 0],
        r_vecs[eclipse_mask, 1],
        r_vecs[eclipse_mask, 2],
        "k-",
        linewidth=4,
        label="Eclipse Region",
    )

    # Draw sun direction arrow
    sun_length = orbit_radius * 1.5
    ax.quiver(
        0,
        0,
        0,
        sun_dir[0] * sun_length,
        sun_dir[1] * sun_length,
        sun_dir[2] * sun_length,
        color="yellow",
        arrow_length_ratio=0.2,
        label="Sun Direction",
    )

    # Draw orbit normal arrow
    normal_length = orbit_radius * 0.5
    ax.quiver(
        0,
        0,
        0,
        orbit_normal[0] * normal_length,
        orbit_normal[1] * normal_length,
        orbit_normal[2] * normal_length,
        color="green",
        arrow_length_ratio=0.2,
        label="Orbit Normal",
    )

    # Draw Earth
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x = earth_radius * np.outer(np.cos(u), np.sin(v))
    y = earth_radius * np.outer(np.sin(u), np.sin(v))
    z = earth_radius * np.outer(np.ones(np.size(u)), np.cos(v))
    ax.plot_surface(x, y, z, color="blue", alpha=0.3)

    # Display information on plot
    beta_text = f"Beta Angle: {beta_angle:.1f}°"
    ax.text2D(
        0.02,
        0.98,
        beta_text,
        transform=ax.transAxes,
        bbox={"facecolor": "white", "alpha": 0.8},
    )

    alt_text = f"Orbit Altitude: {altitude:.1f} km"
    ax.text2D(
        0.02,
        0.93,
        alt_text,
        transform=ax.transAxes,
        bbox={"facecolor": "white", "alpha": 0.8},
    )

    eclipse_fraction = np.sum(eclipse_mask) / len(eclipse_mask)
    eclipse_text = f"Eclipse Fraction: {eclipse_fraction:.2%}"
    ax.text2D(
        0.02,
        0.88,
        eclipse_text,
        transform=ax.transAxes,
        bbox={"facecolor": "white", "alpha": 0.8},
    )

    # Graph settings
    ax.set_xlabel("X [km]")
    ax.set_ylabel("Y [km]")
    ax.set_zlabel("Z [km]")
    ax.set_title("Satellite Orbit Visualization")

    # Equal axis scale
    max_range = orbit_radius * 1.2
    ax.set_xlim([-max_range, max_range])
    ax.set_ylim([-max_range, max_range])
    ax.set_zlim([-max_range, max_range])

    # Show legend
    ax.legend(loc="upper right")

    # Save or display
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches="tight")
        plt.close()
    else:
        plt.show()
