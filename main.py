import yfinance as yf
import pandas as pd
import requests
import json
import time
import os

# --- 設定密鑰 ---
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# --- 股票清單 ---
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
    """ 動態尋找均線支撐 """
    ma_days = [5, 10, 20, 60]
    ma_values = {f"{d}MA": df['Close'].tail(d).mean() for d in ma_days}
    candidates = {k: v for k, v in ma_values.items() if v < current_price}
    
    if candidates:
        best_ma_name = max(candidates, key=candidates.get)
        return best_ma_name, candidates[best_ma_name]
    return "前低", df['Low'].min()

def get_pressure_from_volume(df):
    """ 計算籌碼壓力 """
    idx_max_vol = df['Volume'].idxmax()
    return df.loc[idx_max_vol]['High']

def analyze_market():
    print(f"🚀 啟動雙策略掃描：強勢攻擊 vs 盤整蓄勢...")
    
    strong_list = [] # 策略A: 強勢股
    ready_list = []  # 策略B: 盤整蓄勢股
    
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
            name = STOCK_MAP.get(code, code)
            
            # --- 共同指標 ---
            price = latest['Close']
            sma20 = df['Close'].tail(20).mean()
            sma60 = df['Close'].tail(60).mean()
            vol_ma5 = df['Volume'].tail(5).mean()
            pct_change = (latest['Close'] - prev['Close']) / prev['Close'] * 100
            
            # 計算壓力支撐 (顯示用)
            sup_n, sup_p = get_dynamic_support(price, df)
            res_p = get_pressure_from_volume(df)
            res_note = "(新高)" if price > res_p else "(量壓)"
            if price > res_p: res_p = df['High'].max()

            # ========== 策略 A: 強勢攻擊股 (Trend Following) ==========
            # 條件：多頭排列 + 爆量 + 實體紅K
            is_trend = price > sma20 and sma20 > sma60
            is_spike = latest['Volume'] > vol_ma5 * 1.3
            is_up = pct_change > 1.0
            
            if is_trend and is_spike and is_up:
                strong_list.append({
                    "name": name, "code": code, "price": round(price, 1),
                    "pct": round(pct_change, 2), "sup_p": round(sup_p, 1), 
                    "sup_n": sup_n, "res_p": round(res_p, 1), "res_note": res_note
                })
                print(f"🔥 強勢: {name}")

            # ========== 策略 B: 盤整蓄勢股 (Consolidation Setup) ==========
            # 條件：
            # 1. 區間盤整：過去 10 天高低點震幅 < 8% (箱型整理)
            # 2. 蓄勢待發：現價位於箱型上半部 (準備突破)
            # 3. 偷吃貨：最近 3 天平均成交量 > 10 天平均 (價穩量增)
            # 4. 多頭預備：股價還是在季線(SMA60)之上 (長多保護短空)
            
            hist_10 = df.iloc[-10:]
            box_high = hist_10['High'].max()
            box_low = hist_10['Low'].min()
            
            # 箱型幅度 (Box Width)
            box_width = (box_high - box_low) / box_low
            is_tight_box = box_width < 0.08  # 8% 以內的壓縮
            
            # 位置 (Position in Box)
            box_mid = (box_high + box_low) / 2
            is_upper_half = price > box_mid # 收在箱型上半部
            
            # 量能佈局 (Accumulation)
            vol_3ma = df['Volume'].tail(3).mean()
            vol_10ma = df['Volume'].tail(10).mean()
            is_accumulating = vol_3ma > vol_10ma # 近期量能溫和放大
            
            # 長線保護
            is_long_trend = price > sma60 

            if is_tight_box and is_upper_half and is_accumulating and is_long_trend:
                # 為了避免跟強勢股重複，如果漲幅太大(>3%)通常已經噴出了，就不算盤整
                if pct_change < 3.0: 
                    ready_list.append({
                        "name": name, "code": code, "price": round(price, 1),
                        "box_h": round(box_high, 1), "box_l": round(box_low, 1),
                        "vol_ratio": round(vol_3ma/vol_10ma, 1) # 量能放大倍數
                    })
                    print(f"📦 蓄勢: {name} (箱型 {round(box_width*100,1)}%)")

            time.sleep(0.5) 
            
        except Exception: continue

    # --- 訊息發送 ---
    if strong_list or ready_list:
        msg = "【📊 AI 雙策略選股報告】\n"
        
        # 區塊 1: 強勢股
        if strong_list:
            strong_list.sort(key=lambda x: x['pct'], reverse=True)
            msg += f"🚀 噴出強勢股 (前{min(5, len(strong_list))}名)\n"
            msg += "="*16 + "\n"
            for s in strong_list[:5]:
                msg += f"🔥 {s['code']} {s['name']}\n"
                msg += f"💰 {s['price']} (+{s['pct']}%)\n"
                msg += f"🟢 撐 {s['sup_p']} / 🔴 壓 {s['res_p']}\n"
                msg += "-"*16 + "\n"
        
        # 區塊 2: 盤整蓄勢股
        if ready_list:
            # 依量能放大倍數排序 (量越大的越可能快噴)
            ready_list.sort(key=lambda x: x['vol_ratio'], reverse=True)
            msg += f"\n📦 盤整蓄勢股 (主力佈局)\n"
            msg += "="*16 + "\n"
            for s in ready_list[:5]:
                msg += f"👀 {s['code']} {s['name']}\n"
                msg += f"💰 現價 {s['price']} (區間整理)\n"
                msg += f"📊 區間: {s['box_l']} ~ {s['box_h']}\n"
                msg += f"⚡ 量能放大: {s['vol_ratio']}倍\n"
                msg += "-"*16 + "\n"

        msg += "(AI 僅供參考)"
        
        if LINE_ACCESS_TOKEN:
            send_line_msg(msg)
            print("✅ 雙策略報告已發送")
        else:
            print(msg)
    else:
        print("今日無符合條件個股")

if __name__ == "__main__":
    analyze_market()
