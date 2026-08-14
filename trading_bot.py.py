
import ccxt
import pandas as pd
import time
import requests

# ----------------------------------------------------
# 1. إعدادات Telegram
# ----------------------------------------------------
TELEGRAM_TOKEN = "8781606392:AAG6eOJt5KMqouKEZZTfZ6wexhLG4xDBHZg"

def get_latest_chat_id():
    """جلب Chat ID تلقائياً من أحدث رسالة تلقاها البوت"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        res = requests.get(url).json()
        if res.get("ok") and res.get("result"):
            return str(res["result"][-1]["message"]["chat"]["id"])
    except Exception as e:
        print(f"خطأ فـ جلب Chat ID: {e}")
    return None

def send_telegram_msg(chat_id, message):
    """إرسال رسالة نصية عبر Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        return requests.post(url, data=payload).json()
    except Exception as e:
        print(f"خطأ فـ إرسال التليجرام: {e}")

# ----------------------------------------------------
# 2. إعدادات المنصة والتداول (Real vs Paper)
# ----------------------------------------------------
USE_REAL_TRADING = False  # رجعها True إيلا بغيتي تتداول بفلوس حقيقية فـ Binance

# مفاتيح Binance API (خاصة فقط بالتداول الحقيقي)
BINANCE_API_KEY = "YOUR_BINANCE_API_KEY"
BINANCE_SECRET_KEY = "YOUR_BINANCE_SECRET_KEY"

if USE_REAL_TRADING:
    exchange = ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_SECRET_KEY,
        'enableRateLimit': True
    })
    print("⚠️ البوت شغال فـ وضع التداول الحقيقي (Real Trading)!")
else:
    exchange = ccxt.binance({'enableRateLimit': True})
    print("🧪 البوت شغال فـ وضع التداول الوهمي (Paper Trading).")

# ----------------------------------------------------
# 3. إعدادات إدارة المخاطر والمحفظة
# ----------------------------------------------------
balance_usdt = 1000.0       # المحفظة الوهمية (1000 USDT)
btc_held = 0.0              # كمية البيتكوين
position = None             # حالة الصفقة (None أو "BUY")
buy_price = 0.0             # سعر الشراء لحساب الأرباح والخسائر

STOP_LOSS_PCT = 0.015       # 1.5% وقف الخسارة
TAKE_PROFIT_PCT = 0.020     # 2.0% جني الأرباح

symbol = 'BTC/USDT'
timeframe = '1m'            # فريم الدقيقة

# ----------------------------------------------------
# 4. دوال التحليل الفني والإشارات
# ----------------------------------------------------
def fetch_data():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    df['SMA_5'] = df['close'].rolling(window=5).mean()
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def get_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    buy_cond = (prev['SMA_5'] <= prev['SMA_20']) and (last['SMA_5'] > last['SMA_20']) and (last['RSI'] < 70)
    sell_cond = ((prev['SMA_5'] >= prev['SMA_20']) and (last['SMA_5'] < last['SMA_20'])) or (last['RSI'] > 75)
    
    if buy_cond:
        return "BUY"
    elif sell_cond:
        return "SELL"
    return "HOLD"

# ----------------------------------------------------
# 5. الحلقة الرئيسية للتشغيل
# ----------------------------------------------------
chat_id = get_latest_chat_id()
if chat_id:
    send_telegram_msg(chat_id, "🚀 TraderNux المطور شغال مع حماية Stop-Loss & Take-Profit!")

while True:
    try:
        if not chat_id:
            chat_id = get_latest_chat_id()

        data = fetch_data()
        data = calculate_indicators(data)
        signal = get_signal(data)
        
        current_price = data.iloc[-1]['close']
        current_rsi = round(data.iloc[-1]['RSI'], 2)

        # A. فحص حماية إدارة المخاطر (عند وجود صفقة مفتوحة)
        if position == "BUY":
            price_change = (current_price - buy_price) / buy_price

            # 1. حالة Stop-Loss (وقف الخسارة)
            if price_change <= -STOP_LOSS_PCT:
                balance_usdt = btc_held * current_price
                msg = f"🛑 وقف الخسارة (Stop-Loss)!\nPrice: ${current_price:.2f}\nخسارة: {price_change*100:.2f}%\nالمحفظة: ${balance_usdt:.2f} USDT"
                print(f"[RISK] {msg}")
                if chat_id: send_telegram_msg(chat_id, msg)
                btc_held = 0.0
                position = None
                buy_price = 0.0

            # 2. حالة Take-Profit (جني الأرباح)
            elif price_change >= TAKE_PROFIT_PCT:
                balance_usdt = btc_held * current_price
                msg = f"🎯 جني الأرباح (Take-Profit)!\nPrice: ${current_price:.2f}\nربح: +{price_change*100:.2f}%\nالمحفظة: ${balance_usdt:.2f} USDT"
                print(f"[PROFIT] {msg}")
                if chat_id: send_telegram_msg(chat_id, msg)
                btc_held = 0.0
                position = None
                buy_price = 0.0

        # B. تنفيذ الصفقات بناءً على الاستراتيجية العادية
        if signal == "BUY" and position is None:
            buy_price = current_price
            btc_held = balance_usdt / current_price
            balance_usdt = 0.0
            position = "BUY"
            msg = f"🟢 إشارة شراء (BUY)!\nPrice: ${current_price:.2f}\nRSI: {current_rsi}\nتم شراء: {btc_held:.5f} BTC\n🎯 TP: ${buy_price*(1+TAKE_PROFIT_PCT):.2f} | 🛑 SL: ${buy_price*(1-STOP_LOSS_PCT):.2f}"
            print(f"[TRADE] {msg}")
            if chat_id: send_telegram_msg(chat_id, msg)

        elif signal == "SELL" and position == "BUY":
            balance_usdt = btc_held * current_price
            profit_loss = ((current_price - buy_price) / buy_price) * 100
            msg = f"🔴 إشارة بيع (SELL)!\nPrice: ${current_price:.2f}\nالنتيجة: {profit_loss:+.2f}%\nالمحفظة الحالية: ${balance_usdt:.2f} USDT"
            print(f"[TRADE] {msg}")
            if chat_id: send_telegram_msg(chat_id, msg)
            btc_held = 0.0
            position = None
            buy_price = 0.0

        else:
            total_val = balance_usdt if position is None else btc_held * current_price
            print(f"Price: ${current_price:.2f} | RSI: {current_rsi} | Signal: {signal} | Wallet: ${total_val:.2f}")

        time.sleep(30)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)