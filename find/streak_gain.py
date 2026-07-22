# -*- coding: utf-8 -*-
"""
找出今年连续 N 个交易日累计涨幅超过阈值的个股.

筛选逻辑:
  以每个交易日为窗口起点 D, 窗口 = [D, D+N-1] 共 N 个交易日
  累计涨幅 = (close[D+N-1] / preclose[D] - 1) * 100  (N日 compound 收益)
  若 >= GAIN_MIN 则该窗口入选

输出: 每只票只展示累计最高的一个窗口, 按累计涨幅降序
参数: DAYS(窗口交易日数), GAIN_MIN(累计涨幅下限%), MAX_LIMIT_UPS(窗口内涨停数上限)
"""
import unicodedata
import pandas as pd
from build_code_name import load_code_name

# ===================== 参数 =====================
KLINE_CSV = "D:/Code/Python/Horizon/data/all_kline_26.csv"
START_DATE = "20260101"              # 起始交易日 YYYYMMDD
DAYS = 5                             # 连续交易日数
GAIN_MIN = 30                        # 累计涨幅下限 (%)
MAX_LIMIT_UPS = 1                    # 窗口内涨停数上限 (None=不限制)
# ===============================================


def _norm(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _zt_ratio_series(codes: pd.Series) -> pd.Series:
    """按6位代码前缀给涨停幅度: 创/科创20%, 北交所30%, 其余10%"""
    c6 = codes.astype(str).str.split(".").str[-1]
    ratio = pd.Series(0.10, index=codes.index)
    ratio[c6.str.startswith(("300", "301", "688", "689"))] = 0.20
    ratio[c6.str.startswith(("8", "4")) | c6.str.startswith("920")] = 0.30
    return ratio


def _disp_w(s) -> int:
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


def _print_table(df, right_cols):
    if df.empty:
        print("  (无)")
        return
    cols = df.columns.tolist()
    aligns = ["right" if c in right_cols else "left" for c in cols]
    widths = [max(_disp_w(c), max(_disp_w(str(v)) for v in df[c])) for c in cols]
    header = "  ".join(_pad(c, w, a) for c, w, a in zip(cols, widths, aligns))
    print(header)
    print("-" * _disp_w(header))
    for _, row in df.iterrows():
        print("  ".join(_pad(str(row[c]), w, a) for c, w, a in zip(cols, widths, aligns)))


def main():
    df = pd.read_csv(KLINE_CSV, dtype={"code": str})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values(["code", "date"]).reset_index(drop=True)
    start_norm = _norm(START_DATE)

    # N日累计涨幅 = close[D+N-1] / preclose[D] - 1
    end_close = df.groupby("code")["close"].shift(-(DAYS - 1))
    end_date = df.groupby("code")["date"].shift(-(DAYS - 1))
    df["结束日"] = end_date
    df[f"{DAYS}日累计"] = (end_close / df["preclose"] - 1) * 100

    # 涨停判定: 用 pctChg 接近涨停幅度判定 (避开涨停价 round 0.01 误差)
    # 主板>=9.5%, 创/科创>=19.5%, 北交所>=29.5%
    ratio = _zt_ratio_series(df["code"])
    df["涨停"] = (df["pctChg"] >= ratio * 100 - 0.5).astype(int)
    df["窗口涨停"] = df.groupby("code")["涨停"].transform(
        lambda s: s.rolling(DAYS, min_periods=DAYS).sum().shift(-(DAYS - 1))
    )

    mask = (
        (df["date"] >= start_norm)
        & df[f"{DAYS}日累计"].notna()
        & (df[f"{DAYS}日累计"] >= GAIN_MIN)
    )
    if MAX_LIMIT_UPS is not None:
        mask = mask & (df["窗口涨停"] <= MAX_LIMIT_UPS)
    hit = df[mask].copy()
    if hit.empty:
        print(f"今年({START_DATE}起) 无连续 {DAYS} 日累计涨幅 >= {GAIN_MIN}%"
              f"且涨停数 <= {MAX_LIMIT_UPS} 的个股")
        return

    total_windows = len(hit)
    # 每只票只保留累计最高的窗口 (同一票多个重叠窗口时取最高)
    hit_best = hit.sort_values(["code", f"{DAYS}日累计"], ascending=[True, False])
    hit_best = hit_best.drop_duplicates("code", keep="first")
    hit_best = hit_best.sort_values(f"{DAYS}日累计", ascending=False)

    name_map = load_code_name()
    hit_best["名称"] = hit_best["code"].map(lambda c: name_map.get(c, "-"))

    out = pd.DataFrame({
        "代码": hit_best["code"].values,
        "名称": hit_best["名称"].values,
        "起始日": hit_best["date"].values,
        "结束日": hit_best["结束日"].values,
        f"{DAYS}日累计": [f"{x:.2f}%" for x in hit_best[f"{DAYS}日累计"].values],
        "涨停": hit_best["窗口涨停"].astype(int).values,
        "成交额": [_fmt_amount(x) for x in hit_best["amount"].values],
        "换手率": [f"{x:.2f}%" if pd.notna(x) else "-" for x in hit_best["turn"].values],
    })

    limit_desc = f", 涨停数 <= {MAX_LIMIT_UPS}" if MAX_LIMIT_UPS is not None else ""
    print(f"今年({START_DATE}起) 连续{DAYS}日累计涨幅 >= {GAIN_MIN}%{limit_desc}: "
          f"{len(out)} 只股票 (共 {total_windows} 个达标窗口)\n")
    _print_table(out, {f"{DAYS}日累计", "涨停", "成交额", "换手率"})


if __name__ == "__main__":
    main()