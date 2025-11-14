import argparse
import logging
import os
import subprocess
from datetime import datetime

import pandas as pd
from rich.logging import RichHandler

logger = logging.getLogger(__name__)


def create_analysis_config_template(output_file: str = "analysis_config_template.csv"):
    """解析設定のテンプレートファイルを作成する関数

    Args:
        output_file (str): 出力ファイルのパス

    """
    template_df = pd.DataFrame(
        {
            "mode": ["earth"],  # earth または deep_space
            "altitude": [500.0],  # 地球周回軌道の場合のみ使用 [km]
            "beta": [60.0],  # 地球周回軌道の場合のみ使用 [度]
            "sun_x": [None],  # 深宇宙の場合のみ使用
            "sun_y": [None],  # 深宇宙の場合のみ使用
            "sun_z": [None],  # 深宇宙の場合のみ使用
            "duration": [40010.0],  # 解析時間 [秒]
            "num_orbits": [None],  # 周回数（指定時はdurationより優先）
            "temp_grid_interval": [5.0],  # 温度データの出力間隔 [秒]
            "output_dir": ["output"],  # 出力ディレクトリ
        },
    )
    template_df.to_csv(output_file, index=False)
    logger.info(f"解析設定テンプレートを作成しました: {output_file}")


def load_analysis_config(config_file: str) -> list[dict]:
    """解析設定を読み込む関数

    Args:
        config_file (str): 解析設定CSVファイルのパス

    Returns:
        List[Dict]: 解析設定のリスト

    """
    config_df = pd.read_csv(config_file)
    required_columns = ["mode", "duration", "output_dir"]

    # 必須カラムの存在確認
    if not all(col in config_df.columns for col in required_columns):
        raise ValueError(f"設定ファイルには以下のカラムが必要です: {required_columns}")

    # 設定を辞書のリストに変換
    configs = config_df.to_dict("records")
    return configs


def write_analysis_log(log_file: str, config: dict, status: str, error_msg: str | None = None):
    """解析実行のログを記録する関数

    Args:
        log_file (str): ログファイルのパス
        config (Dict): 解析設定
        status (str): 実行状態（'success' または 'error'）
        error_msg (str, optional): エラーメッセージ

    """
    # ログファイルのパスを絶対パスに変換
    log_file = os.path.abspath(log_file)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n=== 解析実行時刻: {timestamp} ===\n")
        f.write(f"モード: {config['mode']}\n")
        if config["mode"] == "earth":
            f.write(f"軌道高度: {config['altitude']} km\n")
            f.write(f"ベータ角: {config['beta']} 度\n")
        else:
            f.write(f"太陽方向ベクトル: [{config['sun_x']}, {config['sun_y']}, {config['sun_z']}]\n")
        f.write(f"解析時間: {config['duration']} 秒\n")
        if pd.notna(config.get("num_orbits")):
            f.write(f"周回数: {config['num_orbits']}\n")
        f.write(f"温度データ出力間隔: {config['temp_grid_interval']} 秒\n")
        f.write(f"出力ディレクトリ: {config['output_dir']}\n")
        f.write(f"実行状態: {status}\n")
        if error_msg:
            f.write(f"エラー: {error_msg}\n")
        f.write("-" * 50 + "\n")


def execute_analysis(config: dict, log_file: str) -> bool:
    """単一の解析を実行する関数

    Args:
        config (Dict): 解析設定
        log_file (str): ログファイルのパス

    Returns:
        bool: 実行が成功したかどうか

    """
    # コマンドライン引数の構築
    cmd = ["multi-node-analysis"]

    # モードに応じた引数の設定
    cmd.extend(["--mode", config["mode"]])

    if config["mode"] == "earth":
        cmd.extend(["--altitude", str(config["altitude"])])
        cmd.extend(["--beta", str(config["beta"])])
    else:  # deep_space
        cmd.extend(["--sun_x", str(config["sun_x"])])
        cmd.extend(["--sun_y", str(config["sun_y"])])
        cmd.extend(["--sun_z", str(config["sun_z"])])

    # 共通の引数
    if pd.notna(config.get("num_orbits")):
        cmd.extend(["--num_orbits", str(config["num_orbits"])])
    else:
        cmd.extend(["--duration", str(config["duration"])])

    cmd.extend(["--temp-grid-interval", str(config["temp_grid_interval"])])
    cmd.extend(["--output_dir", config["output_dir"]])

    try:
        # 解析の実行
        _result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        write_analysis_log(log_file, config, "success")
        logger.info(f"解析が成功しました: {config['output_dir']}")
        return True
    except subprocess.CalledProcessError as e:
        error_msg = f"コマンド実行エラー: {e.stderr}"
        write_analysis_log(log_file, config, "error", error_msg)
        logger.info(f"エラー: {config['output_dir']} の解析中にエラーが発生しました: {error_msg}")
        return False


def batch_analysis(config_file: str, log_file: str = "analysis_log.log"):
    """複数の解析を一括実行する関数

    Args:
        config_file (str): 解析設定CSVファイルのパス
        log_file (str): ログファイルのパス

    """
    # 設定の読み込み
    configs = load_analysis_config(config_file)

    # 各設定に対して解析を実行
    success_count = 0
    for config in configs:
        if execute_analysis(config, log_file):
            success_count += 1

    # 実行結果のサマリー
    logger.info(f"解析実行完了: {success_count}/{len(configs)} 成功")


def main():
    parser = argparse.ArgumentParser(description="複数の解析条件を一括実行します。")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="詳細なログを表示します。",
    )
    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")

    # 解析設定のテンプレートを作成するコマンド
    template_parser = subparsers.add_parser("create-template", help="解析設定のテンプレートファイルを作成")
    template_parser.add_argument(
        "--output-file",
        default="analysis_config_template.csv",
        help="出力ファイルのパス（デフォルト: analysis_config_template.csv）",
    )

    # 複数の解析を一括実行するコマンド
    batch_parser = subparsers.add_parser("batch", help="複数の解析を一括実行")
    batch_parser.add_argument("config_file", help="解析設定CSVファイルのパス")
    batch_parser.add_argument(
        "--log-file",
        default=os.path.join(os.getcwd(), "analysis_log.log"),
        help="ログファイルのパス（デフォルト: ./analysis_log.log）",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    pkg_handler = RichHandler(level=log_level)
    pkg_logger = logging.getLogger("spacecraft_thermal_multi_node_analysis")
    pkg_logger.setLevel(log_level)
    pkg_logger.addHandler(pkg_handler)
    pkg_logger.propagate = False

    if args.command == "create-template":
        create_analysis_config_template(args.output_file)
    elif args.command == "batch":
        batch_analysis(args.config_file, args.log_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
