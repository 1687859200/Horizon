"""
分析第六天开盘涨幅 vs 收盘涨幅的关系
找到所有"二连板→3连阴"信号，统计第六天的开盘/盘中/收盘表现
"""
import pandas as pd
import os
import sys

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2425
CSV_MAP = {
    2026: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline_26.csv'),
    2025: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline.csv'),
    2425: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline.csv'),
}
CSV_PATH = CSV_MAP.get(YEAR, CSV_MAP[2026])
LABEL = {2026: '2026', 2025: '2025', 2425: '2024-2025'}.get(YEAR, str(YEAR))

LIMIT_UP = 9.83

print(f"读取{YEAR}年数据...")
df = pd.read_csv(CSV_PATH)
df = df[df['code'].str.startswith(('sh.60', 'sz.00'), na=False)]
for col in ['open', 'high', 'low', 'close', 'pctChg']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df['date'] = pd.to_datetime(df['date'], errors='coerce')
if YEAR == 2025:
    df = df[df['date'].dt.year == 2025]
elif YEAR == 2425:
    pass
df.reset_index(drop=True, inplace=True)

records = []
for code, group in df.groupby('code'):
    rows = group.reset_index(drop=True)
    n = len(rows)
    for i in range(5, n):
        # 第1,2天涨停
        if rows.loc[i-5, 'pctChg'] < LIMIT_UP or rows.loc[i-4, 'pctChg'] < LIMIT_UP:
            continue
        # 第3,4,5天连续阴线
        if not (rows.loc[i-3, 'open'] > rows.loc[i-3, 'close']
                and rows.loc[i-2, 'open'] > rows.loc[i-2, 'close']
                and rows.loc[i-1, 'open'] > rows.loc[i-1, 'close']):
            continue

        day5 = rows.loc[i-1]
        day6 = rows.loc[i]

        # 第六天各项涨幅
        open_pct = (day6['open'] - day5['close']) / day5['close'] * 100  # 开盘涨幅(相对第5天收盘)
        close_pct = (day6['close'] - day5['close']) / day5['close'] * 100  # 收盘涨幅(相对第5天收盘)
        high_pct = (day6['high'] - day5['close']) / day5['close'] * 100  # 盘中最高(相对第5天收盘)
        intraday = (day6['close'] - day6['open']) / day6['open'] * 100  # 盘中涨幅(收盘-开盘)
        is_limit = day6['pctChg'] >= LIMIT_UP  # 是否涨停

        records.append({
            'code': code,
            'date': str(day6['date'])[:10],
            'open_pct': round(open_pct, 2),
            'close_pct': round(close_pct, 2),
            'high_pct': round(high_pct, 2),
            'intraday': round(intraday, 2),
            'is_limit': is_limit,
            'day5_close': day5['close'],
        })

tdf = pd.DataFrame(records)
total = len(tdf)
print(f"数据: {len(df)}行, {df['code'].nunique()}只")
print(f"符合二连板→3连阴信号: {total}条\n")

# ========== 基本统计 ==========
print(f"{'='*70}")
print(f"【第六天整体表现】(相对第5天收盘)")
print(f"{'='*70}")
print(f"  开盘涨幅: 均值{tdf['open_pct'].mean():+.2f}% | 中位{tdf['open_pct'].median():+.2f}%")
print(f"  收盘涨幅: 均值{tdf['close_pct'].mean():+.2f}% | 中位{tdf['close_pct'].median():+.2f}%")
print(f"  盘中最高: 均值{tdf['high_pct'].mean():+.2f}% | 中位{tdf['high_pct'].median():+.2f}%")
print(f"  盘中涨跌(收-开): 均值{tdf['intraday'].mean():+.2f}% | 中位{tdf['intraday'].median():+.2f}%")
print(f"  涨停数: {tdf['is_limit'].sum()}条 ({tdf['is_limit'].mean()*100:.1f}%)")
print(f"  收盘为红: {(tdf['intraday']>0).sum()}条 ({(tdf['intraday']>0).mean()*100:.1f}%)")
print(f"  收盘为绿: {(tdf['intraday']<0).sum()}条 ({(tdf['intraday']<0).mean()*100:.1f}%)")

# ========== 按开盘涨幅分档 ==========
print(f"\n{'='*70}")
print(f"【按第六天开盘涨幅分档 → 看收盘表现】")
print(f"{'='*70}")
print(f"  {'开盘涨幅':<16} {'数量':>5} {'涨停数':>5} {'收盘均值':>9} {'盘中涨均值':>10} {'收盘为红':>8}")
print("  " + "-" * 60)

bins = [(-99, -5, '低开<-5%'), (-5, -3, '低开-5%~-3%'), (-3, -1, '低开-3%~-1%'),
        (-1, 0, '低开-1%~0%'), (0, 1, '高开0%~+1%'), (1, 2, '高开+1%~+2%'),
        (2, 3, '高开+2%~+3%'), (3, 5, '高开+3%~+5%'), (5, 99, '高开>+5%')]

for lo, hi, label in bins:
    sub = tdf[(tdf['open_pct'] >= lo) & (tdf['open_pct'] < hi)]
    if len(sub) == 0:
        continue
    limit_n = sub['is_limit'].sum()
    red_rate = (sub['intraday'] > 0).mean() * 100
    print(f"  {label:<16} {len(sub):>5} {limit_n:>5} {sub['close_pct'].mean():>+8.2f}% {sub['intraday'].mean():>+9.2f}% {red_rate:>6.0f}%")

# ========== 开盘≥+2%的详细分析 ==========
print(f"\n{'='*70}")
print(f"【如果以开盘价买入(开盘≥+2%的情况)】")
print(f"{'='*70}")
gap2 = tdf[tdf['open_pct'] >= 2]
if len(gap2) > 0:
    # 以开盘价买入, 到收盘的收益
    gap2_return = gap2['intraday']  # 收盘-开盘
    print(f"  开盘≥+2%: {len(gap2)}条 ({len(gap2)/total*100:.1f}%)")
    print(f"  涨停: {gap2['is_limit'].sum()}条 ({gap2['is_limit'].mean()*100:.1f}%)")
    print(f"  以开盘价买入到收盘: 均值{gap2_return.mean():+.2f}% | 中位{gap2_return.median():+.2f}%")
    print(f"  正收益: {(gap2_return>0).sum()}条 ({(gap2_return>0).mean()*100:.1f}%)")
    print(f"  收盘≥+2%(相对开盘): {(gap2['intraday']>=2).sum()}条 ({(gap2['intraday']>=2).mean()*100:.1f}%)")

# ========== 买入价≤30过滤后的统计 ==========
print(f"\n{'='*70}")
print(f"【买入价≤30元过滤后】")
print(f"{'='*70}")
tdf2 = tdf[tdf['day5_close'] <= 30]
total2 = len(tdf2)
print(f"  符合条件: {total2}条 (总{total}条)")
print(f"  开盘涨幅: 均值{tdf2['open_pct'].mean():+.2f}%")
print(f"  收盘涨幅: 均值{tdf2['close_pct'].mean():+.2f}%")
print(f"  涨停数: {tdf2['is_limit'].sum()}条 ({tdf2['is_limit'].mean()*100:.1f}%)")
print(f"  收盘≥+2%(相对开盘): {(tdf2['intraday']>=2).sum()}条")

print(f"\n  {'开盘涨幅':<16} {'数量':>5} {'涨停':>5} {'收盘均值':>9} {'盘中涨均值':>10}")
print("  " + "-" * 50)
for lo, hi, label in bins:
    sub = tdf2[(tdf2['open_pct'] >= lo) & (tdf2['open_pct'] < hi)]
    if len(sub) == 0:
        continue
    limit_n = sub['is_limit'].sum()
    print(f"  {label:<16} {len(sub):>5} {limit_n:>5} {sub['close_pct'].mean():>+8.2f}% {sub['intraday'].mean():>+9.2f}%")
