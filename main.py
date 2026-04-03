from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
from datetime import datetime, timezone, timedelta
import json

app = Flask(__name__)
CORS(app)

GAMMA_BASE = "https://gamma-api.polymarket.com"

# Catégories autorisées (champ "category" des events Polymarket)
ALLOWED_CATEGORIES = {
    "politics", "elections", "economy", "economics", "culture",
    "pop culture", "entertainment", "business", "finance", "geopolitics",
    "science", "law", "health", "media", "society", "government",
    "policy", "trade", "tariff", "world", "climate", "education",
    "technology", "ai", "space", "immigration", "crime", "justice",
}

def is_allowed(m):
    category = (m.get("category") or "").lower().strip()
    # On accepte si la catégorie contient un des mots autorisés
    return any(cat in category for cat in ALLOWED_CATEGORIES)

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
    if days < 1 or days > 7:
        return None
    def ay(p):
        return ((1 - p) / p) * (365 / days) * 100 if 0 < p < 1 else None
    yy, yn = ay(prices[0]), ay(prices[1])
    if yy is None and yn is None:
        return None
    if yy is not None and (yn is None or yy >= yn):
        best = {"yield": yy, "side": "YES", "price": prices[0]}
    else:
        best = {"yield": yn, "side": "NO", "price": prices[1]}
    if best["yield"] < 12:
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
                <div>
                    <h1 class="text-2xl font-bold text-white">🚀 Polymarket <span class="text-blue-400">Yield Screener</span></h1>
                    <p class="text-slate-500 text-xs mt-1">Politique · Élections · Économie · Culture · 1–7 jours · Yield annualisé &gt; 12%</p>
                </div>
                <div id="status" class="text-xs text-slate-500 italic">Chargement...</div>
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
                            <tr class="bg-slate-700/50 text-slate-300 text-xs uppercase tracking-wider">
                                <th class="p-4">Marché</th>
                                <th class="p-4">Côté</th>
                                <th class="p-4 text-right cursor-pointer hover:text-white" onclick="sortBy('yield')">Yield ann. ↕</th>
                                <th class="p-4 text-right">Yes / No</th>
                                <th class="p-4 text-right cursor-pointer hover:text-white" onclick="sortBy('days')">Temps ↕</th>
                                <th class="p-4 text-right cursor-pointer hover:text-white" onclick="sortBy('vol')">Volume ↕</th>
                            </tr>
                        </thead>
                        <tbody id="table-body" class="divide-y divide-slate-700">
                            <tr><td colspan="6" class="p-10 text-center text-slate-500">Récupération des données...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <div id="debug" class="text-xs text-slate-600 mt-3"></div>
        </div>
        <script>
            let allMarkets = [];
            let sortKey = 'yield';
            let sortAsc = false;

            function sortBy(key) {
                if (sortKey === key) sortAsc = !sortAsc;
                else { sortKey = key; sortAsc = false; }
                renderTable();
            }

            function renderTable() {
                const sorted = [...allMarkets].sort((a, b) => {
                    let va = sortKey === 'yield' ? a.best_yield : sortKey === 'days' ? a.days_left : a.volume;
                    let vb = sortKey === 'yield' ? b.best_yield : sortKey === 'days' ? b.days_left : b.volume;
                    return sortAsc ? va - vb : vb - va;
                });
                if (!sorted.length) {
                    document.getElementById('table-body').innerHTML = '<tr><td colspan="6" class="p-10 text-center text-slate-500">Aucune opportunité trouvée.</td></tr>';
                    return;
                }
                document.getElementById('table-body').innerHTML = sorted.map(m => {
                    const yPct = Math.round(m.yes_price * 100);
                    const nPct = 100 - yPct;
                    const yieldDisplay = m.best_yield > 999 ? '>999%' : Math.round(m.best_yield) + '%';
                    const yieldColor = m.best_yield > 100 ? 'text-green-400' : 'text-yellow-400';
                    const sideClass = m.best_side === 'YES'
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'bg-purple-500/20 text-purple-400 border border-purple-500/30';
                    const vol = m.volume >= 1e6 ? '$' + (m.volume/1e6).toFixed(1) + 'M'
                              : m.volume >= 1e3 ? '$' + Math.round(m.volume/1e3) + 'K'
                              : '$' + Math.round(m.volume);
                    const link = 'https://polymarket.com/market/' + m.slug;
                    return `<tr class="hover:bg-slate-700/30 transition cursor-pointer" onclick="window.open('${link}','_blank')">
                        <td class="p-4 text-sm font-medium leading-tight max-w-xs">
                            <div>${m.question}</div>
                            <div class="text-xs text-slate-500 mt-1">${m.category}</div>
                        </td>
                        <td class="p-4"><span class="px-2 py-1 rounded text-[10px] font-bold ${sideClass}">${m.best_side}</span></td>
                        <td class="p-4 text-right font-bold ${yieldColor}">${yieldDisplay}</td>
                        <td class="p-4 text-right text-sm">
                            <span class="text-blue-400 font-mono">${yPct}%</span>
                            <span class="text-slate-600 mx-1">/</span>
                            <span class="text-red-400 font-mono">${nPct}%</span>
                        </td>
                        <td class="p-4 text-right text-orange-300 font-mono text-sm">${m.days_left.toFixed(1)}j</td>
                        <td class="p-4 text-right text-slate-400 text-sm">${vol}</td>
                    </tr>`;
                }).join('');
            }

            async function loadData() {
                try {
                    const res = await fetch('/api/screener');
                    const data = await res.json();
                    allMarkets = data.markets;
                    document.getElementById('status').innerText = 'Mis à jour : ' + new Date(data.fetched_at).toLocaleTimeString('fr-FR');
                    document.getElementById('stat-count').innerText = data.count;
                    document.getElementById('debug').innerText = data.debug || '';
                    if (data.markets.length) {
                        const yields = data.markets.map(m => m.best_yield);
                        document.getElementById('stat-best').innerText = Math.min(Math.max(...yields), 9999).toFixed(0) + '%';
                        document.getElementById('stat-avg').innerText = Math.min(yields.reduce((a,b)=>a+b,0)/yields.length, 9999).toFixed(0) + '%';
                    }
                    renderTable();
                } catch(e) {
                    document.getElementById('table-body').innerHTML = '<tr><td colspan="6" class="p-10 text-center text-red-400">Erreur : ' + e.message + '</td></tr>';
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
    all_markets = []
    seen = set()

    # On pagine pour récupérer suffisamment de marchés
    for offset in range(0, 400, 100):
        params = {
            "active": "true", "closed": "false", "limit": 100,
            "order": "endDate", "ascending": "true",
            "end_date_min": (now + timedelta(days=1)).isoformat(),
            "end_date_max": (now + timedelta(days=7)).isoformat(),
            "offset": offset,
        }
        try:
            batch = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=10).json()
            if not batch:
                break
            all_markets.extend(batch)
        except Exception as e:
            break

    # Collecter les catégories uniques pour debug
    categories_seen = set()
    results = []

    for m in all_markets:
        mid = m.get("id") or m.get("conditionId")
        if mid in seen:
            continue
        seen.add(mid)

        cat = (m.get("category") or "").strip()
        categories_seen.add(cat)

        if not is_allowed(m):
            continue

        b = best_yield(m)
        if not b:
            continue

        results.append({
            "question": m.get("question", ""),
            "slug": m.get("slug", m.get("conditionId", "")),
            "category": cat,
            "volume": float(m.get("volume", 0) or 0),
            "best_yield": round(b["yield"], 1),
            "best_side": b["side"],
            "yes_price": round(b["yes_price"], 4),
            "no_price": round(b["no_price"], 4),
            "days_left": round(b["days_left"], 2),
        })

    results.sort(key=lambda x: x["best_yield"], reverse=True)
    return jsonify({
        "markets": results,
        "count": len(results),
        "fetched_at": now.isoformat(),
        "debug": "Catégories vues : " + ", ".join(sorted(categories_seen)[:30]),
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
