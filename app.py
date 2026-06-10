from flask import Flask, request, jsonify
from cachetools import TTLCache, cached
import requests
from flask_cors import CORS
import os

PORT = int(os.environ.get("PORT", 8000))
app = Flask(__name__)
CORS(app)

DATA_GOV_KEY = os.environ.get("DATA_GOV_API_KEY")
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"  # replace with actual resource id
BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

cache = TTLCache(maxsize=200, ttl=60*15)  # 15 minutes

@cached(cache)
def fetch_from_datagov(params):
    params.update({"api-key": DATA_GOV_KEY or "DEMO_KEY", "format": "json", "limit": 5000})
    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()

@app.route("/prices")
def prices():
    state = request.args.get("state", "Maharashtra")
    params = {"filters[state]": state}
    if request.args.get("commodity"):
        params["filters[commodity]"] = request.args.get("commodity")
    if request.args.get("market"):
        params["filters[market]"] = request.args.get("market")
    try:
        data = fetch_from_datagov(params)
        records = data.get("records", [])
        normalized = []
        for r in records:
            normalized.append({
                "state": r.get("State") or r.get("state"),
                "district": r.get("District") or r.get("district"),
                "market": r.get("Market") or r.get("market"),
                "commodity": r.get("Commodity") or r.get("commodity"),
                "variety": r.get("Variety") or r.get("variety"),
                "arrival_date": r.get("Arrival_Date") or r.get("arrival_date"),
                "min_price": r.get("Min_x0020_Price") or r.get("Min Price") or r.get("min_price"),
                "max_price": r.get("Max_x0020_Price") or r.get("max_price"),
                "modal_price": r.get("Modal_Price") or r.get("modal_price"),
            })
        return jsonify({"records": normalized})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
