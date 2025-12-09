import yfinance as yf
import pandas as pd
import requests
import json
import time
import os

# --- 設定密鑰 ---
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# --- 300+ 檔全方位戰略清單 (核心 150 + 熱門題材擴充) ---
STOCK_DB = {
    # === 1. 台灣 50 (台股心臟) ===
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

    # === 2. 中型 100 (潛力中堅) ===
    "1102": "亞泥", "1210": "大成", "1227": "佳格", "1304": "台聚", "1308": "亞聚",
    "1319": "東陽", "1402": "遠東新", "1476": "儒鴻", "1477": "聚陽", "1503": "士電",
    "1504": "東元", "1513": "中興電", "1519": "華城", "1560": "中砂", "1590": "亞德客",
    "1702": "南僑", "1707": "葡萄王", "1712": "興農", "1717": "長興", "1722": "台肥",
    "1723": "中碳", "1785": "光洋科", "1795": "美時", "1802": "台玻", "1907": "永豐餘",
    "2006": "東和鋼", "2014": "中鴻", "2027": "大成鋼", "2049": "上銀", "2101": "南港",
    "2105": "正新", "2201": "裕隆", "2204": "中華", "2312": "金寶", "2313": "華通",
    "2324": "仁寶", "2337": "旺宏", "2344": "華邦電", "2347": "聯強", "2352": "佳世達",
    "2353": "宏碁", "2354": "鴻準", "2356": "英業達", "2360": "致茂", "2362": "藍天",
    "2368": "金像電", "2376": "技嘉", "2377": "微星", "2383": "台光電", "2385": "群光",
    "2388": "威盛", "2392": "正崴", "2393": "億光", "2404": "漢唐", "2409": "友達",
    "2439": "美律", "2441": "超豐", "2449": "京元電", "2451": "創見", "2474": "可成",
    "2480": "敦陽科", "2492": "華新科", "2498": "宏達電", "2501": "國建", "2542": "興富發",
    "2606": "裕民", "2610": "華航", "2618": "長榮航", "2637": "慧洋", "3005": "神基",
    "3023": "信邦", "3035": "智原", "3036": "文曄", "3042": "晶技", "3044": "健鼎",
    "3189": "景碩", "3293": "鈊象", "3406": "玉晶光", "3443": "創意", "3532": "台勝科",
    "3661": "世芯", "3702": "大聯大", "4919": "新唐", "4958": "臻鼎", "4961": "天鈺",
    "4966": "譜瑞", "5269": "祥碩", "5522": "遠雄", "6176": "瑞儀", "6213": "聯茂",
    "6239": "力成", "6269": "台郡", "6271": "同欣電", "6278": "台表科", "6409": "旭隼",
    "6415": "矽力", "6456": "GIS", "6505": "台塑化", "6669": "緯穎", "6770": "力積電",
    "8046": "南電", "8069": "元太", "8454": "富邦媒", "8464": "億豐", "9904": "寶成",
    "9910": "豐泰", "9914": "美利達", "9917": "中保科", "9921": "巨大", "9941": "裕融",
    "9945": "潤泰新",

    # === 3. 擴充：軍工 & 航太 (政策加持) ===
    "2634": "漢翔", "8033": "雷虎", "2630": "亞航", "5284": "jpp-KY", "8222": "寶一",
    "2645": "長榮航太", "5222": "全訊", "5009": "榮剛", "4572": "駐龍", "4541": "晟田",
    "3029": "零壹", "2453": "凌群",

    # === 4. 擴充：AI 機器人 & 散熱 (黃仁勳概念) ===
    "2359": "所羅門", "4585": "達明", "8374": "羅昇", "2365": "昆盈", "2464": "盟立",
    "6188": "廣明", "3324": "雙鴻", "3013": "晟銘電", "2421": "建準", "3529": "力旺",
    "5274": "信驊", "3013": "晟銘電",

    # === 5. 擴充：生技 & 化工綠能 (防禦+綠電) ===
    "6446": "藥華藥", "6472": "保瑞", "4174": "浩鼎", "4147": "中裕", "6550": "北極星",
    "3176": "基亞", "1760": "寶齡", "4743": "合一", "4128": "中天", "4105": "東洋",
    "6541": "泰福", "6589": "台康生", "3705": "永信", "1720": "生達", "4164": "承業醫",
    "1514": "亞力", "1609": "大亞", "3708": "上緯", "9958": "世紀鋼", "6806": "森崴",
    "3027": "盛達", "1708": "東鹼", "1710": "東聯", "1727": "中華化", "4763": "材料",
    "4755": "三福化", "1773": "勝一", "9939": "宏全",

    # === 6. 擴充：熱門 ETF (大盤風向球) ===
    "0050": "元大台灣50", "0056": "元大高股息", "00878": "國泰永續高股息",
    "00919": "群益台灣精選", "00929": "復華台灣科技", "00940": "元大台灣價值",
    "006208": "富邦台50", "00713": "元大高息低波", "00881": "國泰台灣5G",
    "00631L": "元大台灣50正2", "00679B": "元大美債20年", "00687B": "國泰20年美債"
}

TARGET_STOCKS = sorted(list(STOCK_DB.keys()))

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
    k.iloc[0] = 50; d.iloc[0] = 50
    
    for i in range(1, len(df)):
        k.iloc[i] = (2/3) * k.iloc[i-1] + (1/3) * rsv.iloc[i]
        d.iloc[i] = (2/3) * d.iloc[i-1] + (1/3) * k.iloc[i]
    return k, d

def get_prediction(k_series, d_series, bias_pct):
    # 取得最近 3 天的 K 值 (用來判斷鈍化)
    k_now = k_series.iloc[-1]
    d_now = d_series.iloc[-1]
    k_prev1 = k_series.iloc[-2]
    k_prev2 = k_series.iloc[-3]
    
    # 1. 檢查鈍化 (Passivation)
    # 連續 3 天 K 值 > 80，代表超級強勢
    if k_now > 80 and k_prev1 > 80 and k_prev2 > 80:
        return "🚀高檔鈍化(飆)"

    # 2. 檢查乖離率 (過熱保護)
    if bias_pct > 20: return "⚠️乖離過大"
    
    # 3. KD 狀態
    if k_now > d_now and k_now < 50 and k_prev1 < d_series.iloc[-2]:
        return "📈低檔金叉(買)"
    if k_now > d_now and k_now < 80: 
        return "🔥多頭續攻"
    if k_now < d_now and k_now > 70: 
        return "🔻高檔死叉(賣)"
    
    return "➡️中性盤整"

def get_dynamic_support(current_price, df):
    ma_days = [5, 10, 20, 60]
    ma_values = {f"{d}MA": df['Close'].tail(d).mean() for d in ma_days}
    candidates = {k: v for k, v in ma_values.items() if v < current_price}
    if candidates:
        best_ma = max(candidates, key=candidates.get)
        return best_ma, candidates[best_ma]
    return "前低", df['Low'].min()

def get_pressure_from_volume(df):
    idx_max_vol = df['Volume'].idxmax()
    return df.loc[idx_max_vol]['High']

def analyze_market():
    print(f"🚀 啟動全方位 AI 掃描 (300+ 檔)...")
    
    strong_list = []
    ready_list = []
    
    count = 0
    total = len(TARGET_STOCKS)

    for code in TARGET_STOCKS:
        count += 1
        # 每 20 檔印一次進度，保持 Log 乾淨
        if count % 20 == 0: print(f"進度: {count}/{total}...")

        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            
            if len(df) < 60: continue
            
            k_series, d_series = calculate_kd(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            name = STOCK_DB.get(code, code)
            
            price = latest['Close']
            sma20 = df['Close'].tail(20).mean()
            sma60 = df['Close'].tail(60).mean()
            vol_ma5 = df['Volume'].tail(5).mean()
            pct_change = (price - prev['Close']) / prev['Close'] * 100
            bias_pct = (price - sma20) / sma20 * 100
            
            prediction = get_prediction(k_series, d_series, bias_pct)
            sup_n, sup_p = get_dynamic_support(price, df)
            res_p = get_pressure_from_volume(df)
            if price > res_p: res_p = df['High'].max()
            res_note = "(新高)" if price >= res_p * 0.98 else "(量壓)"

            # 避雷針濾網 (ETF 不適用避雷針濾網，因為ETF是追蹤指數，不容易被單一主力操弄)
            # 但為了保險起見，我們還是保留，但邏輯稍微放寬
            upper_shadow = latest['High'] - max(latest['Close'], latest['Open'])
            body = abs(latest['Close'] - latest['Open'])
            is_solid = upper_shadow < (body * 2.0) if body > 0 else True

            # ========== 策略 A: 強勢攻擊 ==========
            is_trend = price > sma20 and sma20 > sma60
            is_spike = latest['Volume'] > vol_ma5 * 1.3
            is_up = pct_change > 1.0
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
    msg = "【📊 AI 全方位掃描 (含ETF)】\n"
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

    msg += "(AI 結合 KD 鈍化與乖離)"
    
    if LINE_ACCESS_TOKEN:
        send_line_msg(msg)
        print("✅ 報告發送成功")
    else:
        print(msg)

if __name__ == "__main__":
    analyze_market()
