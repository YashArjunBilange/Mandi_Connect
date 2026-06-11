from flask import Flask, request, jsonify
from flask_cors import CORS
from cachetools import TTLCache, cached
from dotenv import load_dotenv
import requests
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

# =========================
# CONFIG
# =========================

API_KEY = os.getenv("API_KEY")

RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"

API_BASE_URL = (
    f"https://api.data.gov.in/resource/{RESOURCE_ID}"
)

DEFAULT_LIMIT = 100

# =========================
# CACHE
# =========================

cache = TTLCache(maxsize=200, ttl=900)


def make_cache_key(params):
    return tuple(sorted(params.items()))


@cached(cache, key=lambda params: make_cache_key(params))
def fetch_from_api(params):
    query = params.copy()

    query["api-key"] = API_KEY
    query["format"] = "json"

    if "limit" not in query:
        query["limit"] = DEFAULT_LIMIT

    response = requests.get(
        API_BASE_URL,
        params=query,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "🌾 Farmer Market API is live",
        "endpoints": [
            "/health",
            "/schema",
            "/options",
            "/prices"
        ]
    })


# =========================
# HEALTH
# =========================

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key_loaded": bool(API_KEY),
        "resource_id": RESOURCE_ID
    })


# =========================
# SCHEMA
# =========================

@app.route("/schema")
def schema():
    try:
        data = fetch_from_api({
            "limit": 1
        })

        return jsonify({
            "fields": data.get("field", []),
            "count": data.get("count"),
            "sample_record": (
                data.get("records", [{}])[0]
                if data.get("records")
                else {}
            )
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# =========================
# OPTIONS
# =========================

@app.route("/options")
def options():
    try:
        data = fetch_from_api({
            "limit": 1000
        })

        records = data.get("records", [])

        states = sorted({
            r.get("state")
            for r in records
            if r.get("state")
        })

        districts = sorted({
            r.get("district")
            for r in records
            if r.get("district")
        })

        markets = sorted({
            r.get("market")
            for r in records
            if r.get("market")
        })

        commodities = sorted({
            r.get("commodity")
            for r in records
            if r.get("commodity")
        })

        return jsonify({
            "states": states,
            "districts": districts,
            "markets": markets,
            "commodities": commodities
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# =========================
# PRICES
# =========================

@app.route("/prices")
def prices():
    try:
        params = {
            "limit": request.args.get("limit", 100)
        }

        state = request.args.get("state")
        district = request.args.get("district")
        market = request.args.get("market")
        commodity = request.args.get("commodity")
        variety = request.args.get("variety")
        grade = request.args.get("grade")

        if state:
            params["filters[state.keyword]"] = state

        if district:
            params["filters[district]"] = district

        if market:
            params["filters[market]"] = market

        if commodity:
            params["filters[commodity]"] = commodity

        if variety:
            params["filters[variety]"] = variety

        if grade:
            params["filters[grade]"] = grade

        data = fetch_from_api(params)

        records = data.get("records", [])

        result = []

        for r in records:
            result.append({
                "state": r.get("state"),
                "district": r.get("district"),
                "market": r.get("market"),
                "commodity": r.get("commodity"),
                "variety": r.get("variety"),
                "grade": r.get("grade"),
                "arrival_date": r.get("arrival_date"),
                "min_price": r.get("min_price"),
                "max_price": r.get("max_price"),
                "modal_price": r.get("modal_price")
            })

        return jsonify({
            "count": len(result),
            "records": result
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
