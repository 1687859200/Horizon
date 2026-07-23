# -*- coding: utf-8 -*-
"""
找出今年内, 连续 N 个交易日的最低价都 > MA 均线 的个股.

筛选逻辑:
  MA(默认MA20) 用前复权 close 计算
  连续 N 天满足 low > MA 即入选 (N 默认 20)
  即: 该段内每个交易日低点都未触及均线, 股价始终在均线之上运行

输出: 每只票展示今年内最长的一段 (起始日/结束日/连续天数/末日收盘)
参数: MA_LEN(均线周期), STREAK_DAYS(连续天数下限)
"""
import unicodedata
import pandas as pd
from build_code_name import load_code_name

# ===================== 参数 =====================
KLINE_CSV = "../data/all_kline_26.csv"
START_DATE = "20260101"              # 起始交易日 YYYYMMDD
MA_LEN = 20                          # 均线周期
STREAK_DAYS = 20                     # 连续天数下限 (>=此值才入选)
# ===============================================


def _norm(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _disp_w(s) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def _pad(s, width: int, align: str = "left") -> str:
    s = str(s)
    n = width - _disp_w(s)
    return s + " " * n if align == "left" else " " * n + s


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
    ma_col = f"MA{MA_LEN}"

    # MA 需要历史数据, 在完整 df 上算 (避免今年初的 MA 因缺历史而 NaN)
    df[ma_col] = df.groupby("code")["close"].transform(
        lambda s: s.rolling(MA_LEN).mean()
    )

    # 今年内切片, 在切片上重算连续段 (避免跨年段干扰)
    year = df[df["date"] >= start_norm].copy()
    year["above"] = (year["low"] > year[ma_col]).astype(int)
    # seg: above==0 出现一次则 +1, 同一连续 above==1 段内 seg 值相同
    year["seg"] = year.groupby("code")["above"].transform(
        lambda s: (s == 0).cumsum()
    )

    # 每段聚合 (只统计 above==1 的行)
    segs = year[year["above"] == 1].groupby(["code", "seg"]).agg(
        起始日=("date", "min"),
        结束日=("date", "max"),
        连续天数=("date", "count"),
        起始日收盘=("close", "first"),
        末日收盘=("close", "last"),
    ).reset_index()

    # 起止日涨幅
    segs["区间涨幅%"] = (segs["末日收盘"] / segs["起始日收盘"] - 1) * 100

    # 每只票只保留最长段
    segs = segs.sort_values(["code", "连续天数"], ascending=[True, False])
    best = segs.drop_duplicates("code", keep="first").reset_index(drop=True)

    hit = best[best["连续天数"] >= STREAK_DAYS].copy()
    if hit.empty:
        print(f"今年({START_DATE}起) 无连续 {STREAK_DAYS} 日以上 low > {ma_col} 的个股")
        return

    # 持续中标志: 结束日 == 今年最后一个交易日
    last_td = year["date"].max()
    hit["标志"] = (hit["结束日"] == last_td).map({True: "▲持续", False: ""})

    name_map = load_code_name()
    hit["名称"] = hit["code"].map(lambda c: name_map.get(c, "-"))

    out = pd.DataFrame({
        "代码": hit["code"].values,
        "名称": hit["名称"].values,
        "起始日": hit["起始日"].values,
        "结束日": hit["结束日"].values,
        "连续天数": hit["连续天数"].astype(int).values,
        "末日收盘": [f"{x:.2f}" for x in hit["末日收盘"].values],
        "区间涨幅": [f"{x:+.2f}%" for x in hit["区间涨幅%"].values],
        "标志": hit["标志"].values,
    })
    out = out.sort_values(["起始日"], ascending=[True]).reset_index(drop=True)

    ongoing = (out["标志"] == "▲持续").sum()
    print(f"今年({START_DATE}起) 连续{STREAK_DAYS}日以上 low > {ma_col}: "
          f"{len(out)} 只股票 (其中 {ongoing} 只仍在持续)\n")
    _print_table(out, {"连续天数", "末日收盘", "区间涨幅"})


if __name__ == "__main__":
    main()
