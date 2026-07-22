"""
龙头首阴: 四连板+ → 断板绿柱 → 次日红柱 → 第三天是否上涨
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
MIN_BOARDS = 4

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

# 转numpy数组加速
codes = df['code'].values
dates = df['date'].values
opens = df['open'].values
closes = df['close'].values
pctChgs = df['pctChg'].values
n = len(df)

# 找每个code的边界
change_idx = np.where(codes[:-1] != codes[1:])[0] + 1
boundaries = np.concatenate([[0], change_idx, [n]])

print(f"遍历 {len(boundaries)-1} 只票...")
results = []

for b in range(len(boundaries) - 1):
    start = boundaries[b]
    end = boundaries[b]
    sz = end - start

    o = opens[start:end]
    c = closes[start:end]
    p = pctChgs[start:end]
    d = dates[start:end]

    i = 0
    while i < sz:
        if p[i] < LIMIT_UP:
            i += 1
            continue

        boards = 0
        while i < sz and p[i] >= LIMIT_UP:
            boards += 1
            i += 1

        if boards < MIN_BOARDS:
            continue

        # 第2步: 断板日绿柱
        if i >= sz or c[i] >= o[i]:
            continue

        # 第3步: 次日红柱
        if i + 1 >= sz or c[i+1] <= o[i+1]:
            continue

        # 第3天数据
        if i + 2 >= sz:
            continue

        results.append({
            'code': codes[start + i],
            '连板数': boards,
            '断板日期': str(d[i])[:10],
            'day1_pct': round(float(p[i]), 2),
            'day2_pct': round(float(p[i+1]), 2),
            'day3_pct': round(float(p[i+2]), 2),
            'day3_up': p[i+2] > 0,
        })

total = len(results)
if total == 0:
    print("没有符合条件的票")
    sys.exit(0)

tdf = pd.DataFrame(results)
up_count = tdf['day3_up'].sum()
up_rate = up_count / total * 100

print(f"\n{'='*60}")
print(f"【{LABEL}: ≥{MIN_BOARDS}连板 → 断板绿柱 → 次日红柱 → 第3天?】")
print(f"{'='*60}")
print(f"符合条件的票: {total}只")
print(f"第3天上涨: {up_count}只 ({up_rate:.1f}%)")
print(f"第3天下跌: {total - up_count}只 ({100 - up_rate:.1f}%)")
print(f"第3天平均涨幅: {tdf['day3_pct'].mean():+.2f}%")

# 按连板数分档
print(f"\n{'='*60}")
print(f"【按连板数分档】")
print(f"{'='*60}")
for b in sorted(tdf['连板数'].unique()):
    sub = tdf[tdf['连板数'] == b]
    u = sub['day3_up'].sum()
    print(f"  {b}连板: {len(sub)}只 | 第3天涨{u}只({u/len(sub)*100:.0f}%) | 平均{sub['day3_pct'].mean():+.2f}%")

# 按断板跌幅分档
print(f"\n{'='*60}")
print(f"【按断板跌幅分档】")
print(f"{'='*60}")
for lo, hi, label in [(-5, 0, '小跌-5%~0%'), (-7, -5, '中跌-7%~-5%'), (-99, -7, '暴跌<-7%')]:
    sub = tdf[(tdf['day1_pct'] >= lo) & (tdf['day1_pct'] < hi)]
    if len(sub) == 0:
        continue
    u = sub['day3_up'].sum()
    print(f"  {label}: {len(sub)}只 | 第3天涨{u}只({u/len(sub)*100:.0f}%) | 平均{sub['day3_pct'].mean():+.2f}%")

# 明细
print(f"\n{'='*70}")
print(f"【明细】")
print(f"{'='*70}")
print(f"  {'code':<12} {'连板':>3} {'断板日期':<12} {'Day1跌':>7} {'Day2涨':>7} {'Day3涨':>7} {'Day3'}")
print("  " + "-" * 65)
for _, r in tdf.sort_values('断板日期').iterrows():
    mark = "UP" if r['day3_up'] else "DN"
    print(f"  {r['code']:<12} {r['连板数']:>3} {r['断板日期']:<12} {r['day1_pct']:>+6.1f}% {r['day2_pct']:>+6.1f}% {r['day3_pct']:>+6.1f}% {mark}")