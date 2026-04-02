from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timezone, timedelta
import json

app = Flask(__name__)
CORS(app)

GAMMA_BASE = "https://gamma-api.polymarket.com"

EXCLUDED = {"sports","sport","nba","nfl","nhl","mlb","soccer","football","basketball","baseball","hockey","tennis","golf","mma","ufc","f1","nascar","racing","crypto","bitcoin","btc","ethereum","eth","defi","nft","weather","climat","meteo","météo"}

def is_excluded(m):
    text = (m.get("question","") + " " + m.get("category","") + " " + str(m.get("tags",[]))).lower()
    return any(t in text for t in EXCLUDED)

def best_yield(m):
    try:
        prices = [float(p) for p in json.loads(m.get("outcomePrices","[]"))]
    except:
        return None
    if len(prices) < 2: return None
    end = m.get("endDate") or m.get("end_date_iso")
    if not end: return None
    try:
        days = (datetime.fromisoformat(end.replace("Z","+00:00")) - datetime.now(timezone.utc)).total_seconds() / 86400
    except:
        return None
    if days <= 0 or days > 7: return None
    def ay(p): return ((1-p)/p)*(365/days)*100 if 0 < p < 1 else None
    yy, yn = ay(prices[0]), ay(prices[1])
    best = {"yield":yy,"side":"YES","price":prices[0]} if yy is not None and (yn is None or yy>=yn) else {"yield":yn,"side":"NO","price":prices[1]}
    if not best["yield"] or best["yield"] < 12: return None
    return {**best, "days_left":days, "yes_price":prices[0], "no_price":prices[1]}

@app.route("/api/screener")
def screener():
    now = datetime.now(timezone.utc)
    params = {"active":"true","closed":"false","limit":200,"order":"endDate","ascending":"true","end_date_min":now.isoformat(),"end_date_max":(now+timedelta(days=7)).isoformat()}
    try:
        markets = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=10).json()
    except Exception as e:
        return jsonify({"error":str(e)}), 502
    results = []
    for m in markets:
        if is_excluded(m): continue
        b = best_yield(m)
        if not b: continue
        results.append({"question":m.get("question",""),"slug":m.get("slug",m.get("conditionId","")),"category":m.get("category","Divers"),"volume":float(m.get("volume",0) or 0),"best_yield":round(b["yield"],2),"best_side":b["side"],"yes_price":round(b["yes_price"],4),"no_price":round(b["no_price"],4),"days_left":round(b["days_left"],3)})
    results.sort(key=lambda x: x["best_yield"], reverse=True)
    return jsonify({"markets":results,"count":len(results),"fetched_at":now.isoformat()})

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```
