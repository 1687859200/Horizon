"""
板，次日开盘0.01及以内
B: 35, 40存在承接
S: 5%出一半，后续5日均线走；低于5%，开盘直接出
"""
import pandas as pd

input_path = "../data/all_kline_26.csv"
ouput_path = ""

def read_data():
    df = pd.read_csv(input_path)
    df_sorted = df.sort_values(['code', 'date'])
    res = df_sorted[df_sorted['code'].str.startswith(('sh.60', 'sz.00'), na=False)].reset_index(drop=True)
    return res


def handle_data(df : pd.DataFrame):

    res = []

    for code, group_df in df.groupby('code'):
        data_list = group_df.to_dict('records')
        flag = 0
        for i in range(0, len(data_list) - 2):
            row = data_list[i]
            if row['pctChg'] > 9.9:
                flag += 1
                if abs(row['close'] - data_list[i + 1]['open']) < 0.02:
                    res.append([row['code'], row['date'], row['close'], data_list[i + 1]['open'], data_list[i + 1]['pctChg'],flag])
            else:
                flag = 0
    return res



def write_data(result_data: list):
    # 写入到输出文件
    df_output = pd.DataFrame(result_data, columns=['code', 'date', 'pct'])
    df_output.to_csv(ouput_path, index=False)

def print_res(result_data: list):
    total, success, total_num = 0, 0, 0
    for i in sorted(result_data, key=lambda x: x[1], reverse=False):
        if str(i[4]) != 'nan' and round(i[3] - i[2], 2) == 0.01:
            print(i)
            total_num += 1
            total += i[4]
            if i[4] > 0:
                success += 1

    print(total, success, total_num)

if __name__ == "__main__":
    data = read_data()
    res = handle_data(data)
    print_res(res)