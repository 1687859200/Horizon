# -*- coding: utf-8 -*-
"""
构建 个股 -> 概念板块 反向索引 (缓存)

数据源: 东方财富概念板块
  - stock_board_concept_name_em()       所有概念板块列表
  - stock_board_concept_cons_em(symbol) 该板块成分股

输出: Horizon/data/concept_index.csv
  列: code, concepts   (concepts 用 '|' 分隔多个概念)

概念成分变化慢, 建议每周/月跑一次更新.
首次构建约 5 分钟(~400 个概念板块, 串行+限速); 之后查找秒级.
"""
import time
import akshare as ak
import pandas as pd

OUTPUT_FILE = "../data/concept_index.csv"
REQUEST_DELAY = 0.25
MAX_RETRY = 3


def to_ks_code(code6) -> str:
    c = str(code6).zfill(6)
    if c[0] in ("6", "9"):
        return f"sh.{c}"
    if c[0] in ("0", "3"):
        return f"sz.{c}"
    return f"bj.{c}"


def _fetch(fn, *args, retries=5, **kwargs):
    """带退避重试的请求(应对东财偶发断连/限流)"""
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt < retries - 1:
                wait = 3 * (attempt + 1)
                print(f"    请求失败({type(e).__name__}), {wait}秒后重试({attempt+1}/{retries}) ...")
                time.sleep(wait)
            else:
                raise


def build_index():
    print("获取概念板块列表 ...")
    concepts_df = _fetch(ak.stock_board_concept_name_em)
    names = concepts_df["板块名称"].tolist()
    total = len(names)
    print(f"共 {total} 个概念板块, 开始遍历成分股 ...\n")

    index = {}        # code -> [概念名...]
    ok, fail = 0, 0

    for i, name in enumerate(names, 1):
        for attempt in range(MAX_RETRY):
            try:
                cons = ak.stock_board_concept_cons_em(symbol=name)
                if cons is None or cons.empty:
                    ok += 1
                    break
                code_col = "代码" if "代码" in cons.columns else cons.columns[1]
                for code6 in cons[code_col].astype(str):
                    index.setdefault(to_ks_code(code6), []).append(name)
                ok += 1
                break
            except Exception as e:
                if attempt < MAX_RETRY - 1:
                    time.sleep(1.5 * (attempt + 1))
                else:
                    print(f"  [{i}/{total}] {name} 失败: {e}")
                    fail += 1
        if i % 20 == 0 or i == total:
            print(f"  进度 {i}/{total}  成功{ok} 失败{fail}  覆盖股票{len(index)}")
        time.sleep(REQUEST_DELAY)

    result = pd.DataFrame(
        [{"code": k, "concepts": "|".join(v)} for k, v in index.items()]
    )
    result.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n构建完成: {len(result)} 只股票, {total} 个概念板块 (成功{ok} 失败{fail})")
    print(f"已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_index()