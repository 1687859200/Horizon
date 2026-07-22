# -*- coding: utf-8 -*-
"""
构建 个股代码 -> 名称 映射表 (本地缓存)

数据源: akshare stock_info_a_code_name()
  一次调用拿全市场 ~5500 只股票的 6位代码 + 名称, 稳定快速 (约5秒).

输出: Horizon/data/code_name.csv
  列: code (sh.XXXXXX/sz.XXXXXX/bj.XXXXXX), name

股票改名频率低, 建议每月或季度跑一次更新.
用法:
    from build_code_name import load_code_name
    name_map = load_code_name()   # {sh.600206: "有研新材", ...}
"""
import akshare as ak
import pandas as pd

OUTPUT_FILE = "D:/Code/Python/Horizon/data/code_name.csv"


def to_ks_code(code6) -> str:
    """6位纯数字 -> 'sh.'/'sz.'/'bj.' 前缀(与 all_kline_26.csv 的 code 对齐)"""
    c = str(code6).zfill(6)
    if c[0] in ("6", "9"):       # 沪市主板/科创板/B股
        return f"sh.{c}"
    if c[0] in ("0", "3"):       # 深市主板/创业板
        return f"sz.{c}"
    return f"bj.{c}"             # 北交所


def build():
    print("拉取全市场 代码+名称 ...")
    df = ak.stock_info_a_code_name()
    df["code"] = df["code"].astype(str).str.zfill(6).map(to_ks_code)
    df.columns = ["code", "name"]
    df = df.sort_values("code").reset_index(drop=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"完成: {len(df)} 只 -> {OUTPUT_FILE}")
    # 抽样验证
    sample = df[df["code"].isin(["sh.600206", "sz.000070", "sh.600519", "sz.000001"])]
    if not sample.empty:
        print("\n抽样:")
        print(sample.to_string(index=False))


def load_code_name(path: str = OUTPUT_FILE) -> dict:
    """读取映射表 -> {code: name}; 文件不存在返回 {}"""
    try:
        df = pd.read_csv(path, dtype={"code": str})
        return dict(zip(df["code"], df["name"]))
    except FileNotFoundError:
        print(f"警告: {path} 不存在, 请先运行 build_code_name.py")
        return {}


if __name__ == "__main__":
    build()
