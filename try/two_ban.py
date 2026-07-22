"""
二连
v1: 所有数据
v2: 优化S策略，重排序，除去开盘-9以下的
V3: 最强势
"""
import pandas as pd

input_path = "../data/all_kline_26.csv"
ouput_path = "../data/two_ban_v2.csv"

def read_data():
    df = pd.read_csv(input_path)
    df_sorted = df.sort_values(['code', 'date'])
    res = df_sorted[df_sorted['code'].str.startswith(('sh.60', 'sz.00'), na=False)].reset_index(drop=True)
    return res

def check_strategy(left, right):
    # TOdo 上影线；多次涨停高位；
    # 绿柱与红柱有交集
    if left[0] <= right[0] <= left[1] or left[0] <= right[1] <= left[1]:
        return True
    return False

def check_die(row):
    if row['open'] == row['close'] and row['pctChg'] < -9:
        return True
    return False

def get_income(first, second):
    B = first['open']
    H = second['high']
    S = second['close']
    if (H - B) / B > 0.095:
        income = 0.5 * B * 1.095 + 0.5 * S
        return (income - B) / B
    return (S - B) / B

def handle_data(df : pd.DataFrame):

    res = []

    for code, group_df in df.groupby('code'):

        flag = False
        index_day = 0
        weight = 0
        weight_list = []

        data_list = group_df.to_dict('records')

        for i in range(2, len(data_list) - 1):
            row = data_list[i]

            if not flag:
                if data_list[i-2]['pctChg'] < 9.8 and data_list[i-1]['pctChg'] >= 9.8 and row['pctChg'] >= 9.8 and data_list[i+1]['pctChg'] < 9.8:
                    flag = True
                    continue
            if flag:
                index_day += 1

                # TOdo 首阴

                # V3
                # 触及涨停
                if row['open'] <= row['close'] and not check_die(row):
                    O = data_list[i - 1]['close']
                    if (row['high'] - O) / O > 0.098:
                    # if (row['high'] - row['open']) / row['open'] > 0.098:
                        weight += 1
                        weight_list.append(row['date'])
                else:
                    if i < len(data_list) - 4 and not check_die(data_list[i + 1]):
                        B = data_list[i + 1]['open']
                        S = data_list[i + 4]['close']
                        r = (B - row['close']) / row['close']
                        if r < 0.04:
                            res.append([row['code'], row['date'], round((S-B)/B * 100, 2), weight, weight_list, round(r* 100, 2)])
                    flag = False
                    weight = 0
                    weight_list = []

        # Todo 每日选择
        # if flag:
        #     print(code, weight, weight_list)

                # V2
                # if row['open'] > row['close']:
                #     B = data_list[i + 1]['open']
                #     r1 = (B - row['close']) / row['close']
                #     if i < len(data_list) - 4 and r1 > -0.09: # and row['close'] > data_list[i - 1]['close']:
                #         income = get_income(data_list[i + 1], data_list[i + 2])
                #         res.append([row['code'], row['date'], round(income* 100, 2)])
                #     flag = False

                # 涨幅小于0，且收盘小于开盘
                # if row['pctChg'] <= 0 and row['close'] <= row['open']:
                #     right_range = [row['open'], row['close'], row['low'], row['high']]
                #     if check_strategy(left_range, right_range):
                #         r1 = (data_list[i+1]['open'] - row['close']) / row['close']
                #         # 次日开盘高于-8%
                #         if r1 >= -0.08 and index_day > 2:
                #             res.append([row['code'], row['date'], left_range[0], left_range[1], row['close'], row['open'], data_list[i+1]['pctChg']])
                #     flag = False
    return res

def write_data(result_data: list):
    # 写入到输出文件
    df_output = pd.DataFrame(result_data, columns=['code', 'date', 'pct'])
    df_output.to_csv(ouput_path, index=False)

def print_res(result_data: list):
    total, success, total_num = 0, 0, 0
    for i in sorted(result_data, key=lambda x: x[1], reverse=False):
        if str(i[2]) != 'nan' and i[3] > 0:
            print(i)
            total_num += 1
            total += i[2]
            if i[2] > 0:
                success += 1

    print(total, success, total_num)

if __name__ == "__main__":
    data = read_data()
    result = handle_data(data)
    # write_data(sorted(result, key=lambda x: x[2], reverse=False))
    print_res(result)

