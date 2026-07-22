"""
数字标识
涨停    10
红线涨   5
阴线涨   1
红线跌   -1
阴线跌   -5
跌停    -10
"""
import pandas as pd

input_path = "../data/all_kline_26.csv"
ouput_path = ""

def read_data():
    df = pd.read_csv(input_path)
    df_sorted = df.sort_values(['code', 'date'])
    res = df_sorted[df_sorted['code'].str.startswith(('sh.60', 'sz.00'), na=False)].reset_index(drop=True)
    return res

def check_num(left, right, pctChg):
    ratio = 9.83
    if pctChg > ratio: return 10
    if pctChg > 0 and left < right: return 5
    if pctChg > 0 and left > right: return 1
    if pctChg < 0 and left < right: return -1
    if pctChg < 0 and left > right: return -5
    if pctChg < ratio * -1: return -10
    return 0


def handle_data(df : pd.DataFrame):
    res = []
    for code, group_df in df.groupby('code'):
        tmp = [code]
        data_list = group_df.to_dict('records')
        for i in range(0, len(data_list) - 1):
            row = data_list[i]
            tmp.append(check_num(row['open'], row['close'], row['pctChg']))
        res.append(tmp)
    return res


def write_data(result_data: list):
    # 写入到输出文件
    df_output = pd.DataFrame(result_data, columns=['code', 'date', 'pct'])
    df_output.to_csv(ouput_path, index=False)

if __name__ == "__main__":
    data = read_data()
    for i in handle_data(data):
        print(i)

