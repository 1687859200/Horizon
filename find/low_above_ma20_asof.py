# -*- coding: utf-8 -*-
"""
截至指定日期, 仍处于连续 N 日以上 low > MA 均线状态的个股.

筛选逻辑:
  MA(默认MA20) 用前复权 close 计算 (在截至目标日的全量数据上 rolling)
  连续段: 每日 low > MA 即 above==1, above==0 出现则断开
  入选条件: 截至目标日当天, 该票仍处于 above==1 状态, 且当前连续段长度 >= STREAK_DAYS

  即: 目标日当天 low > MA, 且往前连续 N 天都满足

用法:
  python low_above_ma20_asof.py 20260718
  不带参数则使用 DEFAULT_TARGET
"""
import sys
import unicodedata
import pandas as pd
from build_code_name import load_code_name

# ===================== 参数 =====================
KLINE_CSV = "../data/all_kline_26.csv"
DEFAULT_TARGET = "20260720"          # 默认目标日 YYYYMMDD
MA_LEN = 20                          # 均线周期
STREAK_DAYS = 20                     # 连续天数下限
# ===============================================


def _norm(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


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
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    target_norm = _norm(target)
    ma_col = f"MA{MA_LEN}"

    df = pd.read_csv(KLINE_CSV, dtype={"code": str})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values(["code", "date"]).reset_index(drop=True)

    # 截至目标日的全量数据 (含目标日)
    df = df[df["date"] <= target_norm].copy()
    if df.empty or target_norm not in df["date"].values:
        print(f"目标日 {target} 无交易数据 (可能是周末/节假日或数据未更新)")
        return

    # MA 在截至目标日的全量上算 (保证历史窗口完整)
    df[ma_col] = df.groupby("code")["close"].transform(
        lambda s: s.rolling(MA_LEN).mean()
    )

    # 连续段: above==0 出现一次 seg +1, 同一连续 above==1 段内 seg 值相同
    df["above"] = (df["low"] > df[ma_col]).astype(int)
    df["seg"] = df.groupby("code")["above"].transform(lambda s: (s == 0).cumsum())

    # 每段聚合 (只统计 above==1 的行)
    segs = df[df["above"] == 1].groupby(["code", "seg"]).agg(
        起始日=("date", "min"),
        结束日=("date", "max"),
        连续天数=("date", "count"),
        末日收盘=("close", "last"),
        末日成交额=("amount", "last"),
        末日换手率=("turn", "last"),
    ).reset_index()

    # 入选: 段结束日 == 目标日 (即目标日当天仍 above), 且连续天数 >= STREAK_DAYS
    hit = segs[
        (segs["结束日"] == target_norm)
        & (segs["连续天数"] >= STREAK_DAYS)
    ].copy()
    if hit.empty:
        print(f"截至 {target}, 无连续 {STREAK_DAYS} 日以上 low > {ma_col} 的个股")
        return

    name_map = load_code_name()
    hit["名称"] = hit["code"].map(lambda c: name_map.get(c, "-"))

    out = pd.DataFrame({
        "代码": hit["code"].values,
        "名称": hit["名称"].values,
        "起始日": hit["起始日"].values,
        "结束日": hit["结束日"].values,
        "连续天数": hit["连续天数"].astype(int).values,
        "末日收盘": [f"{x:.2f}" for x in hit["末日收盘"].values],
        "成交额": [_fmt_amount(x) for x in hit["末日成交额"].values],
        "换手率": [f"{x:.2f}%" if pd.notna(x) else "-" for x in hit["末日换手率"].values],
    })
    out = out.sort_values("连续天数", ascending=False).reset_index(drop=True)

    print(f"截至 {target}, 连续{STREAK_DAYS}日以上 low > {ma_col}: "
          f"{len(out)} 只股票\n")
    _print_table(out, {"连续天数", "末日收盘", "成交额", "换手率"})


if __name__ == "__main__":
    main()
