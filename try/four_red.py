"""
four_red
v1: (+_ 0.01)开
"""
import pandas as pd

input_path = "../data/all_kline_26.csv"
ouput_path = "../data/four_red_v1.csv"

def read_data():
    df = pd.read_csv(input_path)
    df_sorted = df.sort_values(['code', 'date'])
    res = df_sorted[df_sorted['code'].str.startswith(('sh.60', 'sz.00'), na=False)].reset_index(drop=True)
    return res

def handle_data(data):
    code = data['code']
    date = data['date']