from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
from datetime import datetime, timezone, timedelta
import json

app = Flask(__name__)
CORS(app)

GAMMA_BASE = "https://gamma-api.polymarket.com"

EXCLUDED = {
    "sports", "sport", "nba", "nfl", "nhl", "mlb", "soccer", "football",
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
        days = (datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() / 86400
    except:
        return None

    # On accepte les marchés qui finissent entre 0.1 jour et 10 jours
    if days < 0.1 or days > 10:
        return None

    def ay(p):
        # Formule de rendement annualisé (Intérêts composés)
        if 0.01 < p < 0.99: # On évite les prix extrêmes 0 ou 1
            return ((1 + (1 - p) / p) ** (365 / days) - 1) * 100
        return None

    candidates = []
    # On analyse les deux côtés sans restriction de prix à 0.90
    y_yes = ay(prices[0])
    if y_yes: candidates.append({"yield": y_yes, "side": "YES", "price": prices[0]})
    
    y_no = ay(prices[1])
    if y_no: candidates.append({"yield": y_no, "side": "NO", "price": prices[1]})

    if not candidates:
        return None
        
    best = max(candidates, key=lambda x: x["yield"])
    
    # Seuil de rendement plus réaliste : 15% minimum au lieu de 1200%
    if best["yield"] < 15: 
        return None
        
    return {**best, "days_left": days, "yes_price": prices[0], "no_price": prices[1]}

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
            <div class="grid grid-cols-3 gap-4 mb-6">
                <div class="card rounded-lg p-4">
                    <p class="text-slate-400 text-xs uppercase tracking-wider mb-1">Marchés éligibles</p>
                    <p id="stat-count" class="text-2xl font-bold text-white">—</p>
                </div>
                <div class="card rounded-lg p-4">
                    <p class="text-slate-400 text-xs uppercase tracking-wider mb-1">Meilleur yield</p>
                    <p id="stat-best" class="text-2xl font-bold text-green-400">—</p>
                </div>
                <div class="card rounded-lg p-4">
                    <p class="text-slate-400 text-xs uppercase tracking-wider mb-1">Yield moyen</p>
                    <p id="stat-avg" class="text-2xl font-bold text-blue-400">—</p>
                </div>
            </div>
            <div class="card rounded-xl overflow-hidden shadow-2xl">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-700/50 text-slate-300 text-sm uppercase">
                                <th class="p-4">Question</th>
                                <th class="p-4">Côté</th>
                                <th class="p-4 text-right">Yield ann.</th>
                                <th class="p-4 text-right">Prix</th>
                                <th class="p-4 text-right">Temps</th>
                                <th class="p-4 text-right">Volume</th>
                            </tr>
                        </thead>
                        <tbody id="table-body" class="divide-y divide-slate-700">
                            <tr><td colspan="6" class="p-10 text-center text-slate-500">Récupération des données...</td></tr>
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
                    document.getElementById('status').innerText = 'Mis à jour : ' + new Date(data.fetched_at).toLocaleTimeString('fr-FR');
                    document.getElementById('stat-count').innerText = data.count;
                    if (data.markets.length) {
                        const yields = data.markets.map(m => m.best_yield);
                        document.getElementById('stat-best').innerText = Math.min(Math.max(...yields), 9999).toFixed(0) + '%';
                        document.getElementById('stat-avg').innerText = Math.min(yields.reduce((a,b)=>a+b,0)/yields.length, 9999).toFixed(0) + '%';
                    }
                    const tbody = document.getElementById('table-body');
                    if (!data.markets.length) {
                        tbody.innerHTML = '<tr><td colspan="6" class="p-10 text-center text-slate-500">Aucune opportunité trouvée.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.markets.map(m => {
                        const vol = m.volume >= 1e6 ? '$'+(m.volume/1e6).toFixed(1)+'M' : m.volume >= 1e3 ? '$'+Math.round(m.volume/1e3)+'K' : '$'+Math.round(m.volume);
                        const link = 'https://polymarket.com/market/' + m.slug;
                        const sideClass = m.best_side === 'YES' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-purple-500/20 text-purple-400 border border-purple-500/30';
                        return `<tr class="hover:bg-slate-700/30 transition cursor-pointer" onclick="window.open('${link}','_blank')">
                            <td class="p-4 text-sm font-medium leading-tight max-w-xs">
                                <div>${m.question}</div>
                                <div class="text-xs text-slate-500 mt-1">${m.category}</div>
                            </td>
                            <td class="p-4"><span class="px-2 py-1 rounded text-[10px] font-bold ${sideClass}">${m.best_side}</span></td>
                            <td class="p-4 text-right font-bold text-green-400">${m.best_yield > 999 ? '>999' : Math.round(m.best_yield)}%</td>
                            <td class="p-4 text-right text-slate-400 font-mono text-sm">${m.best_side === 'YES' ? m.yes_price : m.no_price}</td>
                            <td class="p-4 text-right text-orange-300 font-mono text-sm">${m.days_left.toFixed(1)}j</td>
                            <td class="p-4 text-right text-slate-400 text-sm">${vol}</td>
                        </tr>`;
                    }).join('');
                } catch(e) {
                    document.getElementById('table-body').innerHTML = '<tr><td colspan="6" class="p-10 text-center text-red-400">Erreur de chargement.</td></tr>';
                }
            }
            loadData();
            setInterval(loadData, 60000);
        </script>
    </body>
    </html>
    """)

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
            "best_yield": round(b["yield"], 1),
            "best_side": b["side"],
            "yes_price": round(b["yes_price"], 4),
            "no_price": round(b["no_price"], 4),
            "days_left": round(b["days_left"], 2),
        })

    results.sort(key=lambda x: x["best_yield"], reverse=True)
    return jsonify({"markets": results, "count": len(results), "fetched_at": now.isoformat()})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
