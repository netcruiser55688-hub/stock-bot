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
    "1513": "中興電", "1503": "士電", "1519": "華城", "1504": "東元",
    "3035": "智原", "3443": "創意", "3661": "世芯", "6531": "愛普",
    "2376": "技嘉", "2356": "英業達", "3013": "晟銘電", "3324": "雙鴻",
    "8046": "南電", "3189": "景碩", "2618": "長榮航", "2610": "華航",
    "9904": "寶成", "9910": "豐泰", "9907": "統一實", "6285": "啟碁",
    "5347": "世界", "6446": "藥華藥", "3529": "力旺", "5274": "信驊",
    "2498": "宏達電", "2363": "矽統", "6116": "彩晶"
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

def calculate_kd(df, n=9):
    """ 計算 KD 指標 """
    low_list = df['Low'].rolling(window=n).min()
    high_list = df['High'].rolling(window=n).max()
    rsv = (df['Close'] - low_list) / (high_list - low_list) * 100
    rsv = rsv.fillna(50)
    
    k = pd.Series(0.0, index=df.index)
    d = pd.Series(0.0, index=df.index)
    k.iloc[0] = 50
    d.iloc[0] = 50
    
    for i in range(1, len(df)):
        k.iloc[i] = (2/3) * k.iloc[i-1] + (1/3) * rsv.iloc[i]
        d.iloc[i] = (2/3) * d.iloc[i-1] + (1/3) * k.iloc[i]
        
    return k, d

# --- 核心優化: AI 趨勢預判 (加入鈍化偵測) ---
def get_prediction(k_series, d_series, bias_pct):
    # 取得最近 3 天的 K 值 (用來判斷鈍化)
    k_now = k_series.iloc[-1]
    d_now = d_series.iloc[-1]
    
    k_prev1 = k_series.iloc[-2]
    k_prev2 = k_series.iloc[-3]
    
    # 1. 檢查鈍化 (Passivation)
    # 連續 3 天 K 值 > 80，代表超級強勢，指標鈍化
    if k_now > 80 and k_prev1 > 80 and k_prev2 > 80:
        return "🚀高檔鈍化(飆)"

    # 2. 檢查乖離率 (過熱保護)
    # 如果沒有鈍化，但乖離過大，則視為風險
    if bias_pct > 20: return "⚠️乖離過大"
    
    # 3. 一般 KD 狀態判定
    # 黃金交叉 (低檔轉強)
    if k_now > d_now and k_now < 50 and k_prev1 < d_series.iloc[-2]:
        return "📈低檔金叉(買)"
    
    # 黃金交叉 (續強)
    if k_now > d_now and k_now < 80: 
        return "🔥多頭續攻"
    
    # 死亡交叉 (高檔修正)
    if k_now < d_now and k_now > 70: 
        return "🔻高檔死叉(賣)"
    
    return "➡️中性盤整"

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
    print(f"🚀 啟動 AI 掃描 (含高檔鈍化偵測)...")
    
    strong_list = []
    ready_list = []
    
    count = 0
    for code in TARGET_STOCKS:
        count += 1
        if count % 10 == 0: print(f"進度: {count}/{len(TARGET_STOCKS)}...")

        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) < 60: continue
            
            k_series, d_series = calculate_kd(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            name = STOCK_MAP.get(code, code)
            
            price = latest['Close']
            sma20 = df['Close'].tail(20).mean()
            sma60 = df['Close'].tail(60).mean()
            vol_ma5 = df['Volume'].tail(5).mean()
            pct_change = (price - prev['Close']) / prev['Close'] * 100
            bias_pct = (price - sma20) / sma20 * 100
            
            # --- 取得預判 (傳入整個 Series 以判斷鈍化) ---
            prediction = get_prediction(k_series, d_series, bias_pct)

            sup_n, sup_p = get_dynamic_support(price, df)
            res_p = get_pressure_from_volume(df)
            if price > res_p: res_p = df['High'].max()
            res_note = "(新高)" if price >= res_p * 0.98 else "(量壓)"

            # 避雷針濾網
            upper_shadow = latest['High'] - max(latest['Close'], latest['Open'])
            body = abs(latest['Close'] - latest['Open'])
            is_solid = upper_shadow < (body * 1.5) if body > 0 else False

            # ========== 策略 A: 強勢攻擊 ==========
            is_trend = price > sma20 and sma20 > sma60
            is_spike = latest['Volume'] > vol_ma5 * 1.3
            is_up = pct_change > 1.0
            
            # 如果是鈍化狀態，就算量縮也算強勢 (因為主力鎖碼)
            is_passivation = "鈍化" in prediction
            
            if is_trend and is_up and is_solid and (is_spike or is_passivation):
                strong_list.append({
                    "name": name, "code": code, "price": round(price, 1),
                    "pct": round(pct_change, 2), "sup_p": round(sup_p, 1), 
                    "res_p": round(res_p, 1), "pred": prediction
                })
                print(f"🔥 強勢: {name} ({prediction})")

            # ========== 策略 B: 盤整蓄勢 ==========
            hist_10 = df.iloc[-10:]
            box_width = (hist_10['High'].max() - hist_10['Low'].min()) / hist_10['Low'].min()
            is_tight_box = box_width < 0.12
            is_upper_half = price > (hist_10['High'].max() + hist_10['Low'].min()) / 2
            
            vol_3ma = df['Volume'].tail(3).mean()
            vol_10ma = df['Volume'].tail(10).mean()
            is_accumulating = vol_3ma > vol_10ma 
            
            k_now = k_series.iloc[-1]
            d_now = d_series.iloc[-1]
            is_kd_gold = k_now > d_now and k_series.iloc[-2] < d_series.iloc[-2]

            if is_tight_box and is_upper_half and is_accumulating and (is_kd_gold or is_trend):
                 if pct_change < 4.0: 
                    ready_list.append({
                        "name": name, "code": code, "price": round(price, 1),
                        "box_h": round(hist_10['High'].max(), 1), 
                        "box_l": round(hist_10['Low'].min(), 1),
                        "vol_ratio": round(vol_3ma/vol_10ma, 1),
                        "pred": "🚀蓄勢待發" if is_kd_gold else "👀區間整理"
                    })
                    print(f"📦 蓄勢: {name}")

            time.sleep(0.5) 
            
        except Exception: continue

    # --- 訊息組裝 ---
    msg = "【📊 AI 隔日預判 (含鈍化)】\n"
    msg += f"🔥 強勢: {len(strong_list)} | 📦 蓄勢: {len(ready_list)}\n"
    msg += "="*16 + "\n"

    if not strong_list and not ready_list:
        msg += "今日無明確訊號，建議觀望。"
    else:
        if strong_list:
            strong_list.sort(key=lambda x: x['pct'], reverse=True)
            msg += f"🚀 強勢股 (Top 10):\n"
            for s in strong_list[:10]:
                msg += f"🔥 {s['code']} {s['name']} {s['pred']}\n"
                msg += f"💰 {s['price']} (+{s['pct']}%)\n"
                msg += f"🟢 撐 {s['sup_p']} / 🔴 壓 {s['res_p']}\n"
                msg += "-"*16 + "\n"

        if ready_list:
            ready_list.sort(key=lambda x: x['vol_ratio'], reverse=True)
            msg += f"\n📦 盤整蓄勢 (Top 10):\n"
            for s in ready_list[:10]:
                msg += f"👀 {s['code']} {s['name']} {s['pred']}\n"
                msg += f"💰 {s['price']} (整理)\n"
                msg += f"📊 區間:{s['box_l']}~{s['box_h']}\n"
                msg += "-"*16 + "\n"

    msg += "(AI 偵測 KD 鈍化與乖離)"
    
    if LINE_ACCESS_TOKEN:
        send_line_msg(msg)
        print("✅ 報告發送成功")
    else:
        print(msg)

if __name__ == "__main__":
    analyze_market()
