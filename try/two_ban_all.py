"""
二连
1.一板及二板巨量
2.一板巨量或二板翻量
3.涨三连调(2板前提)
"""
import pandas as pd

input_path = "../data/all_kline_26.csv"
ouput_path = ""

ratio = 9.83

def read_data():
    df = pd.read_csv(input_path)
    df_sorted = df.sort_values(['code', 'date'])
    res = df_sorted[df_sorted['code'].str.startswith(('sh.60', 'sz.00'), na=False)].reset_index(drop=True)
    # return res[res['code'].isin(['sh.600488'])]
    return res

def handle_income(B, S):
    return round((S - B) / B * 100, 1)

def find_data(df : pd.DataFrame):
    res = []
    for code, group_df in df.groupby('code'):
        data_list = group_df.to_dict('records')
        for i in range(2, len(data_list)):
            row = data_list[i]
            if row['pctChg'] > ratio and data_list[i - 1]['pctChg'] > ratio and data_list[i - 2]['pctChg'] > ratio:
                # if row['close'] < 23:
                res.append([row['code'], row['date'], row['close']])
    return res


def find_1(df: pd.DataFrame):
    res = []
    for code, group_df in df.groupby('code'):
        data_list = group_df.to_dict('records')
        for i in range(2, len(data_list) - 3):
            row = data_list[i]
            # if row['date'] == "2026-03-30":
            #     print(data_list[i - 2]['pctChg'], data_list[i - 1]['pctChg'],row['pctChg'],data_list[i - 1]['volume'] / data_list[i - 2]['volume'],row['volume'] / data_list[i - 1]['volume'])
            if (data_list[i - 2]['pctChg'] < ratio and data_list[i - 1]['pctChg'] > ratio and row['pctChg'] > ratio
                and data_list[i - 1]['volume'] / data_list[i - 2]['volume'] > 3
                    and row['volume'] / data_list[i - 1]['volume'] > 2):
                res.append([row['code'], row['date'], handle_income(data_list[i+1]['open'], data_list[i+2]['close']),
                            round(data_list[i - 1]['volume'] / data_list[i - 2]['volume']*row['volume'] / data_list[i - 1]['volume'],2)])
    return res

def find_2(df: pd.DataFrame):
    res = []
    for code, group_df in df.groupby('code'):
        data_list = group_df.to_dict('records')
        for i in range(2, len(data_list) - 3):
            row = data_list[i]
            if row['pctChg'] > ratio and data_list[i - 1]['pctChg'] > ratio and data_list[i - 2]['pctChg'] < ratio:
                if data_list[i - 1]['volume'] / data_list[i - 2]['volume'] > 3: #row['volume'] / data_list[i - 1]['volume'] > 2
                    res.append([row['code'], row['date'], round(data_list[i + 1]['pctChg']+data_list[i+2]['pctChg'], 1)])
    return res

def find_3(df: pd.DataFrame):
    res = []
    for code, group_df in df.groupby('code'):
        flag = 0
        data_list = group_df.to_dict('records')
        for i in range(1, len(data_list) - 5):
            row = data_list[i]
            if data_list[i - 1]['pctChg'] > ratio and row['pctChg'] > ratio:
                flag = 5
            elif flag > 0 and (data_list[i - 1]['pctChg'] > ratio and row['open'] >= row['close'] and data_list[i+1]['open'] >= data_list[i+1]['close']
                    and data_list[i+2]['open'] >= data_list[i+2]['close']):
                res.append([row['code'], row['date'], handle_income(data_list[i+3]['open'], data_list[i+4]['close'])])
            flag -= 1
    return res

def find_3_day(df: pd.DataFrame):
    for code, group_df in df.groupby('code'):
        data_list = group_df.to_dict('records')
        if (len(data_list) > 5 and data_list[-4]['pctChg'] > ratio and data_list[-3]['open'] >= data_list[-3]['close']
            and data_list[-2]['open'] >= data_list[-2]['close'] and data_list[-1]['open'] >= data_list[-1]['close']):
            print(code)


def write_data(result_data: list):
    # 写入到输出文件
    df_output = pd.DataFrame(result_data, columns=['code', 'date', 'pct'])
    df_output.to_csv(ouput_path, index=False)


def print_res(result_data: list):
    total, success = 0, 0
    for i in sorted(result_data, key=lambda x: x[0], reverse=False):
        print(i)
        total += i[2]
        if i[2] > 0:
            success += 1
    print(len(result_data), success, total)


if __name__ == "__main__":
    data = read_data()
    # result = find_data(data)
    result = find_3(data)
    print_res(result)


    # find_3_day(data)

