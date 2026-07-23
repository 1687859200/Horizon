# -*- coding: utf-8 -*-
"""
目标日选股: 涨幅 6~9% 且 当日K线穿越20日均线

筛选条件(对目标日当天):
  1. 涨幅(pctChg) 在 [6%, 9%] 区间
  2. 当日最低价 <= MA20  且  当日最高价 >= MA20
     (即当日K线上下穿/触及20日均线, 视为围绕均线波动)

数据源:
  - 本地: Horizon/data/all_kline_26.csv (前复权日线, 算 MA20)

输入: TARGET_DATE (顶部变量, YYYYMMDD, 必须是交易日)
"""
import unicodedata
import pandas as pd

from build_code_name import load_code_name

# ===================== 用户输入变量 =====================
TARGET_DATE = "20260306"               # 目标交易日, 格式 YYYYMMDD
KLINE_CSV = "../data/all_kline_26.csv"

GAIN_LOW = 6.0                         # 涨幅下限 (%)
GAIN_HIGH = 9.0                        # 涨幅上限 (%)
MA_LEN = 20                            # 均线周期
FORWARD_DAYS = 5  # 后续累计涨幅交易日数
# =======================================================


# ---------- 本地K线: 算MA20, 取目标日切片 ----------
def load_day_with_ma(kline_csv: str, target_date: str, ma_len: int = MA_LEN):
    """返回目标日切片(含 MA20, MACD)"""
    df = pd.read_csv(kline_csv, dtype={"code": str})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    df[f"MA{ma_len}"] = df.groupby("code")["close"].transform(
        lambda s: s.rolling(ma_len).mean()
    )
    # MACD(12,26,9): DIF = EMA12 - EMA26, DEA = EMA9(DIF), MACD柱 = 2*(DIF-DEA)
    g = df.groupby("code")["close"]
    df["DIF"] = g.transform(lambda s: s.ewm(span=12, adjust=False).mean()) - \
                g.transform(lambda s: s.ewm(span=26, adjust=False).mean())
    df["DEA"] = df.groupby("code")["DIF"].transform(lambda s: s.ewm(span=9, adjust=False).mean())
    df["MACD"] = 2 * (df["DIF"] - df["DEA"])
    # 后N日累计涨幅: 优先第N日, 不足N日则取最新可用日(只要有次日数据就兜底)
    future_n = df.groupby("code")["close"].shift(-FORWARD_DAYS)
    last_close = df.groupby("code")["close"].transform("last")
    next_close = df.groupby("code")["close"].shift(-1)
    fwd_close = future_n.where(future_n.notna(), last_close.where(next_close.notna()))
    df[f"后{FORWARD_DAYS}日累计"] = (fwd_close / df["close"] - 1) * 100

    target_norm = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"
    day = df[df["date"] == target_norm].copy()
    if day.empty:
        raise ValueError(f"本地K线中找不到 {target_norm} 的数据, 请确认日期或更新K线库.")
    return day, target_norm


# ---------- 中文对齐打印 ----------
def _disp_w(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def _pad(s, width: int, align: str = "left") -> str:
    s = str(s)
    n = width - _disp_w(s)
    return s + " " * n if align == "left" else " " * n + s


def _fmt_amount(v) -> str:
    if v is None or v != v:
        return "-"
    if v >= 1e8:
        return f"{v/1e8:.2f}亿"
    if v >= 1e4:
        return f"{v/1e4:.1f}万"
    return f"{v:.0f}"


def _print_aligned(df, title: str):
    print(f"\n{title}  共 {len(df)} 只")
    if df.empty:
        print("  (无)")
        return
    cols = df.columns.tolist()
    right_cols = {"收盘", "最低", "最高", f"MA{MA_LEN}", "涨幅",
                  "DIF", "DEA", "MACD", "成交额", "流通市值",
                  f"后{FORWARD_DAYS}日累计", "换手率"}
    aligns = ["right" if c in right_cols else "left" for c in cols]
    widths = [max(_disp_w(c), max(_disp_w(str(v)) for v in df[c])) for c in cols]
    header = "  ".join(_pad(c, w, a) for c, w, a in zip(cols, widths, aligns))
    print(header)
    print("-" * _disp_w(header))
    for _, row in df.iterrows():
        print("  ".join(_pad(str(row[c]), w, a) for c, w, a in zip(cols, widths, aligns)))


# ---------- 主流程 ----------
def main():
    target = TARGET_DATE
    day, target_norm = load_day_with_ma(KLINE_CSV, target, MA_LEN)
    print(f"目标日期: {target_norm}")
    # 当日大盘加权涨幅(成交额加权, 近似全A)
    valid = day.dropna(subset=["pctChg", "amount"])
    total_amt = valid["amount"].sum()
    mkt_gain = (valid["pctChg"] * valid["amount"]).sum() / total_amt if total_amt > 0 else float("nan")
    print(f"当日大盘加权涨幅: {mkt_gain:+.2f}%")
    print(f"本地K线覆盖股票数: {day['code'].nunique()}")

    ma_col = f"MA{MA_LEN}"

    # 过滤掉 MA20 不足周期的新股/次新股
    has_ma = day[day[ma_col].notna()].copy()
    print(f"有 {MA_LEN} 日均线数据的股票数: {len(has_ma)}")

    # 条件1: 涨幅 6~9%
    cond_gain = (has_ma["pctChg"] >= GAIN_LOW) & (has_ma["pctChg"] <= GAIN_HIGH)
    # 条件2: 当日最低 <= MA20 且 当日最高 >= MA20  (穿越均线)
    cond_cross = (has_ma["low"] <= has_ma[ma_col]) & (has_ma["high"] >= has_ma[ma_col])

    final = has_ma[cond_gain & cond_cross].copy()
    print(f"满足 涨幅[{GAIN_LOW}%,{GAIN_HIGH}%] + 穿越{MA_LEN}日均线: {len(final)} 只")

    # 代码 -> 名称
    name_map = load_code_name()
    final["名称"] = final["code"].map(lambda c: name_map.get(c, "-"))
    # 流通市值: 由换手率反推流通股本(流通股本 = volume*100/turn), 再乘close
    final["流通市值"] = (final["volume"] * 100 * final["close"] / final["turn"]).where(final["turn"] > 0)
    # 收盘站上MA20 打标志(穿越条件下 close>=MA 视为"收回")
    final["标志"] = final["close"].ge(final[ma_col]).map({True: "▲", False: ""})

    # 展示列
    fwd_col = f"后{FORWARD_DAYS}日累计"
    show = final[["code", "名称", "pctChg", "close", "low", "high", ma_col,
                  "DIF", "DEA", "MACD", "amount", "流通市值", "turn", fwd_col, "标志"]].copy()
    show.columns = ["代码", "名称", "涨幅", "收盘", "最低", "最高", f"MA{MA_LEN}",
                    "DIF", "DEA", "MACD", "成交额", "流通市值", "换手率", fwd_col, "标志"]
    show = show.sort_values("涨幅", ascending=False)
    show["涨幅"] = show["涨幅"].map(lambda v: f"{v:.2f}%")
    for c in ["收盘", "最低", "最高", f"MA{MA_LEN}"]:
        show[c] = show[c].map(lambda v: f"{v:.2f}")
    for c in ["DIF", "DEA", "MACD"]:
        show[c] = show[c].map(lambda v: f"{v:+.3f}" if pd.notna(v) else "-")
    show["成交额"] = show["成交额"].map(_fmt_amount)
    show["流通市值"] = show["流通市值"].map(_fmt_amount)
    show[fwd_col] = show[fwd_col].map(lambda v: f"{v:+.2f}%" if pd.notna(v) else "-")
    show["换手率"] = show["换手率"].map(lambda v: f"{v:.2f}%" if pd.notna(v) else "-")

    _print_aligned(
        show,
        f"=== 涨幅 {GAIN_LOW}%~{GAIN_HIGH}% 且 当日穿越 {MA_LEN} 日均线 ===",
    )

    # 保存(保留原始字段, 便于后续分析)
    # out_path = f"gain{int(GAIN_LOW)}_{int(GAIN_HIGH)}_cross_ma{MA_LEN}_{target}.csv"
    # final.to_csv(out_path, index=False, encoding="utf-8-sig")
    # print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
