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

# --- 優化功能 1: 檢查 K 棒結構 (過濾避雷針) ---
def is_solid_candle(open_p, close_p, high_p, low_p):
    """
    判斷是否為實體強勢紅 K (拒絕長上影線)
    規則：上影線長度 不得超過 實體長度的 1 倍
    """
    if close_p <= open_p: return False # 收黑直接淘汰
    
    body_len = close_p - open_p
    upper_shadow = high_p - close_p
    
    # 如果上影線太長 (超過實體的 1.2 倍)，代表賣壓重，容易假突破
    if upper_shadow > body_len * 1.2:
        return False
    return True

# --- 優化功能 2: 檢查乖離率 (避免追高) ---
def get_bias_status(price, sma20):
    """ 計算乖離率：(現價 - 月線) / 月線 """
    bias = (price - sma20) / sma20 * 100
    if bias > 20: return "⚠️過熱"
    if bias > 15: return "偏高"
    return "正常"

def get_dynamic_support(current_price, df):
    ma_days = [5, 10, 20, 60]
    ma_values = {f"{d}MA": df['Close'].tail(d).mean() for d in ma_days}
    candidates = {k: v for k, v in ma_values.items() if v < current_price}
    if candidates:
        best_ma_name = max(candidates, key=candidates.get)
        return best_ma_name, candidates[best_ma_name]
    return "前低", df['Low'].min()

def get_pressure_from_volume(df):
    idx_max_vol = df['Volume'].idxmax()
    return df.loc[idx_max_vol]['High']

def analyze_market():
    print(f"🚀 啟動極致精準掃描 (Top 10 + 避雷針過濾)...")
    
    strong_list = []
    ready_list = []
    
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
            
            # 基礎數據
            price = latest['Close']
            open_p = latest['Open']
            high_p = latest['High']
            low_p = latest['Low']
            
            sma20 = df['Close'].tail(20).mean()
            sma60 = df['Close'].tail(60).mean()
            vol_ma5 = df['Volume'].tail(5).mean()
            pct_change = (price - prev['Close']) / prev['Close'] * 100
            
            # 進階運算
            sup_n, sup_p = get_dynamic_support(price, df)
            res_p = get_pressure_from_volume(df)
            res_note = "(新高)" if price > res_p else "(量壓)"
            if price > res_p: res_p = df['High'].max()
            
            bias_status = get_bias_status(price, sma20)

            # --- 全域濾網 (Global Filter) ---
            # 1. 必須收紅 (今日收盤 > 昨日收盤)
            # 2. 必須是實體紅K (過濾長上影線/避雷針)
            if pct_change <= 0 or not is_solid_candle(open_p, price, high_p, low_p):
                continue

            # ========== 策略 A: 強勢攻擊 (Precision Mode) ==========
            is_trend = price > sma20 and sma20 > sma60
            # 量能加嚴：除了大於均量，也要大於昨日量的 1.0 倍 (確保量沒縮)
            is_spike = latest['Volume'] > vol_ma5 * 1.3 and latest['Volume'] > prev['Volume']
            is_up = pct_change > 1.5 # 漲幅要求稍微提高到 1.5%
            
            if is_trend and is_spike and is_up:
                strong_list.append({
                    "name": name, "code": code, "price": round(price, 1),
                    "pct": round(pct_change, 2), "sup_p": round(sup_p, 1), 
                    "sup_n": sup_n, "res_p": round(res_p, 1), "res_note": res_note,
                    "bias": bias_status
                })
                print(f"🔥 強勢: {name}")

            # ========== 策略 B: 盤整蓄勢 (Precision Mode) ==========
            hist_10 = df.iloc[-10:]
            box_high = hist_10['High'].max()
            box_low = hist_10['Low'].min()
            box_width = (box_high - box_low) / box_low
            
            is_tight_box = box_width < 0.08
            box_mid = (box_high + box_low) / 2
            is_upper_half = price > box_mid
            
            vol_3ma = df['Volume'].tail(3).mean()
            vol_10ma = df['Volume'].tail(10).mean()
            is_accumulating = vol_3ma > vol_10ma 
            is_long_trend = price > sma60 

            if is_tight_box and is_upper_half and is_accumulating and is_long_trend:
                if pct_change < 4.0: # 盤整股漲幅不宜過大，太大就變噴出了
                    ready_list.append({
                        "name": name, "code": code, "price": round(price, 1),
                        "box_h": round(box_high, 1), "box_l": round(box_low, 1),
                        "vol_ratio": round(vol_3ma/vol_10ma, 1),
                        "bias": bias_status
                    })
                    print(f"📦 蓄勢: {name}")

            time.sleep(0.5) 
            
        except Exception: continue

    # --- 訊息組裝 ---
    msg = "【📊 AI 極致精準選股】\n"
    msg += f"🔥 強勢: {len(strong_list)} | 📦 蓄勢: {len(ready_list)}\n"
    msg += "="*16 + "\n"

    if not strong_list and not ready_list:
        msg += "今日無符合「實體紅K+有量」之標的。\n避開假突破風險，建議觀望。"
    else:
        # 強勢股 (Top 10)
        if strong_list:
            strong_list.sort(key=lambda x: x['pct'], reverse=True)
            for s in strong_list[:10]:
                msg += f"🔥 {s['code']} {s['name']}\n"
                msg += f"💰 {s['price']} (+{s['pct']}%)\n"
                if s['bias'] != "正常": msg += f"⚠️ 乖離{s['bias']} (勿追高)\n"
                msg += f"🟢 撐 {s['sup_p']} / 🔴 壓 {s['res_p']}\n"
                msg += "-"*16 + "\n"

        # 蓄勢股 (Top 10)
        if ready_list:
            ready_list.sort(key=lambda x: x['vol_ratio'], reverse=True)
            msg += f"\n📦 盤整蓄勢 (籌碼安定)\n"
            msg += "-"*16 + "\n"
            for s in ready_list[:10]:
                msg += f"👀 {s['code']} {s['name']}\n"
                msg += f"💰 {s['price']} (區間:{s['box_l']}~{s['box_h']})\n"
                msg += f"⚡ 量能放大: {s['vol_ratio']}倍\n"
                msg += "-"*16 + "\n"

    msg += "(AI 過濾上影線與假突破)"
    
    if LINE_ACCESS_TOKEN:
        send_line_msg(msg)
        print("✅ 報告發送成功")
    else:
        print(msg)

if __name__ == "__main__":
    analyze_market()
