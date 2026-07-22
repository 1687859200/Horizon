"""
二连板 → 3连阴 → 第6天盘中入场(方案A近似)
入场: 开盘≥+1%(相对第5天收盘) + 收盘红K(分时承接近似) → 以+1.5%价格买入
持有到第9天收盘离场, -8%止损
"""
import pandas as pd
import os
import sys

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2425
ENTRY_THRESHOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
LABEL = {2026: '2026', 2025: '2025', 2425: '2024-2025'}.get(YEAR, str(YEAR))
CSV_MAP = {
    2026: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline_26.csv'),
    2025: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline.csv'),
    2425: os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline.csv'),
}
CSV_PATH = CSV_MAP.get(YEAR, CSV_MAP[2026])

LIMIT_UP = 9.83
STOP_LOSS = -8.0
MAX_HOLD = 3  # 持到第9天(买入后3天)
MAX_BUY_PRICE = 30  # 买入价上限

print(f"读取{YEAR}年数据...")
df = pd.read_csv(CSV_PATH)
df = df[df['code'].str.startswith(('sh.60', 'sz.00'), na=False)]
for col in ['open', 'high', 'low', 'close', 'pctChg']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df['date'] = pd.to_datetime(df['date'], errors='coerce')
if YEAR == 2025:
    df = df[df['date'].dt.year == 2025]
elif YEAR == 2425:
    pass  # 全部数据 2024+2025
df.reset_index(drop=True, inplace=True)
print(f"数据: {len(df)}行, {df['code'].nunique()}只\n")

trades = []
skipped = 0

for code, group in df.groupby('code'):
    rows = group.reset_index(drop=True)
    n = len(rows)
    for i in range(5, n - 1):
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

        # 第六天涨停则无法买入, 跳过
        if day6['pctChg'] >= LIMIT_UP:
            skipped += 1
            continue

        close_from_open = (day6['close'] - day6['open']) / day6['open'] * 100

        # 入场条件: 尾盘收盘涨幅 ≥ 阈值(相对开盘)
        if close_from_open < ENTRY_THRESHOLD:
            skipped += 1
            continue

        buy_price = day6['close']
        if buy_price > MAX_BUY_PRICE:
            skipped += 1
            continue
        pullback_pct = (day5['close'] - rows.loc[i-4, 'close']) / rows.loc[i-4, 'close'] * 100

        # 持仓跟踪: 从第7天(i+1)开始, 最多持MAX_HOLD天
        exit_day = None
        exit_reason = ''
        total_pct = 0
        max_pct = 0  # 持仓期间最高涨幅

        for d in range(1, MAX_HOLD + 1):
            idx = i + d
            if idx >= n:
                # 数据结束
                last = rows.loc[n - 1]
                total_pct = (last['close'] - buy_price) / buy_price * 100
                exit_day = d
                exit_reason = f'到期{str(last["date"])[:10]}'
                break

            day = rows.loc[idx]
            low_pct = (day['low'] - buy_price) / buy_price * 100
            open_pct = (day['open'] - buy_price) / buy_price * 100
            high_pct = (day['high'] - buy_price) / buy_price * 100
            if high_pct > max_pct:
                max_pct = high_pct

            # 止损
            if low_pct <= STOP_LOSS:
                actual_stop = open_pct if open_pct <= STOP_LOSS else STOP_LOSS
                total_pct = actual_stop
                exit_reason = f'止损{actual_stop:+.1f}%'
                exit_day = d
                break

            # 到期清仓
            if d == MAX_HOLD:
                total_pct = (day['close'] - buy_price) / buy_price * 100
                exit_reason = f'到期{str(day["date"])[:10]} {total_pct:+.1f}%'
                exit_day = d
                break
        else:
            # 循环正常结束(没break) → 数据不够
            last = rows.loc[n - 1]
            total_pct = (last['close'] - buy_price) / buy_price * 100
            exit_day = MAX_HOLD
            exit_reason = f'到期{str(last["date"])[:10]}'

        drawdown = round(max_pct - total_pct, 2) if max_pct > 0 else 0
        trades.append({
            'code': code,
            '买入日期': str(day6['date'])[:10],
            '回调幅度%': round(pullback_pct, 2),
            '买入价': round(buy_price, 2),
            '持天': exit_day,
            '最高涨%': round(max_pct, 2),
            '收益%': round(total_pct, 2),
            '利润回撤%': drawdown,
            '出局原因': exit_reason,
        })

total = len(trades)
if total == 0:
    print("没有符合条件的交易")
    sys.exit(0)

tdf = pd.DataFrame(trades)

print(f"{'='*60}")
print(f"【{LABEL}: 二连板→3连阴→第6天入场→止盈止损策略】")
print(f"{'='*60}")
print(f"规则: 第6天收盘≥+{ENTRY_THRESHOLD}%(相对开盘)尾盘买入 | 买价≤{MAX_BUY_PRICE}元 | 持到第{6+MAX_HOLD}天离场 | -8%止损")
print(f"筛选: 跳过无信号({skipped}条)")
print(f"实际交易: {total}条\n")

ret = tdf['收益%']
print(f"  平均收益: {ret.mean():+.2f}%")
print(f"  中位收益: {ret.median():+.2f}%")
print(f"  胜率: {(ret > 0).sum()}/{total} ({(ret > 0).mean()*100:.1f}%)")
print(f"  最大盈利: {ret.max():+.2f}%")
print(f"  最大亏损: {ret.min():+.2f}%")
print(f"  累计收益: {ret.sum():+.2f}%")

stopped = tdf[tdf['出局原因'].str.startswith('止损')]
held = tdf[~tdf['出局原因'].str.startswith('止损')]
print(f"\n  止损出局: {len(stopped)}条 ({len(stopped)/total*100:.1f}%) 平均{stopped['收益%'].mean():+.2f}%")
print(f"  持到期:   {len(held)}条 ({len(held)/total*100:.1f}%) 平均{held['收益%'].mean():+.2f}%")

# 利润回撤分析
print(f"\n{'='*60}")
print(f"【利润回撤分析】")
print(f"{'='*60}")
big_draw = tdf[tdf['利润回撤%'] >= 5].sort_values('利润回撤%', ascending=False)
print(f"  回撤≥5%: {len(big_draw)}条 (占总交易{len(big_draw)/total*100:.0f}%)")
if len(big_draw) > 0:
    print(f"  回撤均值: {big_draw['利润回撤%'].mean():.1f}% | 最高涨均值: {big_draw['最高涨%'].mean():+.1f}% | 最终收益均值: {big_draw['收益%'].mean():+.2f}%")
    print(f"\n  {'code':<12} {'日期':<12} {'最高涨':>7} {'最终':>7} {'回撤':>6} | {'出局原因'}")
    print("  " + "-" * 70)
    for _, r in big_draw.iterrows():
        print(f"  {r['code']:<12} {r['买入日期']:<12} {r['最高涨%']:>+6.1f}% {r['收益%']:>+6.1f}% {r['利润回撤%']:>5.1f}% | {r['出局原因']}")

# 按回调幅度分档
print(f"\n{'='*60}")
print(f"【按回调幅度分档】")
print(f"{'='*60}")
for lo, hi, label in [(-5, 0, '浅调-5%~0%'), (-10, -5, '中调-10%~-5%'), (-20, -10, '深调-20%~-10%'), (-99, -20, '暴跌<-20%')]:
    sub = tdf[(tdf['回调幅度%'] >= lo) & (tdf['回调幅度%'] < hi)]
    if len(sub) == 0:
        continue
    r = sub['收益%']
    print(f"  {label}: {len(sub)}条 | 胜率{(r>0).mean()*100:.0f}% | 平均{r.mean():+.2f}% | 累计{r.sum():+.2f}%")

# 明细
print(f"\n{'='*80}")
print(f"【全部交易明细(按收益排序)】")
print(f"{'='*80}")
print(f"  {'code':<12} {'买入日期':<12} {'回调%':>7} {'买价':>7} {'持天':>3} {'最高涨':>7} {'收益%':>7} {'回撤':>6} | {'出局原因'}")
print("  " + "-" * 90)
for _, r in tdf.sort_values('收益%', ascending=False).iterrows():
    mark = " *" if r['收益%'] > 0 else " X"
    print(f"  {r['code']:<12} {r['买入日期']:<12} {r['回调幅度%']:>+6.1f}% {r['买入价']:>7.2f} "
          f"{r['持天']:>3} {r['最高涨%']:>+6.1f}% {r['收益%']:>+6.2f}% {r['利润回撤%']:>5.1f}% | {r['出局原因']}{mark}")

out_path = os.path.join(os.path.dirname(__file__), '..', 'data', f'pullback_{YEAR}_backtest.csv')
tdf.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n已保存: {out_path}")
