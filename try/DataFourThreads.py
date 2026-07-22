"""
新浪财经API下载A股日K线数据 (akshare.stock_zh_a_daily)
数据源: https://finance.sina.com.cn (免费、稳定、字段齐全)

字段映射:
  新浪 turnover × 100 -> turn (换手率, 百分比)
  preclose = 前一日close (多取前缀日期保证首行有效)
  pctChg = (close - preclose) / preclose * 100

更新模式:
  FULL_REFRESH = False (默认) -> 增量更新: 只拉已有最新日期之后的新数据
  FULL_REFRESH = True          -> 全量重拉: 忽略已有数据从头拉 (每周/月数据校准用)
"""

import sys
from datetime import datetime
import akshare as ak
import pandas as pd
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_COLS = ['code', 'date', 'open', 'high', 'low', 'close',
               'preclose', 'volume', 'amount', 'turn', 'pctChg']
REQUEST_DELAY = 0.2
MAX_RETRY = 3
WORKER_COUNT = 10

TEMP_DIR = "../data/tmp_kline"
TARGET_FILE = "../data/all_kline_26.csv"

# 全量刷新开关: True=忽略已有数据全量重拉(数据校准); False=增量更新(默认)
# 注意: 切换复权方式后需先 FULL_REFRESH=True 全量重拉一次, 完成后改回 False
FULL_REFRESH = False
# 全量模式起始日期(保证2026-01-01首行有preclose)
FULL_START_DATE = "20251220"


def build_last_index(existing_file):
    """读取已有K线文件, 返回 {code: (last_date_str, last_close)}"""
    if not os.path.exists(existing_file):
        return {}
    try:
        df = pd.read_csv(existing_file, usecols=['code', 'date', 'close'],
                         dtype={'code': str})
    except Exception as e:
        print(f"读取已有文件失败, 走全量: {e}")
        return {}
    df = df.sort_values(['code', 'date'])
    idx = {}
    for code, g in df.groupby('code'):
        last = g.iloc[-1]
        idx[code] = (str(last['date']), float(last['close']))
    return idx


def get_latest_trade_date():
    """获取 <= 今天的最新交易日(YYYY-MM-DD), 用于跳过已是最新的票"""
    try:
        td = ak.tool_trade_date_hist_sina()
        dates = pd.to_datetime(td['trade_date']).dt.strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        latest = dates[dates <= today].max()
        print(f"最新交易日: {latest}")
        return latest
    except Exception as e:
        print(f"获取交易日历失败({e}), 用今天作为最新交易日")
        return datetime.now().strftime('%Y-%m-%d')


def download_stock_data(code_list, thread_name, last_index, latest_td):
    file_path = os.path.join(TEMP_DIR, f"{thread_name}.csv")
    end_date = datetime.now().strftime('%Y%m%d')
    fail_streak = 0
    success = 0
    skipped = 0

    for i, code in enumerate(code_list, 1):
        symbol = code.replace('.', '')

        # 决定起始日期 & 是否增量
        last_date, last_close = last_index.get(code, (None, None))

        # 已是最新交易日, 跳过(省掉 HTTP 请求)
        if last_date and latest_td and last_date >= latest_td:
            skipped += 1
            success += 1
            if skipped % 100 == 0:
                print(f"{thread_name}: 已跳过 {skipped} 只(已是最新)")
            continue

        if FULL_REFRESH or last_date is None:
            start_date = FULL_START_DATE
            is_incremental = False
        else:
            start_date = last_date.replace('-', '')
            is_incremental = True

        for attempt in range(MAX_RETRY):
            try:
                df = ak.stock_zh_a_daily(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )

                if df is None or df.empty:
                    fail_streak += 1
                    break

                df['date'] = df['date'].astype(str)
                df.sort_values('date', inplace=True)
                df.reset_index(drop=True, inplace=True)

                if is_incremental:
                    # 去掉已有最后一天, 只保留新数据
                    df = df[df['date'] > last_date]
                    if df.empty:
                        success += 1
                        print(f"{thread_name}: {i}/{len(code_list)} {code} (已是最新)")
                        fail_streak = 0
                        break
                    df.reset_index(drop=True, inplace=True)
                    # preclose: shift后首行为NaN, 用旧数据last_close补齐
                    df['preclose'] = df['close'].shift(1)
                    df.loc[df.index[0], 'preclose'] = last_close
                else:
                    df['preclose'] = df['close'].shift(1)

                df['pctChg'] = round(
                    (df['close'] - df['preclose']) / df['preclose'] * 100, 4)
                df = df[(df['date'] >= '2026-01-01') & df['preclose'].notna()]
                if df.empty:
                    break

                df['turn'] = df['turnover'] * 100
                df['code'] = code
                df = df[OUTPUT_COLS]

                need_header = not os.path.exists(file_path)
                df.to_csv(file_path, mode='a', index=False, header=need_header)

                success += 1
                print(f"{thread_name}: {i}/{len(code_list)} {code} (+{len(df)}行)")
                fail_streak = 0
                break

            except Exception as e:
                if attempt < MAX_RETRY - 1:
                    print(f"{thread_name}: {i}/{len(code_list)} {code} 重试{attempt+1} - {e}")
                    time.sleep(2 * (attempt + 1))
                else:
                    print(f"{thread_name}: {i}/{len(code_list)} {code} 失败 - {e}")
                    fail_streak += 1

        if fail_streak >= 5:
            print(f"{thread_name}: 连续{fail_streak}次失败, 等待10秒...")
            time.sleep(10)
            fail_streak = 0

        time.sleep(REQUEST_DELAY)

    return thread_name, success, len(code_list), skipped


def merge_temp_files():
    """合并临时文件, 按 (code,date) 去重, 返回 DataFrame 或 None"""
    all_dfs = []
    for f in sorted(os.listdir(TEMP_DIR)):
        if f.endswith('.csv'):
            all_dfs.append(pd.read_csv(os.path.join(TEMP_DIR, f), dtype={'code': str}))
    if not all_dfs:
        return None
    new_data = pd.concat(all_dfs, ignore_index=True)
    new_data.drop_duplicates(['code', 'date'], keep='last', inplace=True)
    return new_data


def cleanup_temp():
    if os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            os.remove(os.path.join(TEMP_DIR, f))
        os.rmdir(TEMP_DIR)


if __name__ == "__main__":
    df = pd.read_csv('../Data/stocks.csv')
    codes = df[
        df['code'].str.startswith('sh.60') | df['code'].str.startswith('sz.00')
    ]['code'].tolist()

    n = len(codes)

    # 建立已有数据索引
    if FULL_REFRESH:
        last_index = {}
        latest_td = None
        print(f"[全量模式] 共 {n} 只股票, {WORKER_COUNT}线程下载中...")
    else:
        last_index = build_last_index(TARGET_FILE)
        latest_td = get_latest_trade_date()
        print(f"[增量模式] 共 {n} 只股票, {WORKER_COUNT}线程, "
              f"已有数据覆盖 {len(last_index)} 只...")

    # 清理临时目录
    if os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            os.remove(os.path.join(TEMP_DIR, f))
    else:
        os.makedirs(TEMP_DIR)

    # 均分任务给各线程
    chunk_size = n // WORKER_COUNT + 1
    chunks = [(codes[i*chunk_size:(i+1)*chunk_size], f"T{i+1}")
              for i in range(WORKER_COUNT)]

    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
        futures = {
            executor.submit(download_stock_data, chunk, name, last_index, latest_td): name
            for chunk, name in chunks
        }
        for future in as_completed(futures):
            name, success, total, skipped = future.result()
            print(f"--- {name} 完成: 成功{success}/{total}, 跳过{skipped}只(已是最新) ---")

    # 合并临时文件
    new_data = merge_temp_files()
    if new_data is None:
        # 无任何新数据输出
        if FULL_REFRESH:
            print("\n下载失败!")
        else:
            print("\n本轮无新数据(已是最新交易日或全部命中已是最新)")
        cleanup_temp()
        sys.exit(0)

    print(f"\n本轮拉取: {len(new_data)}条, {new_data['code'].nunique()}只")

    if FULL_REFRESH:
        # 全量: 覆盖写, 保留原成功率校验
        if new_data['code'].nunique() >= n * 0.95:
            if os.path.exists(TARGET_FILE):
                os.remove(TARGET_FILE)
            new_data.sort_values(['code', 'date']).to_csv(
                TARGET_FILE, index=False, encoding='utf-8-sig')
            print(f"已保存(全量): {TARGET_FILE}")
            cleanup_temp()
        else:
            print(f"警告: 成功{new_data['code'].nunique()}只 < 预期{n*0.95:.0f}只, 保留临时文件不覆盖")
            print(f"临时目录: {TEMP_DIR}")
    else:
        # 增量: 读旧 + 拼新 + 去重 + 覆盖写
        if os.path.exists(TARGET_FILE):
            old = pd.read_csv(TARGET_FILE, dtype={'code': str})
            old_len = len(old)
            combined = pd.concat([old, new_data], ignore_index=True)
            combined.drop_duplicates(['code', 'date'], keep='last', inplace=True)
            combined.sort_values(['code', 'date'], inplace=True)
            combined.to_csv(TARGET_FILE, index=False, encoding='utf-8-sig')
            print(f"已保存(增量): 新增 {len(combined) - old_len}条, "
                  f"总计 {len(combined)}条 -> {TARGET_FILE}")
        else:
            new_data.sort_values(['code', 'date']).to_csv(
                TARGET_FILE, index=False, encoding='utf-8-sig')
            print(f"首次保存: {len(new_data)}条 -> {TARGET_FILE}")
        cleanup_temp()