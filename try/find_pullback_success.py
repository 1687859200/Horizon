"""
连板断板跌停反包策略 v4
不开盘买，盘中确认强势再进场
入场条件: 盘中涨到+3%买入(确认有资金) + 收盘≥+5%(加满仓)
收盘<0%不买(放弃)
"""

import pandas as pd
import os
import sys

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'all_kline.csv')

LIMIT_UP = 9.83
LIMIT_DOWN = -9.83
MIN_STREAK = 2
OPEN_FILTER = -3.0      # 开盘过滤
ENTRY_THRESHOLD = 5.0    # 尾盘买入门槛(收盘相对开盘)
ADD_POSITION = 5.0        # 满仓线(收盘相对开盘)
STOP_LOSS = -8.0

print("读取数据...")
df = pd.read_csv(CSV_PATH)
df = df[df['code'].astype(str).str.match(r'^(sh\.60|sz\.00)')]
df['date'] = pd.to_datetime(df['date'], errors='coerce')
df = df.dropna(subset=['date'])
for col in ['open', 'high', 'low', 'close', 'pctChg', 'preclose']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df = df.dropna(subset=['pctChg'])
df.sort_values(['code', 'date'], inplace=True)
df.reset_index(drop=True, inplace=True)

print(f"数据: {len(df)}行, {df['code'].nunique()}只, {df['date'].min().date()}~{df['date'].max().date()}")
print(f"规则: 尾盘收盘≥+{ENTRY_THRESHOLD}%买入 | 收盘≥+{ADD_POSITION}%满仓 | +10%止盈 | {STOP_LOSS}%止损\n")

df['is_limit_up'] = df['pctChg'] >= LIMIT_UP

trades = []
skipped_open = 0
skipped_weak = 0
skipped_no_trigger = 0
processed = 0

for code, group in df.groupby('code'):
    processed += 1
    if processed % 1000 == 0:
        print(f"  {processed}/{df['code'].nunique()}, {len(trades)}笔", end='\r')

    group = group.reset_index(drop=True)
    n = len(group)

    i = 0
    while i < n:
        if group.loc[i, 'is_limit_up']:
            start_idx = i
            while i < n and group.loc[i, 'is_limit_up']:
                i += 1
            end_idx = i - 1
            streak = end_idx - start_idx + 1

            if streak >= MIN_STREAK:
                break_idx = end_idx + 1
                if break_idx < n:
                    break_day = group.loc[break_idx]
                    if break_day['pctChg'] <= LIMIT_DOWN:
                        is_yizi = (abs(break_day['open'] - break_day['low']) < 0.01
                                   and abs(break_day['open'] - break_day['close']) < 0.01)
                        if not is_yizi:
                            buy_idx = break_idx + 1
                            if buy_idx >= n:
                                continue

                            buy_day = group.loc[buy_idx]
                            open_price = buy_day['open']
                            # 开盘涨幅(相对断板日收盘)
                            open_pct = (open_price - break_day['close']) / break_day['close'] * 100

                            # 过滤1: 开盘太低
                            if open_pct < OPEN_FILTER:
                                skipped_open += 1
                                continue

                            # 收盘涨幅(相对开盘价) - 尾盘确认
                            close_from_open_pct = (buy_day['close'] - open_price) / open_price * 100

                            # 过滤2: 收盘没到+2%，不买(尾盘确认强势)
                            if close_from_open_pct < ENTRY_THRESHOLD:
                                skipped_no_trigger += 1
                                continue

                            # 尾盘买入价 = 收盘价
                            buy_price = round(buy_day['close'], 2)

                            # 收盘时判断仓位
                            is_strong_close = close_from_open_pct >= ADD_POSITION

                            record = {
                                'code': code,
                                '连板天数': streak,
                                '断板日期': break_day['date'].strftime('%Y-%m-%d'),
                                '断板跌幅%': round(break_day['pctChg'], 2),
                                '买入日期': buy_day['date'].strftime('%Y-%m-%d'),
                                '开盘价': round(open_price, 2),
                                '买入价': buy_price,
                                '开盘涨幅': round(open_pct, 2),
                                '收盘强度%': round(close_from_open_pct, 2),
                                '仓位': '满' if is_strong_close else '半',
                            }

                            # 持仓跟踪从次日开始
                            half_sold = False
                            half_sell_day = None
                            is_full = record['仓位'] == '满'

                            for j in range(buy_idx + 1, n):
                                day = group.loc[j]
                                low_pct = (day['low'] - buy_price) / buy_price * 100
                                high_pct = (day['high'] - buy_price) / buy_price * 100
                                open_day_pct = (day['open'] - buy_price) / buy_price * 100
                                is_green = day['close'] < day['open']

                                # 止损
                                if low_pct <= STOP_LOSS:
                                    actual_stop = open_day_pct if open_day_pct <= STOP_LOSS else STOP_LOSS
                                    if half_sold:
                                        total_pct = (10 + actual_stop) / 2
                                        reason = f'半仓{half_sell_day}@+10%, 余仓止损{actual_stop:+.1f}%'
                                    else:
                                        total_pct = actual_stop
                                        reason = f'止损{actual_stop:+.1f}%'
                                    record.update({
                                        '持有天数': j - buy_idx,
                                        '半仓止盈': '是' if half_sold else '否',
                                        '半仓卖出日': half_sell_day if half_sold else '-',
                                        '余仓卖出日': day['date'].strftime('%m-%d'),
                                        '余仓收益%': round(actual_stop, 2),
                                        '综合收益%': round(total_pct, 2),
                                        '出局原因': reason,
                                    })
                                    break

                                # +10%止盈
                                if not half_sold and high_pct >= 10:
                                    half_sold = True
                                    half_sell_day = day['date'].strftime('%m-%d')

                                # 绿K卖出
                                if is_green:
                                    remain_pct = (day['close'] - buy_price) / buy_price * 100
                                    if half_sold:
                                        total_pct = (10 + remain_pct) / 2
                                        reason = f'半仓{half_sell_day}@+10%, 余仓{day["date"].strftime("%m-%d")}绿K卖出'
                                    else:
                                        total_pct = remain_pct
                                        reason = f'未到10%, {day["date"].strftime("%m-%d")}绿K卖出'
                                    record.update({
                                        '持有天数': j - buy_idx,
                                        '半仓止盈': '是' if half_sold else '否',
                                        '半仓卖出日': half_sell_day if half_sold else '-',
                                        '余仓卖出日': day['date'].strftime('%m-%d'),
                                        '余仓收益%': round(remain_pct, 2),
                                        '综合收益%': round(total_pct, 2),
                                        '出局原因': reason,
                                    })
                                    break
                            else:
                                # 数据末尾
                                last = group.loc[n - 1]
                                remain_pct = (last['close'] - buy_price) / buy_price * 100
                                if half_sold:
                                    total_pct = (10 + remain_pct) / 2
                                else:
                                    total_pct = remain_pct
                                record.update({
                                    '持有天数': n - 1 - buy_idx,
                                    '半仓止盈': '是' if half_sold else '否',
                                    '半仓卖出日': half_sell_day if half_sold else '-',
                                    '余仓卖出日': last['date'].strftime('%m-%d'),
                                    '余仓收益%': round(remain_pct, 2),
                                    '综合收益%': round(total_pct, 2),
                                    '出局原因': f'到期{last["date"].strftime("%m-%d")}',
                                })

                            trades.append(record)
        else:
            i += 1

# ==================== 输出 ====================
trade_df = pd.DataFrame(trades)
total = len(trade_df)

print(f"\n\n{'=' * 80}")
print(f"策略v5: 尾盘收盘≥+{ENTRY_THRESHOLD}%买入 + 收盘≥+{ADD_POSITION}%满仓 + 开盘≥{OPEN_FILTER}%")
print(f"{'=' * 80}")

print(f"\n选股扫描: 跳过开盘低({skipped_open}) + 收盘未到+{ENTRY_THRESHOLD}%({skipped_no_trigger}) = 放弃{skipped_open+skipped_no_trigger}条")
print(f"实际交易: {total}条")

if total == 0:
    sys.exit(0)

ret = trade_df['综合收益%']

print(f"\n{'='*60}")
print(f"【整体收益】")
print(f"{'='*60}")
print(f"  平均收益: {ret.mean():+.2f}%")
print(f"  中位收益: {ret.median():+.2f}%")
print(f"  胜率: {(ret > 0).sum()}/{total} ({(ret > 0).mean()*100:.1f}%)")
print(f"  最大盈利: {ret.max():+.2f}%")
print(f"  最大亏损: {ret.min():+.2f}%")
print(f"  累计收益: {ret.sum():+.2f}%")

# 仓位
full = trade_df[trade_df['仓位'] == '满']
half = trade_df[trade_df['仓位'] == '半']
print(f"\n  满仓(收盘≥+{ADD_POSITION}%): {len(full)}条 | 胜率{(full['综合收益%']>0).mean()*100:.0f}% | 平均{full['综合收益%'].mean():+.2f}% | 累计{full['综合收益%'].sum():+.2f}%")
print(f"  半仓(收盘+{ENTRY_THRESHOLD}%~+{ADD_POSITION}%): {len(half)}条 | 胜率{(half['综合收益%']>0).mean()*100:.0f}% | 平均{half['综合收益%'].mean():+.2f}% | 累计{half['综合收益%'].sum():+.2f}%")

# 止盈
tp = trade_df[trade_df['半仓止盈'] == '是']
no_tp = trade_df[trade_df['半仓止盈'] == '否']
print(f"\n  触发+10%止盈: {len(tp)}条 ({len(tp)/total*100:.1f}%) 平均{tp['综合收益%'].mean():+.2f}%")
print(f"  未触发止盈:   {len(no_tp)}条 ({len(no_tp)/total*100:.1f}%) 平均{no_tp['综合收益%'].mean():+.2f}%")

# 年份
print(f"\n{'='*60}")
print(f"【按年份】")
print(f"{'='*60}")
trade_df['年份'] = pd.to_datetime(trade_df['买入日期']).dt.year
for year in sorted(trade_df['年份'].unique()):
    sub = trade_df[trade_df['年份'] == year]
    win = (sub['综合收益%'] > 0).sum()
    tp_r = (sub['半仓止盈'] == '是').sum()
    print(f"  {year}年: {len(sub)}条 | 胜率{win/len(sub)*100:.0f}% | 平均{sub['综合收益%'].mean():+.2f}% | 止盈率{tp_r/len(sub)*100:.0f}% | 累计{sub['综合收益%'].sum():+.2f}%")

# 连板天数
print(f"\n{'='*60}")
print(f"【按连板天数】")
print(f"{'='*60}")
for days in sorted(trade_df['连板天数'].unique()):
    sub = trade_df[trade_df['连板天数'] == days]
    if len(sub) < 3:
        continue
    win = (sub['综合收益%'] > 0).sum()
    print(f"  {days}连板: {len(sub)}条 | 胜率{win/len(sub)*100:.0f}% | 平均{sub['综合收益%'].mean():+.2f}%")

# 明细
print(f"\n{'='*80}")
print(f"【全部交易明细】")
print(f"{'='*80}")
print(f"  {'code':<12} {'天':>2} {'日期':<12} {'开涨幅':>6} {'买价':>7} {'强度%':>6} {'仓位':>3} "
      f"{'持天':>3} {'收益':>7} {'止盈':>3} | {'出局原因'}")
print("  " + "-" * 100)
for _, r in trade_df.sort_values('综合收益%', ascending=False).iterrows():
    mark = " *" if r['综合收益%'] > 0 else " X"
    print(f"  {r['code']:<12} {r['连板天数']:>2} {r['买入日期']:<12} {r['开盘涨幅']:>+5.1f}% {r['买入价']:>7.2f} "
          f"{r['收盘强度%']:>+5.1f}% {r['仓位']:>3} "
          f"{r['持有天数']:>3} {r['综合收益%']:>+6.2f}% {r['半仓止盈']:>3} | {r['出局原因']}{mark}")

out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'strategy_v5_backtest.csv')
trade_df.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n已保存: {out_path}")
