import os
import time
import requests
import ccxt
import pandas as pd

# ==================== الإعدادات ====================
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1m'
INITIAL_BALANCE = 20.0  # رأس المال المخصص: 20 دولار
POSITION_SIZE = 10.0    # مبلغ كل صفقة: 10 دولار
TAKE_PROFIT_PCT = 0.015 # target ربح: 1.5%
STOP_LOSS_PCT = 0.008   # وقف خسارة متحرك: 0.8%

# معلومات Telegram المحدثة الخاصة بك
TELEGRAM_TOKEN = "8781606392:AAG6e0Jt5KMqouKEZZTfZ6wexhLG4xDBHZg"
TELEGRAM_CHAT_ID = "5696943440"

# ==================== الدوار والوظائف ====================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"خطأ فـ التليجرام: {e}")

exchange = ccxt.binance({'enableRateLimit': True})

def fetch_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=205)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # حساب RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # حساب EMA 200 للترند العام
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    return df

# متغيرات المحفظة والحالة
wallet_usdt = INITIAL_BALANCE
btc_holding = 0.0
in_position = False
buy_price = 0.0
highest_price = 0.0

send_telegram(f"🚀 *TraderNux v2.0 شغال بنجاح!*\n💰 *رأس المال:* ${INITIAL_BALANCE}\n📊 *الاستراتيجية:* RSI + EMA 200 + Trailing SL")

while True:
    try:
        df = fetch_data()
        current_price = df['close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        current_ema200 = df['ema200'].iloc[-1]
        
        # شرط الشراء المؤكد: ترند صاعد + ذروة البيع
        is_uptrend = current_price > current_ema200
        is_oversold = current_rsi < 35
        
        # 1. الشراء (BUY)
        if not in_position and is_uptrend and is_oversold:
            if wallet_usdt >= POSITION_SIZE:
                btc_holding = POSITION_SIZE / current_price
                wallet_usdt -= POSITION_SIZE
                buy_price = current_price
                highest_price = current_price
                in_position = True
                
                msg = (f"🟢 *إشارة شراء مؤكدة (BUY)*\n"
                       f"💵 *السعر:* ${current_price:.2f}\n"
                       f"📈 *RSI:* {current_rsi:.1f} | *EMA200:* ${current_ema200:.2f}\n"
                       f"💼 *المبلغ:* ${POSITION_SIZE}")
                print(msg)
                send_telegram(msg)
                
        # 2. إدارة الصفقة والمبيعات (SELL / SL / TP)
        elif in_position:
            # تحديث أعلى سعر وصل ليه السوق فـ الصفقة
            if current_price > highest_price:
                highest_price = current_price
            
            # Trailing Stop-Loss dynamic
            trailing_sl = highest_price * (1 - STOP_LOSS_PCT)
            take_profit = buy_price * (1 + TAKE_PROFIT_PCT)
            
            reason = None
            if current_price >= take_profit:
                reason = "🎯 أرباح (Take Profit)"
            elif current_price <= trailing_sl:
                reason = "🛡️ وقف خسارة متحرك (Trailing Stop Loss)"
                
            if reason:
                return_usdt = btc_holding * current_price
                wallet_usdt += return_usdt
                profit_loss = return_usdt - POSITION_SIZE
                
                msg = (f"🔴 *إشارة بيع ({reason})*\n"
                       f"💵 *سعر البيع:* ${current_price:.2f}\n"
                       f"💰 *النتيجة:* {profit_loss:+.2f}$ USDT\n"
                       f"🏦 *الرصيد الكلي:* ${wallet_usdt:.2f}")
                print(msg)
                send_telegram(msg)
                
                in_position = False
                btc_holding = 0.0

        print(f"Price: ${current_price:.2f} | RSI: {current_rsi:.1f} | EMA200: ${current_ema200:.2f} | Wallet: ${wallet_usdt:.2f}")
        time.sleep(30)
        
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)