"""
etf  B,S 策略
"""


total_r = 6896      #总仓位
now_b = 0           #当前量
now_ratio = 0       #当前占比

B1, B2 = 0, 0

if now_b == 0 :
    B1 = total_r * 0.2
    print(f"""
        当前B量：{B1}
        """)
else:
    if now_ratio < 25:
        B2 = total_r * 0.05
    else:
        B2 = total_r * (0.03 - now_ratio / 100)
    print(f"""
        当前B量：{B2}
        """)

