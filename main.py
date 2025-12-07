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
    """
    動態尋找最貼近的均線支撐
    邏輯：檢查 5, 10, 20, 60 日線，找出「位於股價下方」且「最接近股價」的那條線。
    """
    ma_days = [5, 10, 20, 60]
    best_ma_val = 0
    best_ma_name = "無"
    
    # 計算各均線值
    ma_values = {}
    for d in ma_days:
        val = df['Close'].tail(d).mean()
        ma_values[f"{d}MA"] = val

    # 找出「小於現價」的最大均線 (最靠近的地板)
    candidates = {k: v for k, v in ma_values.items() if v < current_price}
    
    if candidates:
        # 找最大值 (最接近現價)
        best_ma_name = max(candidates, key=candidates.get)
        best_ma_val = candidates[best_ma_name]
    else:
        # 如果股價跌破所有均線，則支撐為前波低點
        best_ma_val = df['Low'].min()
        best_ma_name = "前低"

    return best_ma_name, best_ma_val

def get_pressure_from_volume(df):
    """
    計算籌碼壓力：過去 60 天內，成交量最大那一天的「最高價」
    """
    # 找到最大成交量的日期索引
    idx_max_vol = df['Volume'].idxmax()
    # 取得那一天的最高價
    pressure_price = df.loc[idx_max_vol]['High']
    return pressure_price

def analyze_market():
    print(f"🚀 啟動 AI 掃描：動態支撐/大量壓力運算中...")
    strong_stocks = []
    
    count = 0
    for code in TARGET_STOCKS:
        count += 1
        if count % 10 == 0: print(f"進度: {count}/{len(TARGET_STOCKS)}...")

        try:
            ticker = f"{code}.TW"
            stock = yf.Ticker(ticker)
            # 抓取 3 個月以計算 60 日內的爆量點
            df = stock.history(period="3mo")
            
            if len(df) < 60: continue
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- 基礎數據 ---
            sma20 = df['Close'].tail(20).mean()
            sma60 = df['Close'].tail(60).mean()
            vol_ma5 = df['Volume'].tail(5).mean()
            
            # --- 篩選條件 (多頭排列 + 攻擊量) ---
            # 1. 股價 > 月線 > 季線 (多頭排列)
            is_trend_up = latest['Close'] > sma20 and sma20 > sma60
            # 2. 爆量 (1.3倍即可，放寬標準以免漏掉緩步推升股)
            is_volume_spike = latest['Volume'] > vol_ma5 * 1.3
            # 3. 漲幅 > 1%
            pct_change = (latest['Close'] - prev['Close']) / prev['Close'] * 100

            if is_trend_up and is_volume_spike and pct_change > 1.0:
                
                # --- 進階計算 ---
                # A. 找動態支撐
                sup_name, sup_price = get_dynamic_support(latest['Close'], df)
                
                # B. 找爆量壓力
                res_price = get_pressure_from_volume(df)
                
                # 若現價已經突破爆量壓力，則壓力改為近半年高點(或顯示無壓)
                if latest['Close'] > res_price:
                    res_price = df['High'].max() # 改抓區間最高
                    res_note = "(新高)"
                else:
                    res_note = "(量壓)"

                name = STOCK_MAP.get(code, code)
                
                stock_data = {
                    "code": code,
                    "name": name,
                    "price": round(latest['Close'], 1),
                    "pct": round(pct_change, 2),
                    "sup_n": sup_name,            # 支撐名稱 (如 5MA)
                    "sup_p": round(sup_price, 1), # 支撐價格
                    "res_p": round(res_price, 1), # 壓力價格
                    "res_note": res_note          # 壓力備註
                }
                strong_stocks.append(stock_data)
                print(f"🔥 入選: {name} (撐在 {sup_name})")
            
            time.sleep(0.5) 
            
        except Exception:
            continue

    # --- 排序與發送 ---
    if strong_stocks:
        # 依照漲幅排序
        strong_stocks.sort(key=lambda x: x['pct'], reverse=True)
        top_picks = strong_stocks[:8]

        msg_body = f"【📈 AI 操盤手報告】\n"
        msg_body += f"策略：多頭排列 + 動態支撐\n"
        msg_body += "=" * 16 + "\n"
        
        for s in top_picks:
            # 格式：
            # 🔥 2330 台積電 (+2.5%)
            # 支撐: 1020(5MA) | 壓力: 1080(量壓)
            msg_body += f"🔥 {s['code']} {s['name']} (+{s['pct']}%)\n"
            msg_body += f"🟢 撐: {s['sup_p']}({s['sup_n']})\n"
            msg_body += f"🔴 壓: {s['res_p']}{s['res_note']}\n"
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
