import os
import time
import threading
import requests
import ccxt
import pandas as pd

# ==================== الإعدادات الأساسية ====================
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1m'
POSITION_SIZE_USDT = 10.0
INITIAL_STOP_LOSS_PCT = 0.008   # وقف خسارة ابتدائي: 0.8%
TRAILING_GAP_PCT = 0.005        # مسافة التتبع للربح المتحرك: 0.5%
FEE_PCT = 0.001                 # 0.1% عمولة المنصة

REAL_TRADING = False  

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "YOUR_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "YOUR_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8781606392:AAG6e0Jt5KMqouKEZZTfZ6wexhLG4xDBHZg")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5696943440")

# متغيرات الحالة
bot_running = True
virtual_wallet = 999.25
btc_holding = 0.0
in_position = False
buy_price = 0.0
highest_price = 0.0

# ==================== دوال تيليجرام والأزرار ====================
def send_telegram(message, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

# لوحة الأزرار التفاعلية تحت الرسالة
get_keyboard = {
    "inline_keyboard": [
        [
            {"text": "📊 حالة المحفظة", "callback_data": "status"},
            {"text": "🛑 إيقاف/تشغيل", "callback_data": "toggle_bot"}
        ]
    ]
}

# نظام الاستماع لأزرار تيليجرام فـ الخلفية (Polling)
def telegram_listener():
    global bot_running
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35).json()
            if "result" in response:
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    if "callback_query" in update:
                        query = update["callback_query"]
                        data = query["data"]
                        chat_id = query["message"]["chat"]["id"]
                        
                        if data == "status":
                            status_msg = (f"📊 *تقرير الحالة الآن:*\n"
                                          f"⚙️ *البوت:* {'🟢 شغال' if bot_running else '🔴 متوقف'}\n"
                                          f"🏦 *رصيد المحفظة:* ${virtual_wallet:.2f}\n"
                                          f"💼 *صفقة مفتوحة:* {'نعم' if in_position else 'لا'}")
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                          json={"chat_id": chat_id, "text": status_msg, "parse_mode": "Markdown"})
                        elif data == "toggle_bot":
                            bot_running = not bot_running
                            state_text = "🟢 تم تشغيل البوت!" if bot_running else "🔴 تم إيقاف البوت مؤقتاً!"
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                          json={"chat_id": chat_id, "text": state_text})
        except Exception as e:
            time.sleep(5)

# تشغيل المستمع فـ مسار مستقل (Thread)
threading.Thread(target=telegram_listener, daemon=True).start()

# إعدادات المنصة CCXT
exchange = ccxt.binance({'enableRateLimit': True, 'apiKey': BINANCE_API_KEY, 'secret': BINANCE_SECRET})

def fetch_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=205)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    ema_gain = gain.ewm(com=13, adjust=False).mean()
    ema_loss = loss.ewm(com=13, adjust=False).mean()
    rs = ema_gain / ema_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    return df

send_telegram("🚀 *TraderNux v4.0 شغال بالأزرار التفاعلية والربح المتحرك!*", reply_markup=get_keyboard)

# ==================== الحلقة الرئيسية للتداول ====================
while True:
    try:
        if not bot_running:
            time.sleep(10)
            continue
            
        df = fetch_data()
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        current_ema200 = df['ema200'].iloc[-1]
        
        is_uptrend = current_price > current_ema200
        is_oversold = current_rsi < 35
        
        # 1. الشراء (BUY)
        if not in_position and is_uptrend and is_oversold:
            buy_price = current_price
            highest_price = current_price
            
            if REAL_TRADING:
                order = exchange.create_market_buy_order(SYMBOL, POSITION_SIZE_USDT / current_price)
                btc_holding = order['filled']
                buy_price = order['price'] if order['price'] else current_price
            else:
                net_position = POSITION_SIZE_USDT * (1 - FEE_PCT)
                btc_holding = net_position / current_price
                virtual_wallet -= POSITION_SIZE_USDT
            
            in_position = True
            
            msg = (f"🟢 *إشارة شراء مؤكدة (BUY)*\n"
                   f"💵 *السعر:* ${buy_price:.2f}\n"
                   f"📈 *RSI:* {current_rsi:.1f} | *EMA200:* ${current_ema200:.2f}")
            print(msg)
            send_telegram(msg, reply_markup=get_keyboard)

        # 2. البيع وإدارة الصفقة (Trailing Take-Profit & Stop-Loss)
        elif in_position:
            if current_price > highest_price:
                highest_price = current_price
                
            # وقف الخسارة المتحرك وجني الأرباح الذكي
            stop_loss_price = buy_price * (1 - INITIAL_STOP_LOSS_PCT)
            trailing_take_profit = highest_price * (1 - TRAILING_GAP_PCT)
            
            reason = None
            if current_price <= stop_loss_price:
                reason = "🛡️ وقف خسارة (Stop Loss)"
            elif current_price < trailing_take_profit and highest_price > buy_price * 1.01:
                reason = "🎯 جني أرباح متحرك (Trailing Take Profit)"
                
            if reason:
                if REAL_TRADING:
                    order = exchange.create_market_sell_order(SYMBOL, btc_holding)
                    sell_price = order['price'] if order['price'] else current_price
                    returned_usdt = order['cost']
                else:
                    raw_return = btc_holding * current_price
                    returned_usdt = raw_return * (1 - FEE_PCT)
                    virtual_wallet += returned_usdt
                    sell_price = current_price

                pnl = returned_usdt - POSITION_SIZE_USDT
                
                msg = (f"🔴 *إشارة بيع ({reason})*\n"
                       f"💵 *سعر البيع:* ${sell_price:.2f}\n"
                       f"💰 *النتيجة:* {pnl:+.2f}$ USDT\n"
                       f"🏦 *الرصيد الكلي:* ${virtual_wallet:.2f}")
                print(msg)
                send_telegram(msg, reply_markup=get_keyboard)
                
                in_position = False
                btc_holding = 0.0

        print(f"Price: ${current_price:.2f} | RSI: {current_rsi:.1f} | Wallet: ${virtual_wallet:.2f}")
        time.sleep(20)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)