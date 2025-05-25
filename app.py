from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import yfinance as yf

app = Flask(__name__)
cached_data = {}
last_updated = None

# Yahoo Finance tickers
TICKERS = {
    "gold": "GC=F",
    "silver": "SI=F",
    "platinum": "PL=F",
    "palladium": "PA=F"
}

# FX ticker for USD to GBP
FX_TICKER = "GBPUSD=X"

def get_usd_to_gbp_rate():
    try:
        fx_data = yf.Ticker(FX_TICKER).history(period="1d")
        rate = fx_data["Close"].iloc[-1]
        return 1 / rate  # Convert USD → GBP
    except Exception as e:
        print("FX rate error:", e)
        return 0.79  # fallback conversion rate

def get_yfinance_data(ticker):
    try:
        data = yf.Ticker(ticker).history(period="7d")
        if len(data) < 2:
            return None
        current_price = data["Close"].iloc[-1]
        last_week_price = data["Close"].iloc[0]
        change_pct = ((current_price - last_week_price) / last_week_price) * 100
        return current_price, change_pct
    except Exception as e:
        print(f"Error fetching {ticker}:", e)
        return None

def update_prices():
    global cached_data, last_updated
    fx_rate = get_usd_to_gbp_rate()
    updated = {}

    for metal, ticker in TICKERS.items():
        result = get_yfinance_data(ticker)
        if result:
            price_usd, change_pct = result
            price_gbp = round(price_usd * fx_rate, 2)
            updated[metal] = {
                "price": price_gbp,
                "change_pct": round(change_pct, 2),
                "is_up": bool(change_pct >= 0)  # FIXED: native Python bool
            }
        else:
            updated[metal] = {
                "price": None,
                "change_pct": None,
                "is_up": None
            }

    cached_data = updated
    last_updated = datetime.utcnow()

@app.route("/api/metals")
def metals():
    global last_updated
    if not last_updated or datetime.utcnow() - last_updated > timedelta(minutes=5):
        update_prices()
    return jsonify(cached_data)

@app.route("/")
def index():
    return "✅ Metal Price API (GBP) with yfinance — /api/metals"

# Background scheduler: refresh every 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(update_prices, 'interval', minutes=5)
scheduler.start()
update_prices()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
