# -*- coding: utf-8 -*-
"""
找出今年 N 连板及以上个股, 在连板断掉后 K线首次穿越20日均线的日期.

逻辑:
  1. 涨停/连板判定同 n_boards.py (本地K线, 按代码前缀分档涨停幅度)
  2. 对每只 N 连板票, 取其最后一次连板(>=N)的结束日
  3. 从结束日次日起向后扫描, 找首个 low<=MA20<=high (K线触及MA20) 的交易日

输出: 代码/名称/最高连板/连板结束日/首次穿MA20日/间隔交易日/收盘/MA20
"""
import unicodedata
import pandas as pd
from build_code_name import load_code_name

# ===================== 参数 =====================
KLINE_CSV = "../data/all_kline_26.csv"
START_DATE = "20260101"              # 起始交易日
N_BOARDS = 5                         # 连板数下限
MA_LEN = 20                          # 均线周期
# ===============================================


def _norm(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _zt_ratio_series(codes: pd.Series) -> pd.Series:
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
    ma_col = f"MA{MA_LEN}"

    # 涨停 + 连板数
    ratio = _zt_ratio_series(df["code"])
    df["涨停价"] = (df["preclose"] * (1 + ratio)).round(2)
    df["涨停"] = df["close"] >= df["涨停价"]
    df["断板"] = ~df["涨停"]
    df["seg"] = df.groupby("code")["断板"].cumsum()
    df["连板数"] = df.groupby(["code", "seg"])["涨停"].cumsum()

    # MA20 + 前日收盘(用于判定上穿)
    df[ma_col] = df.groupby("code")["close"].transform(lambda s: s.rolling(MA_LEN).mean())
    df["prev_close"] = df.groupby("code")["close"].shift(1)

    # 今年达到 N 连板及以上的票
    hot = df[(df["date"] >= start_norm) & (df["连板数"] >= N_BOARDS)]
    if hot.empty:
        print(f"今年({START_DATE}起) 无 {N_BOARDS} 连板及以上的个股")
        return

    # 每只票: 最高连板 + 连板段最后一天
    agg = hot.groupby("code").agg(
        最高连板=("连板数", "max"),
        连板结束日=("date", "max"),
    ).reset_index()

    name_map = load_code_name()
    records = []
    for _, r in agg.iterrows():
        code, end_date, max_b = r["code"], r["连板结束日"], int(r["最高连板"])
        # 断板次日起的切片
        sub = df[(df["code"] == code) & (df["date"] > end_date) & df[ma_col].notna()].reset_index(drop=True)
        # 红柱上穿: 前日close<MA20, 当日close>=MA20, 且为阳线(close>open)
        cross_mask = (
            (sub["prev_close"] < sub[ma_col])
            & (sub["close"] >= sub[ma_col])
            & (sub["close"] > sub["open"])
        )
        cross_idx = cross_mask[cross_mask].index

        rec = {
            "代码": code,
            "名称": name_map.get(code, "-"),
            "最高连板": max_b,
            "连板结束日": end_date,
        }
        if len(cross_idx) > 0:
            pos = cross_idx[0]
            first = sub.iloc[pos]
            rec.update({
                f"首次上穿MA{MA_LEN}日": first["date"],
                "间隔交易日": int(pos + 1),
                "收盘": f"{first['close']:.2f}",
                f"MA{MA_LEN}": f"{first[ma_col]:.2f}",
            })
        else:
            rec.update({
                f"首次上穿MA{MA_LEN}日": "尚未上穿",
                "间隔交易日": "-",
                "收盘": "-",
                f"MA{MA_LEN}": "-",
            })
        records.append(rec)

    out = pd.DataFrame(records).sort_values(
        ["最高连板", "连板结束日"], ascending=[False, True]
    )

    print(f"今年({START_DATE}起) {N_BOARDS}连板及以上: {len(out)} 只")
    print(f"找出连板断后 红柱首次上穿{MA_LEN}日均线之日\n")
    _print_table(out, {"最高连板", "间隔交易日", "收盘", f"MA{MA_LEN}"})


if __name__ == "__main__":
    main()
