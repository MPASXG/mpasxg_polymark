from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
from datetime import datetime, timezone, timedelta
import json

app = Flask(__name__)
CORS(app)

GAMMA_BASE = "https://gamma-api.polymarket.com"

# Liste de mots-clés pour filtrer les marchés non désirés
EXCLUDED = {
    "sports", "sport", "Hyperliquid", "Game", "Solana", "BNB", "XRP,"nba", "nfl", "nhl", "mlb", "soccer", "football", 
    "basketball", "baseball", "hockey", "tennis", "golf", "mma", "ufc", 
    "f1", "nascar", "racing", "crypto", "bitcoin", "btc", "ethereum", 
    "eth", "defi", "nft", "weather", "climat", "meteo", "météo"
}

def is_excluded(m):
    text = (m.get("question", "") + " " + m.get("category", "") + " " + str(m.get("tags", []))).lower()
    return any(t in text for t in EXCLUDED)

def best_yield(m):
    try:
        prices = [float(p) for p in json.loads(m.get("outcomePrices", "[]"))]
    except:
        return None
    
    if len(prices) < 2:
        return None
        
    end = m.get("endDate") or m.get("end_date_iso")
    if not end:
        return None
        
    try:
        # Calcul du temps restant en jours
        days = (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() / 86400
    except:
        return None
        
    if days <= 0 or days > 7:
        return None

    def calculate_annualized_yield(p):
        # Formule : ((1 - prix) / prix) * (365 / jours_restants) * 100
        if 0 < p < 1:
            return ((1 - p) / p) * (365 / days) * 100
        return None

    yield_yes = calculate_annualized_yield(prices[0])
    yield_no = calculate_annualized_yield(prices[1])

    # On choisit le meilleur côté (YES ou NO)
    if yield_yes is not None and (yield_no is None or yield_yes >= yield_no):
        best = {"yield": yield_yes, "side": "YES", "price": prices[0]}
    else:
        best = {"yield": yield_no, "side": "NO", "price": prices[1]}

    # On ignore les rendements trop faibles (inférieurs à 12% par an)
    if not best["yield"] or best["yield"] < 12:
        return None
        
    return {**best, "days_left": days, "yes_price": prices[0], "no_price": prices[1]}

# --- PAGE D'ACCUEIL VISUELLE ---
@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Polymarket Yield Screener</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { background-color: #0f172a; color: #f8fafc; font-family: sans-serif; }
            .card { background: #1e293b; border: 1px solid #334155; }
        </style>
    </head>
    <body class="p-4 md:p-10">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-between items-center mb-8">
                <h1 class="text-2xl font-bold text-white">🚀 Polymarket <span class="text-blue-400">Yield Screener</span></h1>
                <div id="status" class="text-xs text-slate-500 italic">Mise à jour en direct...</div>
            </div>

            <div class="card rounded-xl overflow-hidden shadow-2xl">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-700/50 text-slate-300 text-sm uppercase">
                                <th class="p-4">Question</th>
                                <th class="p-4">Side</th>
                                <th class="p-4 text-right">Annual Yield</th>
                                <th class="p-4 text-right">Price</th>
                                <th class="p-4 text-right">Time Left</th>
                            </tr>
                        </thead>
                        <tbody id="table-body" class="divide-y divide-slate-700">
                            <tr><td colspan="5" class="p-10 text-center text-slate-500">Récupération des données...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script>
            async function loadData() {
                try {
                    const res = await fetch('/api/screener');
                    const data = await res.json();
                    const tbody = document.getElementById('table-body');
                    document.getElementById('status').innerText = 'Dernier fetch : ' + new Date(data.fetched_at).toLocaleTimeString();
                    
                    if (data.markets.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="p-10 text-center">Aucune opportunité trouvée.</td></tr>';
                        return;
                    }

                    tbody.innerHTML = data.markets.map(m => `
                        <tr class="hover:bg-slate-700/30 transition">
                            <td class="p-4 text-sm font-medium leading-tight max-w-xs md:max-w-md">${m.question}</td>
                            <td class="p-4">
                                <span class="px-2 py-1 rounded text-[10px] font-bold ${m.best_side === 'YES' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'}">
                                    ${m.best_side}
                                </span>
                            </td>
                            <td class="p-4 text-right font-bold text-green-400">
                                ${m.best_yield > 1000 ? '> 1000' : Math.round(m.best_yield)}%
                            </td>
                            <td class="p-4 text-right text-slate-400 text-sm font-mono">
                                ${m.best_side === 'YES' ? m.yes_price : m.no_price}$
                            </td>
                            <td class="p-4 text-right text-orange-300 text-sm font-mono">
                                ${m.days_left.toFixed(1)} jours
                            </td>
                        </tr>
                    `).join('');
                } catch (e) {
                    document.getElementById('table-body').innerHTML = '<tr><td colspan="5" class="p-10 text-center text-red-400">Erreur de chargement.</td></tr>';
                }
            }
            loadData();
            setInterval(loadData, 60000); // Refresh toutes les minutes
        </script>
    </body>
    </html>
    """)

# --- API ENDPOINT ---
@app.route("/api/screener")
def screener():
    now = datetime.now(timezone.utc)
    params = {
        "active": "true",
        "closed": "false",
        "limit": 200,
        "order": "endDate",
        "ascending": "true",
        "end_date_min": now.isoformat(),
        "end_date_max": (now + timedelta(days=7)).isoformat()
    }
    
    try:
        markets = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=10).json()
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    
    results = []
    for m in markets:
        if is_excluded(m):
            continue
        
        b = best_yield(m)
        if not b:
            continue
            
        results.append({
            "question": m.get("question", ""),
            "slug": m.get("slug", m.get("conditionId", "")),
            "category": m.get("category", "Divers"),
            "volume": float(m.get("volume", 0) or 0),
            "best_yield": b["yield"],
            "best_side": b["side"],
            "yes_price": b["yes_price"],
            "no_price": b["no_price"],
            "days_left": b["days_left"]
        })
    
    results.sort(key=lambda x: x["best_yield"], reverse=True)
    return jsonify({
        "markets": results, 
        "count": len(results), 
        "fetched_at": now.isoformat()
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    # Railway utilise le Procfile, mais cette ligne permet de tester en local
    app.run(host="0.0.0.0", port=8080)
