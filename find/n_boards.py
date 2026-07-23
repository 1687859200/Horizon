# -*- coding: utf-8 -*-
"""
找出今年 N 连板及以上的个股 (N 可调).

连板: 连续交易日收盘触及涨停价.
  主板 10% / 创业板·科创板 20% / 北交所 30% (按代码前缀分档, 本地判定).
  ST 股(5%涨停)按 10% 判定, 可能漏识别 → 如需精确再补 ST 名单.

参数: N_BOARDS(连板数下限), START_DATE(起始交易日)
"""
import unicodedata
import pandas as pd
from build_code_name import load_code_name

# ===================== 参数 =====================
KLINE_CSV = "../data/all_kline_26.csv"
START_DATE = "20260101"              # 起始交易日 YYYYMMDD
N_BOARDS = 5                         # 连板数下限(>=此值才入选)
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

    # 涨停判定 (本地, 按代码前缀分档)
    ratio = _zt_ratio_series(df["code"])
    df["涨停价"] = (df["preclose"] * (1 + ratio)).round(2)
    df["涨停"] = df["close"] >= df["涨停价"]

    # 连板数: 连续涨停累计天数, 遇断板归零 (向量化 seg 技巧)
    df["断板"] = ~df["涨停"]
    df["seg"] = df.groupby("code")["断板"].cumsum()
    df["连板数"] = df.groupby(["code", "seg"])["涨停"].cumsum()

    # 今年达到 N 连板及以上的行
    hot = df[(df["date"] >= start_norm) & (df["连板数"] >= N_BOARDS)].copy()
    if hot.empty:
        print(f"今年({START_DATE}起) 无 {N_BOARDS} 连板及以上的个股")
        return

    # 每只票: 首次达N那天(最早一行) + 今年最高连板
    first_rows = hot.sort_values(["code", "date"]).groupby("code", as_index=False).first()
    first_rows["最高连板"] = first_rows["code"].map(hot.groupby("code")["连板数"].max())

    name_map = load_code_name()
    first_rows["名称"] = first_rows["code"].map(lambda c: name_map.get(c, "-"))

    out = pd.DataFrame({
        "代码": first_rows["code"].values,
        "名称": first_rows["名称"].values,
        "最高连板": first_rows["最高连板"].astype(int).values,
        f"达{N_BOARDS}板日": first_rows["date"].values,
        "收盘": [f"{x:.2f}" for x in first_rows["close"].values],
        "成交额": [_fmt_amount(x) for x in first_rows["amount"].values],
        "换手率": [f"{x:.2f}%" if pd.notna(x) else "-" for x in first_rows["turn"].values],
    })
    out = out.sort_values(["最高连板", f"达{N_BOARDS}板日"], ascending=[False, True])

    print(f"今年({START_DATE}起) {N_BOARDS}连板及以上个股: {len(out)} 只\n")
    _print_table(out, {"最高连板", "收盘", "成交额", "换手率"})

    # 连板分布
    print("\n连板分布:")
    for n, g in out.groupby("最高连板"):
        print(f"  {n}连板: {len(g)} 只")


if __name__ == "__main__":
    main()
