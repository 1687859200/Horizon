"""
首板断板红K延续:
第1天首次涨停 → 第2天断板红K(不涨停) → 第3天红K(不涨停) → 第4天涨幅统计
"""
import pandas as pd
import numpy as np
import os
import sys

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
LABEL = {2026: '2026', 2025: '2025', 2425: '2024-2025'}.get(YEAR, str(YEAR))
CSV_MAP = {
    2026: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline_26.csv'),
    2025: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline.csv'),
    2425: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline.csv'),
}
CSV_PATH = CSV_MAP.get(YEAR, CSV_MAP[2026])
LIMIT_UP = 9.83

print(f"读取{LABEL}年数据...")
df = pd.read_csv(CSV_PATH)
df = df[df['code'].str.startswith(('sh.60', 'sz.00'), na=False)]
for col in ['open', 'high', 'low', 'close', 'pctChg']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df['date'] = pd.to_datetime(df['date'], errors='coerce')
if YEAR == 2025:
    df = df[df['date'].dt.year == 2025]
df.sort_values(['code', 'date'], inplace=True)
df.reset_index(drop=True, inplace=True)
print(f"数据: {len(df)}行, {df['code'].nunique()}只")

# numpy数组加速
codes = df['code'].values
dates = df['date'].values
opens = df['open'].values
closes = df['close'].values
pctChgs = df['pctChg'].values
n = len(df)

change_idx = np.where(codes[:-1] != codes[1:])[0] + 1
boundaries = np.concatenate([[0], change_idx, [n]])

print(f"遍历 {len(boundaries)-1} 只票...")
results = []

for b in range(len(boundaries) - 1):
    start = boundaries[b]
    end = boundaries[b + 1]
    sz = end - start

    o = opens[start:end]
    c = closes[start:end]
    p = pctChgs[start:end]
    d = dates[start:end]

    for i in range(sz):
        # 第1天: 涨停
        if p[i] < LIMIT_UP:
            continue

        # 首次涨停: 前一天不能是涨停
        if i > 0 and p[i - 1] >= LIMIT_UP:
            continue

        # 第2天: 断板, 开盘>第1天收盘, 红K, 不涨停
        if i + 1 >= sz:
            break
        if p[i + 1] >= LIMIT_UP:    # 涨停了, 不是断板
            continue
        if o[i + 1] <= c[i]:        # 开盘没高开
            continue
        if c[i + 1] <= o[i + 1]:    # 绿K
            continue

        # 第3天: 开盘>第2天收盘, 红K, 不涨停
        if i + 2 >= sz:
            break
        if p[i + 2] >= LIMIT_UP:
            continue
        if o[i + 2] <= c[i + 1]:    # 开盘没高开
            continue
        if c[i + 2] <= o[i + 2]:
            continue

        # 第4天涨幅
        if i + 3 >= sz:
            break

        results.append({
            'code': codes[start + i],
            'date': str(d[i])[:10],
            'day1_pct': round(float(p[i]), 2),
            'day2_pct': round(float(p[i + 1]), 2),
            'day3_pct': round(float(p[i + 2]), 2),
            'day4_pct': round(float(p[i + 3]), 2),
            'day4_up': p[i + 3] > 0,
        })

total = len(results)
if total == 0:
    print("没有符合条件的票")
    sys.exit(0)

tdf = pd.DataFrame(results)
up_count = tdf['day4_up'].sum()
up_rate = up_count / total * 100

print(f"\n{'='*60}")
print(f"【{LABEL}: 首板→断板红K→再红K→第4天涨幅】")
print(f"{'='*60}")
print(f"符合条件的票: {total}只")
print(f"第4天上涨: {up_count}只 ({up_rate:.1f}%)")
print(f"第4天下跌: {total - up_count}只 ({100 - up_rate:.1f}%)")
print(f"第4天平均涨幅: {tdf['day4_pct'].mean():+.2f}%")
print(f"第4天中位涨幅: {tdf['day4_pct'].median():+.2f}%")

# 按第2天涨幅分档
print(f"\n{'='*60}")
print(f"【按第2天(断板日)涨幅分档】")
print(f"{'='*60}")
for lo, hi, label in [(0, 3, '小涨0%~+3%'), (3, 6, '中涨+3%~+6%'), (6, 99, '大涨>+6%')]:
    sub = tdf[(tdf['day2_pct'] >= lo) & (tdf['day2_pct'] < hi)]
    if len(sub) == 0:
        continue
    u = sub['day4_up'].sum()
    print(f"  {label}: {len(sub)}只 | 涨{u}只({u/len(sub)*100:.0f}%) | 平均{sub['day4_pct'].mean():+.2f}%")

# 按第3天涨幅分档
print(f"\n{'='*60}")
print(f"【按第3天涨幅分档】")
print(f"{'='*60}")
for lo, hi, label in [(0, 3, '小涨0%~+3%'), (3, 6, '中涨+3%~+6%'), (6, 99, '大涨>+6%')]:
    sub = tdf[(tdf['day3_pct'] >= lo) & (tdf['day3_pct'] < hi)]
    if len(sub) == 0:
        continue
    u = sub['day4_up'].sum()
    print(f"  {label}: {len(sub)}只 | 涨{u}只({u/len(sub)*100:.0f}%) | 平均{sub['day4_pct'].mean():+.2f}%")

# 明细
print(f"\n{'='*70}")
print(f"【明细(按日期排序)】")
print(f"{'='*70}")
print(f"  {'code':<12} {'日期':<12} {'Day1':>7} {'Day2':>7} {'Day3':>7} {'Day4':>7} {'Day4'}")
print("  " + "-" * 70)
for _, r in tdf.sort_values('date').iterrows():
    mark = " UP" if r['day4_up'] else " DN"
    print(f"  {r['code']:<12} {r['date']:<12} {r['day1_pct']:>+6.1f}% {r['day2_pct']:>+6.1f}% {r['day3_pct']:>+6.1f}% {r['day4_pct']:>+6.1f}%{mark}")