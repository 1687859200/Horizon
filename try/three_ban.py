"""
三连

"""
import pandas as pd

input_path = "../data/all_kline_26.csv"
ouput_path = ""

ratio = 9.83

def read_data():
    df = pd.read_csv(input_path)
    df_sorted = df.sort_values(['code', 'date'])
    res = df_sorted[df_sorted['code'].str.startswith(('sh.60', 'sz.00'), na=False)].reset_index(drop=True)
    return res


def handle_data(df : pd.DataFrame):
    res = []
    for code, group_df in df.groupby('code'):
        Flag = 0    # Todo 5及以上风险极高,需调整多次
        data_list = group_df.to_dict('records')
        for i in range(0, len(data_list) - 3):
            row = data_list[i]
            if row['pctChg'] > ratio:
                Flag += 1
                continue
            if Flag in (3, 4):
                B = data_list[i+1]['open']
                S = data_list[i+3]['close']
                down_ratio = round((row['close'] - row['open']) / row['open'] * 100, 2)
                open_ratio = round((B - row['close']) / row['close'] * 100, 2)
                vol_ratio = round(row['volume'] / data_list[i-1]['volume'], 2)
                if open_ratio > -8 and vol_ratio > 1 and down_ratio > 0 and data_list[i+1]['pctChg'] > ratio * -1:
                    res.append([row['code'], row['date'], Flag, row['pctChg'], down_ratio, open_ratio, vol_ratio, round((S - B) / B * 100, 2)])
            Flag = 0
    return res

def find_data(df : pd.DataFrame):
    res = []
    for code, group_df in df.groupby('code'):
        data_list = group_df.to_dict('records')
        for i in range(2, len(data_list)):
            row = data_list[i]
            if data_list[i-2]['pctChg'] > ratio and data_list[i-1]['pctChg'] > ratio and row['pctChg'] > ratio:
                res.append([row['code'], row['date']])
                break
    return res

def print_res(result_data: list):
    total, success = 0, 0
    for i in sorted(result_data, key=lambda x: x[-1], reverse=False):
        print(i)
        total += i[-1]
        if i[-1] > 0:
            success += 1
    print(len(result_data), success, total)



def write_data(result_data: list):
    # 写入到输出文件
    df_output = pd.DataFrame(result_data, columns=['code', 'date', 'pct'])
    df_output.to_csv(ouput_path, index=False)

if __name__ == "__main__":
    data = read_data()
    result = handle_data(data)
    # result = find_data(data)
    print_res(result)
