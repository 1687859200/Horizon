"""
mootdx 可用性测试
"""
from mootdx.quotes import Quotes

# 1. 连接标准行情服务器
client = Quotes.factory(market='std')
print("1. 连接标准行情服务器: OK")

# 2. 获取股票日K线 (以浦发银行 sh600000 为例)
df = client.bars(symbol='600000', frequency=9, offset=5)
print(f"2. 获取日K线 (600000, 最近5根):\n{df}\n")

# 3. 获取股票实时行情
df = client.quotes(symbol=['600000', '000001'])
print(f"3. 获取实时行情:\n{df}\n")

print("mootdx 库测试通过!")