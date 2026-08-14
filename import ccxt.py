import ccxt
import pandas as pd
import time

# 1. الاتصال بمنصة Binance (بيانات عامة وبدون حاجة لحساب حالياً)
exchange = ccxt.binance({
    'enableRateLimit': True,
})

symbol = 'BTC/USDT'  # زوج التداول (بيتكوين مقابل الدولار الرقمي)
timeframe = '1h'     # إطار زمني: شارت الساعة

def fetch_data():
    # جلب آخر 100 شمعة من السوق
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_signals(df):
    # حساب المتوسطات المتحركة (SMA)
    df['SMA_10'] = df['close'].rolling(window=10).mean()
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    
    # التقاط آخر قيمتين للتحقق من تقاطع الخطوط
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    # شرط الشراء (Golden Cross)
    if prev_row['SMA_10'] <= prev_row['SMA_50'] and last_row['SMA_10'] > last_row['SMA_50']:
        return "BUY (شراء)"
    # شرط البيع (Death Cross)
    elif prev_row['SMA_10'] >= prev_row['SMA_50'] and last_row['SMA_10'] < last_row['SMA_50']:
        return "SELL (بيع)"
    
    return "HOLD (انتظار)"

# 3. التشغيل المستمر للبوت
print("--------------------------------------------------")
print("🚀 البوت خدام دابا وكيراقب سوق البيتكوين لايف...")
print("--------------------------------------------------")

while True:
    try:
        data = fetch_data()
        signal = calculate_signals(data)
        current_price = data.iloc[-1]['close']
        
        print(f"💰 الثمن الحالي لـ {symbol}: ${current_price} | 📊 الإشارة: {signal}")
        
        # يتسنى 60 ثانية ويرجع يتحقق من جديد
        time.sleep(60) 
    except Exception as e:
        print(f"⚠️ حدث خطأ فـ الاتصال: {e}")
        time.sleep(10)