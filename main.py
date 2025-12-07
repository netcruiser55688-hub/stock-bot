import yfinance as yf
import pandas as pd
import requests
import json
import time
import os

# --- 設定密鑰 ---
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# --- 台灣 50 (0050) + 中型 100 (0051) 成分股清單 ---
# 為了避免爬蟲失效，直接內建這 150 檔熱門權值股
ALL_STOCKS = [
    # 台灣 50
    "2330", "2317", "2454", "2308", "2303", "2881", "2882", "1301", "2002", "2603",
    "3231", "2382", "2357", "3008", "1303", "2891", "1216", "2886", "2884", "5880",
    "2892", "2885", "2207", "2379", "3045", "5871", "2345", "3034", "2890", "2912",
    "1101", "4904", "2880", "2883", "2887", "2395", "2412", "3711", "5876", "6669",
    "3037", "1605", "2059", "2327", "2408", "2609", "2615", "3017", "3231", "4938",
    # 中型 100 (精選部分高流動性代表)
    "1102", "1210", "1227", "1304", "1308", "1319", "1402", "1434", "1476", "1477",
    "1503", "1504", "1513", "1560", "1590", "1605", "1702", "1707", "1712", "1717",
    "1722", "1723", "1785", "1795", "1802", "1907", "2006", "2014", "2027", "2049",
    "2101", "2105", "2201", "2204", "2312", "2313", "2324", "2337", "2344", "2347",
    "2352", "2353", "2354", "2356", "2360", "2362", "2368", "2376", "2377", "2383",
    "2385", "2388", "2392", "2393", "2404", "2409", "2439", "2441", "2449", "2451",
    "2474", "2480", "2492", "2498", "2501", "2542", "2606", "2610", "2618", "2637",
    "3005", "3023", "3035", "3036", "3042", "3044", "3189", "3293", "3406", "3443",
    "3532", "3661", "3702", "4919", "4958", "4961", "4966", "5269", "5522", "6176",
    "6213", "6239", "6269", "6271", "6278", "6409", "6415", "6456", "6505", "6669",
    "6770", "8046", "8069", "8454", "8464", "9904", "9910", "9914", "9917", "9921",
    "9941", "9945"
]

# 移除重複代碼 (以防萬一)
TARGET_STOCKS = sorted(list(set(ALL_STOCKS)))

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
    
    # 進度條計數器
    count = 0
    total = len(TARGET_STOCKS)

    for code in TARGET_STOCKS:
        count += 1
        # 在 GitHub Log 顯示簡易進度，每 10 檔印一次，避免 Log 太長
        if count % 10 == 0:
            print(f"進度: {count}/{total}...")

        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            df = stock.history(period="30d")
            
            if len(df) < 20: continue 
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- 嚴格篩選策略 ---
            # 1. 站上月線 (趨勢多頭)
            sma20 = df['Close'].tail(20).mean()
            # 2. 爆量 (大於 5日均量 1.5倍)
            vol_ma5 = df['Volume'].tail(5).mean()
            is_volume_spike = latest['Volume'] > vol_ma5 * 1.5
            # 3. 實體紅K (收盤 > 開盤 且 收盤 > 昨天收盤)
            is_red_candle = latest['Close'] > latest['Open'] and latest['Close'] > prev['Close']
            # 4. 漲幅大於 1% (過濾掉那種只漲 0.1% 的盤整股)
            change_pct = (latest['Close'] - prev['Close']) / prev['Close'] * 100

            if latest['Close'] > sma20 and is_volume_spike and is_red_candle and change_pct > 1.0:
                stock_data = {
                    "code": code,
                    "price": round(latest['Close'], 1),
                    "pct": round(change_pct, 2)
                }
                strong_stocks.append(stock_data)
                print(f"🔥 抓到飆股: {code} (+{stock_data['pct']}%)")
            
            # ⚠️ 關鍵：增加休息時間，避免掃 150 檔被 Yahoo 封鎖 IP
            time.sleep(0.8) 
            
        except Exception as e:
            print(f"Error {code}: {e}")
            continue

    # --- 整理與排序 (排行榜機制) ---
    if strong_stocks:
        # 依照漲幅由高到低排序 (最強的在上面)
        strong_stocks.sort(key=lambda x: x['pct'], reverse=True)
        
        # 只取前 10 名，避免訊息太長
        top_picks = strong_stocks[:10]

        msg_body = f"【🏆 台股 150 大掃描】\n"
        msg_body += f"強勢股 TOP {len(top_picks)} (月線之上+爆量)\n"
        msg_body += "-" * 18 + "\n"
        
        for s in top_picks:
            msg_body += f"🔥 {s['code']} | 漲{s['pct']}% | ${s['price']}\n"
        
        msg_body += "\n(AI 僅供參考，投資自負風險)"
        
        # 發送
        if LINE_ACCESS_TOKEN and LINE_USER_ID:
            send_line_msg(msg_body)
            print("✅ 排行榜通知已發送！")
        else:
            print(msg_body)
    else:
        print("今日市場疲弱，無符合條件之強勢股。")

if __name__ == "__main__":
    analyze_market()
