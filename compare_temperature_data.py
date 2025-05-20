import pandas as pd
import os
import argparse
from pathlib import Path

def compare_temperature_data(td_file, output_file, output_dir='comparison'):
    """
    温度データを比較し、差分を計算してCSVファイルに出力する関数
    
    Args:
        td_file (str): comparison/td/配下のCSVファイルパス
        output_file (str): output/配下の解析結果フォルダ内のtemperature_data.csvファイルパス
        output_dir (str): 出力先ディレクトリ
    """
    # 入力ファイルの読み込み
    td_df = pd.read_csv(td_file)
    output_df = pd.read_csv(output_file)
    
    # カラム名の対応付け
    # tdファイルのカラム名をoutputファイルの形式に合わせる
    column_mapping = {
        'MAIN_PNL_PX.1': 'PX [°C]',
        'MAIN_PNL_MX.1': 'MX [°C]',
        'MAIN_PNL_PY.1': 'PY [°C]',
        'MAIN_PNL_MY.1': 'MY [°C]',
        'MAIN_PNL_PZ.1': 'PZ [°C]',
        'MAIN_PNL_MZ.1': 'MZ [°C]',
        'MAIN_PNL_MY.20001': 'MY_MLI [°C]'
    }
    td_df = td_df.rename(columns=column_mapping)
    
    # 時間カラムの対応付け
    td_df = td_df.rename(columns={'Times': 'Time [s]'})
    
    # 差分の計算
    diff_df = pd.DataFrame()
    diff_df['Time [s]'] = td_df['Time [s]']
    
    # 各ノードの温度差分を計算
    for col in output_df.columns:
        if col != 'Time [s]':
            diff_df[f'{col}_diff'] = abs(td_df[col] - output_df[col])
    
    # 出力ディレクトリの作成
    os.makedirs(output_dir, exist_ok=True)
    
    # 出力ファイル名の生成
    td_filename = Path(td_file).stem
    output_filename = Path(output_file).parent.name
    output_path = os.path.join(output_dir, f'diff_{td_filename}_vs_{output_filename}.csv')
    
    # 差分データの保存
    diff_df.to_csv(output_path, index=False)
    print(f'差分データを保存しました: {output_path}')

def main():
    parser = argparse.ArgumentParser(description='温度データを比較し、差分を計算してCSVファイルに出力します。')
    parser.add_argument('td_file', help='comparison/td/配下のCSVファイルパス')
    parser.add_argument('output_file', help='output/配下の解析結果フォルダ内のtemperature_data.csvファイルパス')
    parser.add_argument('--output-dir', default='comparison', help='出力先ディレクトリ（デフォルト: comparison）')
    
    args = parser.parse_args()
    compare_temperature_data(args.td_file, args.output_file, args.output_dir)

if __name__ == '__main__':
    main() 