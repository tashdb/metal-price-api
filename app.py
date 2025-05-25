from flask import Flask, jsonify
from stockdex import Ticker
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import os

load_dotenv()

app = Flask(__name__)
cached_data = {}
last_updated = None

ALPHA_API_KEY = os.getenv("ALPHA_API_KEY")

def get_from_stockdex(ticker_symbol):
    try:
        ticker = Ticker(ticker=ticker_symbol)
        data = ticker.yahoo_api_price(range='7d', dataGranularity='1d')
        if not data or len(data) < 2:
            return None
        current_price = data[-1]['close']
        last_week_price = data[0]['close']
        change_pct = ((current_price - last_week_price) / last_week_price) * 100
        return {
            "price": round(current_price, 2),
            "change_pct": round(change_pct, 2),
            "is_up": change_pct >= 0,
            "source": "yahoo"
        }
    except Exception:
        return None

def get_from_alpha_vantage(symbol):
    try:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={ALPHA_API_KEY}"
        res = requests.get(url).json()
        series = res.get("Time Series (Daily)", {})
        if len(series) < 2:
            return None
        dates = sorted(series.keys(), reverse=True)
        current_price = float(series[dates[0]]["4. close"])
        last_week_price = float(series[dates[-1]]["4. close"])
        change_pct = ((current_price - last_week_price) / last_week_price) * 100
        return {
            "price": round(current_price, 2),
            "change_pct": round(change_pct, 2),
            "is_up": change_pct >= 0,
            "source": "alpha_vantage"
        }
    except Exception:
        return None

TICKER_MAP = {
    "gold": ("GC=F", "XAUUSD"),
    "silver": ("SI=F", "XAGUSD"),
    "platinum": ("PL=F", "XPTUSD")
}

def update_prices():
    global cached_data, last_updated
    updated = {}
    for metal, (yahoo, alpha) in TICKER_MAP.items():
        data = get_from_stockdex(yahoo)
        if not data:
            data = get_from_alpha_vantage(alpha)
        updated[metal] = data or {"price": None, "change_pct": None, "is_up": None, "source": "none"}
    cached_data = updated
    last_updated = datetime.utcnow()

@app.route("/api/metals")
def metals():
    global last_updated
    if not last_updated or datetime.utcnow() - last_updated > timedelta(minutes=15):
        update_prices()
    return jsonify(cached_data)

scheduler = BackgroundScheduler()
scheduler.add_job(update_prices, 'interval', minutes=15)
scheduler.start()
update_prices()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
