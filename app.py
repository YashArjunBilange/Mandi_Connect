from flask import Flask, request, jsonify, render_template
from cachetools import TTLCache, cached
import requests
from flask_cors import CORS
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
API_KEY = os.environ.get("API_KEY")
API_KEY_PARAM = os.environ.get("API_KEY_PARAM", "api-key")
API_KEY_HEADER = os.environ.get("API_KEY_HEADER")

RESOURCE_ID = os.environ.get(
    "API_RESOURCE_ID",
    "9ef84268-d588-465a-a308-a864a43d0070"
)

API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    f"https://api.data.gov.in/resource/{RESOURCE_ID}"
)

API_DEFAULT_LIMIT = os.environ.get("API_DEFAULT_LIMIT", "5000")

# ─────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────
cache = TTLCache(maxsize=200, ttl=60 * 15)

def cache_key(params):
    return tuple(sorted(params.items())) if isinstance(params, dict) else str(params)

# ─────────────────────────────────────────────
# SAFE API FETCH (NO MORE 500 CRASHES)
# ─────────────────────────────────────────────
@cached(cache, key=cache_key)
def fetch_from_api(params):
    if not API_BASE_URL:
        return {"error": "API_BASE_URL not configured"}

    query = params.copy() if params else {}
    headers = {}

    # API key handling
    if API_KEY:
        if API_KEY_HEADER:
            headers[API_KEY_HEADER] = API_KEY
        else:
            query.setdefault(API_KEY_PARAM, API_KEY)

    query.setdefault("format", "json")
    query.setdefault("limit", API_DEFAULT_LIMIT)

    try:
        resp = requests.get(
            API_BASE_URL,
            params=query,
            headers=headers,
            timeout=20
        )

        # ❗ prevent silent crashes
        if resp.status_code != 200:
            return {
                "error": "API request failed",
                "status_code": resp.status_code,
                "response": resp.text[:300]
            }

        try:
            return resp.json()
        except Exception:
            return {
                "error": "Invalid JSON from API",
                "response": resp.text[:300]
            }

    except requests.exceptions.Timeout:
        return {"error": "API timeout"}

    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────
# FRONTEND ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html", page_name="home")

@app.route("/get-prices")
def get_prices():
    return render_template("get_prices.html", page_name="get-prices")

@app.route("/historical-trends")
def trends():
    return render_template("trends.html", page_name="trends")

@app.route("/notifications")
def notifications():
    return render_template("notifications.html", page_name="notifications")

# ─────────────────────────────────────────────
# API STATUS
# ─────────────────────────────────────────────
@app.route("/api")
def api_info():
    return jsonify({
        "message": "✅ Farmer Market API is live",
        "usage": "/prices?state=Maharashtra&commodity=Onion"
    })

@app.route("/health")
def health():
    return jsonify({
        "api_base_url": API_BASE_URL,
        "api_key_loaded": bool(API_KEY),
        "api_key_mode": "header" if API_KEY_HEADER else "query",
        "resource_id": RESOURCE_ID,
        "status": "ok"
    })

# ─────────────────────────────────────────────
# SCHEMA DEBUG (VERY IMPORTANT)
# ─────────────────────────────────────────────
@app.route("/schema")
def schema():
    data = fetch_from_api({"limit": 1})

    if isinstance(data, dict) and data.get("error"):
        return jsonify(data), 500

    records = data.get("records", [])
    if not records:
        return jsonify({"error": "No records found"}), 404

    return jsonify({
        "fields": list(records[0].keys()),
        "example": records[0]
    })

# ─────────────────────────────────────────────
# OPTIONS (SAFE EXTRACTION)
# ─────────────────────────────────────────────
@app.route("/options")
def options():
    data = fetch_from_api({"limit": 500})

    if isinstance(data, dict) and data.get("error"):
        return jsonify(data), 500

    records = data.get("records", [])

    districts, markets, commodities = set(), set(), set()

    for r in records:
        districts.add(r.get("District"))
        markets.add(r.get("Market"))
        commodities.add(r.get("Commodity"))

    return jsonify({
        "districts": sorted(d for d in districts if d),
        "markets": sorted(m for m in markets if m),
        "commodities": sorted(c for c in commodities if c),
    })

# ─────────────────────────────────────────────
# PRICE API (FIXED + ROBUST MAPPING)
# ─────────────────────────────────────────────
@app.route("/prices")
def prices():
    params = {}

    if request.args.get("state"):
        params["filters[State]"] = request.args.get("state")

    if request.args.get("commodity"):
        params["filters[Commodity]"] = request.args.get("commodity")

    if request.args.get("district"):
        params["filters[District]"] = request.args.get("district")

    if request.args.get("market"):
        params["filters[Market]"] = request.args.get("market")

    if request.args.get("arrival_date"):
        params["filters[Arrival Date]"] = request.args.get("arrival_date")

    data = fetch_from_api(params)

    if isinstance(data, dict) and data.get("error"):
        return jsonify(data), 500

    records = data.get("records", [])

    normalized = []

    for r in records:
        normalized.append({
            "state": r.get("State"),
            "district": r.get("District"),
            "market": r.get("Market"),
            "commodity": r.get("Commodity"),
            "variety": r.get("Variety"),
            "grade": r.get("Grade"),

            # 🔥 FIXED FIELD NAMES (CRITICAL)
            "arrival_date": r.get("Arrival Date"),
            "min_price": r.get("Min X0020 Price"),
            "max_price": r.get("Max X0020 Price"),
            "modal_price": r.get("Modal X0020 Price"),
        })

    return jsonify({
        "count": len(normalized),
        "records": normalized
    })

# ─────────────────────────────────────────────
# RUN APP
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
