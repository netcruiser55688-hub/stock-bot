import yfinance as yf
import pandas as pd
import requests
import json
import time
import os

# --- 設定密鑰 ---
LINE_ACCESS_TOKEN = os.environ.get("LINE_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# --- 選股清單 (可自行擴充) ---
TARGET_STOCKS = [
    "2330", "2317", "2454", "2308", "2303", "2881", "2882", "1301", "2002", "2603",
    "3231", "2382", "2357", "3008", "1303", "2891", "1216", "2886", "2884", "5880"
]

def send_line_msg(msg):
    """ 
    使用 LINE Messaging API 推播訊息 (Push Message)
    """
    url = "https://api.line.me/v2/bot/message/push"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + str(LINE_ACCESS_TOKEN)
    }
    
    payload = {
        "to": str(LINE_USER_ID),
        "messages": [
            {
                "type": "text",
                "text": msg
            }
        ]
    }
    
    try:
        # 發送請求
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        # 檢查結果
        if response.status_code == 200:
            print("✅ LINE 通知已發送！")
        else:
            print(f"❌ 發送失敗: {response.status_code}")
            print(response.text) # 印出錯誤訊息方便除錯
            
    except Exception as e:
        print(f"❌ 連線錯誤: {e}")

def analyze_market():
    print("🚀 開始執行全台股掃描...")
    strong_stocks = []
    
    # 建立訊息標題
    msg_body = "【📊 台股收盤強勢掃描】\n"
    msg_body += f"掃描範圍：台灣權值股 ({len(TARGET_STOCKS)}檔)\n"
    msg_body += "-" * 15 + "\n"

    for code in TARGET_STOCKS:
        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            df = stock.history(period="30d")
            
            if len(df) < 20: continue 
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- 篩選策略 ---
            # 1. 站上月線
            sma20 = df['Close'].tail(20).mean()
            # 2. 爆量 (大於 5日均量 1.5倍)
            vol_ma5 = df['Volume'].tail(5).mean()
            is_volume_spike = latest['Volume'] > vol_ma5 * 1.5
            # 3. 收紅
            is_up = latest['Close'] > prev['Close']

            if latest['Close'] > sma20 and is_volume_spike and is_up:
                change_pct = round((latest['Close'] - prev['Close']) / prev['Close'] * 100, 2)
                # 為了版面整潔，縮短每行訊息
                stock_info = f"🔥 {code} | 漲{change_pct}% | ${round(latest['Close'], 1)}"
                strong_stocks.append(stock_info)
                print(f"發現強勢股: {code}")
            
            time.sleep(1) # 避免太快被擋
            
        except Exception as e:
            print(f"Error {code}: {e}")
            continue

    # --- 整理與發送 ---
    if strong_stocks:
        msg_body += "\n".join(strong_stocks)
        msg_body += "\n\n(AI 僅供參考)"
        
        # 檢查是否設定了 Token
        if LINE_ACCESS_TOKEN and LINE_USER_ID:
            send_line_msg(msg_body)
        else:
            print("❌ 未設定 LINE Token，無法發送訊息。")
            print("請檢查 GitHub Secrets 或本機變數設定。")
            print(msg_body)
    else:
        print("今日無符合條件之股票，不發送通知。")

if __name__ == "__main__":
    analyze_market()
