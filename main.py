import yfinance as yf
import pandas as pd
import requests
import json
import time
import os

# --- 設定密鑰 ---
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# --- 股票代碼與中文名稱對照表 (台股權值股精選) ---
# 字典查詢速度最快，避免額外 API 請求
STOCK_MAP = {
    # 權值龍頭
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2308": "台達電", "2303": "聯電",
    "2881": "富邦金", "2882": "國泰金", "1301": "台塑", "2002": "中鋼", "2603": "長榮",
    "3711": "日月光", "2891": "中信金", "1216": "統一", "2886": "兆豐金", "2884": "玉山金",
    "5880": "合庫金", "2892": "第一金", "2885": "元大金", "2207": "和泰車", "2379": "瑞昱",
    "3045": "台灣大", "5871": "中租", "2345": "智邦", "3034": "聯詠", "2890": "永豐金",
    "2912": "統一超", "1101": "台泥", "4904": "遠傳", "2880": "華南金", "2883": "凱基金",
    "2887": "台新金", "2395": "研華", "2412": "中華電", "5876": "上海商銀", "6669": "緯穎",
    "3037": "欣興", "1605": "華新", "2059": "川湖", "2327": "國巨", "2408": "南亞科",
    "2609": "陽明", "2615": "萬海", "3017": "奇鋐", "3231": "緯創", "4938": "和碩",
    "2382": "廣達", "2357": "華碩", "3008": "大立光", "1303": "南亞",
    # 熱門中型與題材股
    "1513": "中興電", "1503": "士電", "1519": "華城", "1504": "東元", # 重電
    "3035": "智原", "3443": "創意", "3661": "世芯", "6531": "愛普",   # IP/IC
    "2376": "技嘉", "2356": "英業達", "3013": "晟銘電",               # AI 伺服器
    "3324": "雙鴻", "3017": "奇鋐",                                   # 散熱
    "8046": "南電", "3189": "景碩",                                   # ABF
    "2618": "長榮航", "2610": "華航",                                 # 航空
    "9904": "寶成", "9910": "豐泰"                                    # 傳產
}

# 取得所有要掃描的代碼
TARGET_STOCKS = sorted(list(STOCK_MAP.keys()))

def send_line_msg(msg):
    """ 使用 LINE Messaging API 推播訊息 """
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + str(LINE_ACCESS_TOKEN)
    }
    payload = {
        "to": str(LINE_USER_ID),
        "messages": [{"type": "text", "text": msg}]
    }
    try:
        requests.post(url, headers=headers, data=json.dumps(payload))
    except Exception as e:
        print(f"❌ 連線錯誤: {e}")

def analyze_market():
    print(f"🚀 開始執行全市場掃描，共 {len(TARGET_STOCKS)} 檔股票...")
    strong_stocks = []
    
    count = 0
    total = len(TARGET_STOCKS)

    for code in TARGET_STOCKS:
        count += 1
        if count % 10 == 0: print(f"進度: {count}/{total}...")

        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            
            # 改為抓取 3 個月 (3mo) 資料，以便計算 60 日高點壓力
            df = stock.history(period="3mo")
            
            if len(df) < 60: continue # 資料太短跳過
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- 技術指標計算 ---
            # 1. 20日均線 (作為支撐)
            sma20 = df['Close'].tail(20).mean()
            
            # 2. 60日最高價 (作為壓力)
            high_60 = df['High'].tail(60).max()
            
            # 3. 5日均量
            vol_ma5 = df['Volume'].tail(5).mean()
            
            # --- 篩選策略 (月線之上 + 爆量 + 收紅) ---
            is_bullish = latest['Close'] > sma20
            is_volume_spike = latest['Volume'] > vol_ma5 * 1.5
            is_red = latest['Close'] > prev['Close']
            pct_change = (latest['Close'] - prev['Close']) / prev['Close'] * 100

            # 漲幅大於 1% 才入選
            if is_bullish and is_volume_spike and is_red and pct_change > 1.0:
                
                # 取得中文名稱，如果沒有就顯示 Code
                name = STOCK_MAP.get(code, code)
                
                stock_data = {
                    "code": code,
                    "name": name,
                    "price": round(latest['Close'], 1),
                    "pct": round(pct_change, 2),
                    "support": round(sma20, 1),   # 支撐 = 月線
                    "pressure": round(high_60, 1) # 壓力 = 近季高點
                }
                strong_stocks.append(stock_data)
                print(f"🔥 抓到: {name} (+{stock_data['pct']}%)")
            
            time.sleep(0.5) 
            
        except Exception as e:
            print(f"Error {code}: {e}")
            continue

    # --- 整理排行榜與發送訊息 ---
    if strong_stocks:
        # 依漲幅排序
        strong_stocks.sort(key=lambda x: x['pct'], reverse=True)
        top_picks = strong_stocks[:8] # 最多顯示 8 檔，避免訊息太長被截斷

        msg_body = f"【📊 台股戰情室】\n"
        msg_body += f"強勢股掃描 (支撐/壓力)\n"
        msg_body += "=" * 16 + "\n"
        
        for s in top_picks:
            # 格式優化：
            # 🔥 2330 台積電 (+2.5%)
            # 💰 $1050 | 撐 1020 / 壓 1080
            msg_body += f"🔥 {s['code']} {s['name']} (+{s['pct']}%)\n"
            msg_body += f"💰 ${s['price']} | 撐 {s['support']} / 壓 {s['pressure']}\n"
            msg_body += "-" * 16 + "\n"
        
        msg_body += "(AI 計算僅供參考)"
        
        if LINE_ACCESS_TOKEN:
            send_line_msg(msg_body)
            print("✅ 完整報告已發送！")
    else:
        print("今日無符合條件之股票。")

if __name__ == "__main__":
    analyze_market()
