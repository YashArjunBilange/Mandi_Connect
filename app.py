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
# ENV CONFIG
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
# CACHE (15 min)
# ─────────────────────────────────────────────
cache = TTLCache(maxsize=200, ttl=60 * 15)

def dict_to_tuple(d):
    return tuple(sorted(d.items()))

# ─────────────────────────────────────────────
# CORE API CALL
# ─────────────────────────────────────────────
@cached(cache, key=lambda params: dict_to_tuple(params))
def fetch_from_api(params):
    if not API_BASE_URL:
        raise ValueError("API_BASE_URL is not configured.")

    query = params.copy()
    headers = {}

    # API key handling
    if API_KEY:
        if API_KEY_HEADER:
            headers[API_KEY_HEADER] = API_KEY
        else:
            query.setdefault(API_KEY_PARAM, API_KEY)

    query.setdefault("format", "json")
    query.setdefault("limit", API_DEFAULT_LIMIT)

    resp = requests.get(
        API_BASE_URL,
        params=query,
        headers=headers,
        timeout=20
    )
    resp.raise_for_status()
    return resp.json()

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
        "message": "✅ Farmer Market API is live.",
        "usage": "/prices?state=Maharashtra&commodity=Onion"
    })

@app.route("/health")
def health():
    return jsonify({
        "api_base_url": API_BASE_URL,
        "api_key_loaded": bool(API_KEY),
        "api_key_mode": "header" if API_KEY_HEADER else "query",
        "api_key_param": None if API_KEY_HEADER else API_KEY_PARAM,
        "resource_id": RESOURCE_ID,
        "default_limit": API_DEFAULT_LIMIT,
        "status": "ok"
    })

# ─────────────────────────────────────────────
# SCHEMA INSPECTION (VERY IMPORTANT FOR DEBUGGING)
# ─────────────────────────────────────────────
@app.route("/schema")
def schema():
    try:
        data = fetch_from_api({"limit": 1})
        records = data.get("records", [])

        if not records:
            return jsonify({"error": "No dataset records found."}), 404

        example = records[0]

        return jsonify({
            "resource_id": RESOURCE_ID,
            "field_count": len(example),
            "fields": list(example.keys()),
            "example_record": example,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# FILTER OPTIONS (SAFE EXTRACTION)
# ─────────────────────────────────────────────
@app.route("/options")
def options():
    try:
        data = fetch_from_api({"limit": 500})
        records = data.get("records", [])

        districts, markets, commodities = set(), set(), set()

        for r in records:
            if r.get("District"):
                districts.add(r.get("District"))
            if r.get("Market"):
                markets.add(r.get("Market"))
            if r.get("Commodity"):
                commodities.add(r.get("Commodity"))

        return jsonify({
            "districts": sorted(districts),
            "markets": sorted(markets),
            "commodities": sorted(commodities),
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "districts": [],
            "markets": [],
            "commodities": [],
        }), 500

# ─────────────────────────────────────────────
# PRICE API (FIXED FIELD MAPPING)
# ─────────────────────────────────────────────
@app.route("/prices")
def prices():
    params = {}

    # Filters (must match API field names exactly)
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

    try:
        data = fetch_from_api(params)
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

                # ⚠️ FIXED FIELD MAPPING (IMPORTANT)
                "arrival_date": r.get("Arrival Date"),
                "min_price": r.get("Min X0020 Price"),
                "max_price": r.get("Max X0020 Price"),
                "modal_price": r.get("Modal X0020 Price"),
            })

        if not normalized:
            return jsonify({
                "message": "No records found for these filters.",
                "records": []
            })

        return jsonify({"records": normalized})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
# RUN APP
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
