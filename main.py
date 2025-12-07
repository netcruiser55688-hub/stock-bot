import yfinance as yf
import pandas as pd
import requests
import json
import time
import os

# --- 設定密鑰 ---
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# --- 股票清單 (台股權值與熱門股) ---
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
    "9904": "寶成", "9910": "豐泰", "9907": "統一實",                 # 傳產
    "6285": "啟碁", "5347": "世界", "6446": "藥華藥"                  # 其他
}

TARGET_STOCKS = sorted(list(STOCK_MAP.keys()))

def send_line_msg(msg):
    """ LINE Messaging API """
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

def get_dynamic_support(current_price, df):
    """ 動態尋找最貼近的均線支撐 """
    ma_days = [5, 10, 20, 60]
    best_ma_val = 0
    best_ma_name = "無"
    
    ma_values = {}
    for d in ma_days:
        val = df['Close'].tail(d).mean()
        ma_values[f"{d}MA"] = val

    candidates = {k: v for k, v in ma_values.items() if v < current_price}
    
    if candidates:
        best_ma_name = max(candidates, key=candidates.get)
        best_ma_val = candidates[best_ma_name]
    else:
        best_ma_val = df['Low'].min()
        best_ma_name = "前低"

    return best_ma_name, best_ma_val

def get_pressure_from_volume(df):
    """ 計算籌碼壓力：大量K棒高點 """
    idx_max_vol = df['Volume'].idxmax()
    pressure_price = df.loc[idx_max_vol]['High']
    return pressure_price

def analyze_market():
    print(f"🚀 啟動 AI 掃描：多頭趨勢 + 關鍵價位運算...")
    strong_stocks = []
    
    count = 0
    for code in TARGET_STOCKS:
        count += 1
        if count % 10 == 0: print(f"進度: {count}/{len(TARGET_STOCKS)}...")

        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            df = stock.history(period="3mo")
            
            if len(df) < 60: continue
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            sma20 = df['Close'].tail(20).mean()
            sma60 = df['Close'].tail(60).mean()
            vol_ma5 = df['Volume'].tail(5).mean()
            
            # --- 篩選條件 ---
            is_trend_up = latest['Close'] > sma20 and sma20 > sma60
            is_volume_spike = latest['Volume'] > vol_ma5 * 1.3
            pct_change = (latest['Close'] - prev['Close']) / prev['Close'] * 100

            if is_trend_up and is_volume_spike and pct_change > 1.0:
                
                # 計算支撐與壓力
                sup_name, sup_price = get_dynamic_support(latest['Close'], df)
                res_price = get_pressure_from_volume(df)
                
                if latest['Close'] > res_price:
                    res_price = df['High'].max()
                    res_note = "(新高)"
                else:
                    res_note = "(量壓)"

                name = STOCK_MAP.get(code, code)
                
                stock_data = {
                    "code": code,
                    "name": name,
                    "price": round(latest['Close'], 1), # 現價
                    "pct": round(pct_change, 2),        # 漲幅
                    "sup_n": sup_name,
                    "sup_p": round(sup_price, 1),
                    "res_p": round(res_price, 1),
                    "res_note": res_note
                }
                strong_stocks.append(stock_data)
                print(f"🔥 入選: {name} ${stock_data['price']}")
            
            time.sleep(0.5) 
            
        except Exception:
            continue

    # --- 排序與發送 ---
    if strong_stocks:
        strong_stocks.sort(key=lambda x: x['pct'], reverse=True)
        top_picks = strong_stocks[:8]

        msg_body = f"【📈 AI 操盤手報告】\n"
        msg_body += f"強勢股關鍵價位監控\n"
        msg_body += "=" * 16 + "\n"
        
        for s in top_picks:
            # 格式調整：更清晰的四行排列
            # 🔥 2330 台積電
            # 💰 現價: 1050.0 (+2.5%)
            # 🟢 支撐: 1020.0 (5MA)
            # 🔴 壓力: 1080.0 (量壓)
            
            msg_body += f"🔥 {s['code']} {s['name']}\n"
            msg_body += f"💰 現價: {s['price']} (+{s['pct']}%)\n"
            msg_body += f"🟢 支撐: {s['sup_p']} ({s['sup_n']})\n"
            msg_body += f"🔴 壓力: {s['res_p']} {s['res_note']}\n"
            msg_body += "-" * 16 + "\n"
        
        msg_body += "(AI 計算僅供參考)"
        
        if LINE_ACCESS_TOKEN:
            send_line_msg(msg_body)
            print("✅ 報告發送成功")
        else:
            print(msg_body)
    else:
        print("今日盤勢震盪，無符合強勢多頭條件個股。")

if __name__ == "__main__":
    analyze_market()
