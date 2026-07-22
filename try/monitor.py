import flet as ft
import threading
import time
from mootdx.quotes import Quotes


# ── 配置区 ──
STOCKS = [
    # {"code": "002141", "name": "X"},
    {"code": "000066", "name": "Z"}
]



def main(page: ft.Page):
    # ── 窗口配置 ──
    page.window.frameless = True
    page.window.bgcolor = ft.Colors.TRANSPARENT
    page.window.always_on_top = True
    page.window.resizable = False
    page.window.width = 130
    page.window.height = 50
    _codes = [s["code"] for s in STOCKS]
    page.window.left = 100
    page.window.top = 100
    page.bgcolor = ft.Colors.TRANSPARENT
    page.padding = 0
    page.spacing = 0

    def on_key(e):
        if e.key == "Escape":
            page.window.destroy()
    page.on_keyboard_event = on_key

    # ── 每只票一行控件 ──
    rows = []
    for _ in STOCKS:
        code_lbl = ft.Text("--", size=11, color="#ffffff", font_family="Consolas")
        pct_lbl = ft.Text("--", size=11, color="#ffffff", font_family="Consolas")
        dir_lbl = ft.Text("--", size=11, color="#ffffff", font_family="Consolas")
        ma_lbl = ft.Text("--", size=11, color="#ffffff", font_family="Consolas")
        rows.append({
            "code": code_lbl, "pct": pct_lbl, "dir": dir_lbl, "ma": ma_lbl,
            "prev_price": None,  # 记住上一次价格
            "row": ft.Row(
                [code_lbl, pct_lbl, dir_lbl, ma_lbl],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        })

    page.add(ft.WindowDragArea(
        ft.Container(
            content=ft.Column([r["row"] for r in rows], spacing=0),
            height=page.window.height,
        )
    ))

    # ── 数据层 ──
    client = None

    def refresh():
        nonlocal client
        try:
            client = Quotes.factory(market='std')
            print("mootdx 连接成功")
        except Exception as e:
            print(f"mootdx 连接失败: {e}")
            return

        while True:
            try:
                _update()
            except Exception as e:
                print(f"刷新失败: {e}")
            time.sleep(6)

    def _update():
        # 批量获取行情
        q = client.quotes(symbol=_codes)
        if q is None or q.empty:
            return

        for i, row_data in enumerate(rows):
            r = q.iloc[i]
            price = float(r['price'])
            last_close = float(r['last_close'])

            row_data["code"].value = STOCKS[i]["name"]

            # 涨幅%
            pct = (price - last_close) / last_close * 100
            row_data["pct"].value = f"{pct:+.2f}%"

            # 股价方向 (与上次刷新比)
            prev = row_data["prev_price"]
            if prev is not None:
                if price > prev:
                    row_data["dir"].value = "▲"
                    row_data["dir"].color = "#ff4444"
                elif price < prev:
                    row_data["dir"].value = "▼"
                    row_data["dir"].color = "#00ff00"
                else:
                    row_data["dir"].value = "—"
                    row_data["dir"].color = "#ffffff"
            row_data["prev_price"] = price

            # 分时均线差值 (成交均价 = 成交额 / 成交量)
            vol = float(r['vol'])
            amount = float(r['amount'])
            if vol > 0:
                vwap = amount / (vol * 100)  # vol单位是手，转成股
                gap = price - vwap
                row_data["ma"].value = f"{gap:+.2f}"
                row_data["ma"].color = "#ff4444" if abs(gap) < 0.1 else "#ffffff"
            else:
                row_data["ma"].value = "--"

        page.update()

    threading.Thread(target=refresh, daemon=True).start()


ft.app(target=main)