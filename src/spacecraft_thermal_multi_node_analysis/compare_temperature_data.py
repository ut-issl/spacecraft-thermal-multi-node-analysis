import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from rich.logging import RichHandler

logger = logging.getLogger(__name__)


def calculate_rmse(diff_df: pd.DataFrame) -> dict[str, float]:
    """各ノードの時間平均RMSEを計算する関数

    Args:
        diff_df (pd.DataFrame): 差分データのDataFrame

    Returns:
        Dict[str, float]: 各ノードのRMSE

    """
    rmse_dict = {}
    for col in diff_df.columns:
        if col.endswith("_diff"):
            # RMSE = sqrt(mean(squared_diff))
            rmse = np.sqrt(np.mean(diff_df[col] ** 2))
            rmse_dict[col.replace("_diff", "")] = rmse
    return rmse_dict


def write_rmse_log(log_file: str, td_file: str, output_file: str, rmse_dict: dict[str, float]):
    """RMSEの結果をログファイルに記録する関数

    Args:
        log_file (str): ログファイルのパス
        td_file (str): 比較元ファイルのパス
        output_file (str): 比較先ファイルのパス
        rmse_dict (Dict[str, float]): 各ノードのRMSE

    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n=== 比較実行時刻: {timestamp} ===\n")
        f.write(f"比較元: {td_file}\n")
        f.write(f"比較先: {output_file}\n")
        f.write("各ノードの時間平均RMSE [°C]:\n")
        f.writelines(f"  {node}: {rmse:.6f}\n" for node, rmse in rmse_dict.items())
        f.write("-" * 50 + "\n")


def compare_temperature_data(td_file: str, output_file: str, output_dir: str = "comparison") -> str:
    """温度データを比較し、差分を計算してCSVファイルに出力する関数

    Args:
        td_file (str): comparison/td/配下のCSVファイルパス
        output_file (str): output/配下の解析結果フォルダ内のtemperature_data.csvファイルパス
        output_dir (str): 出力先ディレクトリ

    Returns:
        str: 出力ファイルのパス

    """
    # 入力ファイルの読み込み
    td_df = pd.read_csv(td_file)
    output_df = pd.read_csv(output_file)

    # カラム名の対応付け
    # tdファイルのカラム名をoutputファイルの形式に合わせる
    column_mapping = {
        "MAIN_PNL_PX.1": "PX [°C]",
        "MAIN_PNL_MX.1": "MX [°C]",
        "MAIN_PNL_PY.1": "PY [°C]",
        "MAIN_PNL_MY.1": "MY [°C]",
        "MAIN_PNL_PZ.1": "PZ [°C]",
        "MAIN_PNL_MZ.1": "MZ [°C]",
        "MAIN_PNL_MY.20001": "MY_MLI [°C]",
    }
    td_df = td_df.rename(columns=column_mapping)

    # 時間カラムの対応付け
    td_df = td_df.rename(columns={"Times": "Time [s]"})

    # 差分の計算
    diff_df = pd.DataFrame()
    diff_df["Time [s]"] = td_df["Time [s]"]

    # 各ノードの温度差分を計算
    for col in output_df.columns:
        if col != "Time [s]":
            diff_df[f"{col}_diff"] = abs(td_df[col] - output_df[col])

    # 出力ディレクトリの作成
    os.makedirs(output_dir, exist_ok=True)

    # 出力ファイル名の生成
    td_filename = Path(td_file).stem
    output_filename = Path(output_file).parent.name
    output_path = os.path.join(output_dir, f"diff_{td_filename}_vs_{output_filename}.csv")

    # 差分データの保存
    diff_df.to_csv(output_path, index=False)
    logger.info(f"差分データを保存しました: {output_path}")

    # RMSEの計算とログ記録
    rmse_dict = calculate_rmse(diff_df)
    log_file = os.path.join(output_dir, "comparison_rmse.log")
    write_rmse_log(log_file, td_file, output_file, rmse_dict)
    logger.info(f"RMSEの結果をログに記録しました: {log_file}")

    return output_path


def load_comparison_config(config_file: str) -> list[dict[str, str]]:
    """比較設定を読み込む関数

    Args:
        config_file (str): 比較設定CSVファイルのパス

    Returns:
        List[Dict[str, str]]: 比較設定のリスト

    """
    config_df = pd.read_csv(config_file)
    required_columns = ["td_file", "output_file"]

    # 必須カラムの存在確認
    if not all(col in config_df.columns for col in required_columns):
        raise ValueError(f"設定ファイルには以下のカラムが必要です: {required_columns}")

    # 設定を辞書のリストに変換
    configs = config_df.to_dict("records")
    return configs


def batch_compare(config_file: str, output_dir: str = "comparison") -> list[str]:
    """複数の比較を一括実行する関数

    Args:
        config_file (str): 比較設定CSVファイルのパス
        output_dir (str): 出力先ディレクトリ

    Returns:
        List[str]: 出力ファイルのパスのリスト

    """
    # 設定の読み込み
    configs = load_comparison_config(config_file)

    # 各設定に対して比較を実行
    output_paths = []
    for config in configs:
        try:
            output_path = compare_temperature_data(config["td_file"], config["output_file"], output_dir)
            output_paths.append(output_path)
        except Exception as e:
            logger.exception(
                f"エラー: {config['td_file']} と {config['output_file']} の比較中にエラーが発生しました: {e!s}",
            )

    return output_paths


def create_config_template(output_file: str = "comparison_config_template.csv"):
    """比較設定のテンプレートファイルを作成する関数

    Args:
        output_file (str): 出力ファイルのパス

    """
    template_df = pd.DataFrame(
        {"td_file": ["comparison/test/example.csv"], "output_file": ["output/example/temperature_data.csv"]},
    )
    template_df.to_csv(output_file, index=False)
    logger.info(f"設定テンプレートを作成しました: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="温度データを比較し、差分を計算してCSVファイルに出力します。")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細なログを表示")

    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")

    # 単一の比較を実行するコマンド
    single_parser = subparsers.add_parser("single", help="単一の比較を実行")
    single_parser.add_argument("td_file", help="comparison/td/配下のCSVファイルパス")
    single_parser.add_argument("output_file", help="output/配下の解析結果フォルダ内のtemperature_data.csvファイルパス")
    single_parser.add_argument(
        "--output-dir",
        default="comparison",
        help="出力先ディレクトリ（デフォルト: comparison）",
    )

    # 複数の比較を一括実行するコマンド
    batch_parser = subparsers.add_parser("batch", help="複数の比較を一括実行")
    batch_parser.add_argument("config_file", help="比較設定CSVファイルのパス")
    batch_parser.add_argument("--output-dir", default="comparison", help="出力先ディレクトリ（デフォルト: comparison）")

    # 設定テンプレートを作成するコマンド
    template_parser = subparsers.add_parser("create-template", help="比較設定のテンプレートファイルを作成")
    template_parser.add_argument(
        "--output-file",
        default="comparison_config_template.csv",
        help="出力ファイルのパス（デフォルト: comparison_config_template.csv）",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    pkg_handler = RichHandler(level=log_level)
    pkg_logger = logging.getLogger("spacecraft_thermal_multi_node_analysis")
    pkg_logger.setLevel(log_level)
    pkg_logger.addHandler(pkg_handler)
    pkg_logger.propagate = False

    if args.command == "single":
        compare_temperature_data(args.td_file, args.output_file, args.output_dir)
    elif args.command == "batch":
        batch_compare(args.config_file, args.output_dir)
    elif args.command == "create-template":
        create_config_template(args.output_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
