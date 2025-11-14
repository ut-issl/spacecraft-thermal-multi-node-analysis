import os.path
from pathlib import Path

import pandas as pd
import pytest
from rich import print  # noqa: A004

import spacecraft_thermal_multi_node_analysis as stmna
from spacecraft_thermal_multi_node_analysis.utils.config_loader import load_constants
from spacecraft_thermal_multi_node_analysis.utils.satellite_config import SatelliteConfiguration


@pytest.fixture
def settings_dir(datadir: Path) -> Path:
    return datadir / "settings"


@pytest.fixture
def ref_satellite_config(settings_dir: Path) -> SatelliteConfiguration:
    return SatelliteConfiguration.from_config_files(str(settings_dir))


@pytest.fixture
def constants(settings_dir: Path) -> dict:
    return load_constants(str(settings_dir))


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    path = tmp_path / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def ref_output_dir(datadir: Path) -> Path:
    return datadir / "output"


def test_run_earth_orbit_analysis(
    constants: dict,
    ref_satellite_config: SatelliteConfiguration,
    output_dir: Path,
    ref_output_dir: Path,
) -> None:
    from spacecraft_thermal_multi_node_analysis.multi_node_analysis import create_satellite_surfaces
    from spacecraft_thermal_multi_node_analysis.utils.plotting_utils import (
        save_heat_input_data,
        save_temperature_data,
    )
    from spacecraft_thermal_multi_node_analysis.utils.thermal_utils import ThermalNode

    times, temperatures, heat_input_records, _eclipse_flags = stmna.run_earth_orbit_analysis(
        config=ref_satellite_config,
        altitude=600.0,
        beta_angle=0.0,
        constants=constants,
        duration=3600.0,
    )
    # ビューファクター行列（Rij）をCSV出力
    node_for_vf = ThermalNode(
        initial_temp=constants["analysis_parameters"]["initial_temperature"],
        dimensions=constants["satellite_dimensions"],
    )
    for surface in create_satellite_surfaces(ref_satellite_config, constants):
        node_for_vf.add_surface(surface)
    vf_csv_path = os.path.join(output_dir, "view_factor_matrix.csv")
    node_for_vf.view_factor_matrix.to_csv(vf_csv_path)
    # RijマトリクスもCSV出力
    node_for_vf.save_rij_matrix(str(output_dir))

    # 結果のプロットと保存
    save_temperature_data(times, temperatures, str(output_dir))
    save_heat_input_data(heat_input_records, str(output_dir))

    for filename in ("heat_input_data.csv", "rij_matrix.csv", "temperature_data.csv", "view_factor_matrix.csv"):
        print(f"Comparing file: {filename}")
        output_file = output_dir / filename
        ref_file = ref_output_dir / filename
        assert output_file.exists(), f"{output_file} does not exist."
        df_output = pd.read_csv(output_file)
        df_ref = pd.read_csv(ref_file)
        pd.testing.assert_frame_equal(df_output, df_ref, atol=1e-6)
