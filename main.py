from flask import Flask, jsonify, render_template_string
import requests
from datetime import datetime, timezone
import json
import time

app = Flask(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Yield Power-Scan 5k</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .yield-low { color: #4ade80; }
            .yield-mid { color: #fbbf24; }
            .yield-high { color: #f87171; font-weight: 900; }
            body { background-color: #0b1120; }
        </style>
    </head>
    <body class="text-slate-200 p-4 md:p-8 font-sans">
        <div class="max-w-6xl mx-auto">
            <div class="flex flex-col md:flex-row justify-between items-center mb-6 gap-4 text-center md:text-left">
                <div>
                    <h1 class="text-3xl font-black tracking-tighter text-white">⚡ POWER-SCAN <span class="text-green-500">5000</span></h1>
                    <p class="text-slate-500 text-sm italic font-medium tracking-wide">Volume > $1k | Tri par échéance ascendante</p>
                </div>
                <div id="status" class="bg-green-900/20 text-green-400 px-6 py-2 rounded-xl border border-green-800/50 text-sm font-bold shadow-lg">
                    Lancement du scan...
                </div>
            </div>
            
            <div class="bg-slate-900/60 rounded-3xl overflow-hidden border border-slate-800 shadow-2xl backdrop-blur-md">
                <table class="w-full text-left text-[11px] md:text-xs">
                    <thead class="bg-slate-800 text-slate-400 uppercase tracking-widest text-[10px] font-black">
                        <tr>
                            <th class="p-5">Marché</th>
                            <th class="p-5">Côté</th>
                            <th class="p-5 text-right">Volume</th>
                            <th class="p-5 text-right">Prix</th>
                            <th class="p-5 text-right">Temps</th>
                            <th class="p-5 text-right text-green-400">Yield Score</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-800/40">
                        <tr><td colspan="6" class="p-32 text-center">
                            <div class="flex flex-col items-center gap-4">
                                <div class="w-10 h-10 border-4 border-green-500 border-t-transparent rounded-full animate-spin"></div>
                                <span class="text-slate-500 font-bold uppercase tracking-widest text-xs">Deep scan des 5000 marchés en cours...</span>
                            </div>
                        </td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        <script>
            async function load() {
                try {
                    const start = Date.now();
                    const res = await fetch('/api/markets');
                    const data = await res.json();
                    const tbody = document.getElementById('content');
                    const status = document.getElementById('status');
                    
                    const duration = ((Date.now() - start) / 1000).toFixed(1);
                    status.innerText = data.length + " opportunités en " + duration + "s";
                    
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" class="p-20 text-center text-slate-600 font-bold uppercase">Aucune opportunité (Volume > $1k)</td></tr>';
                        return;
                    }

                    tbody.innerHTML = data.map(m => {
                        let yieldClass = 'yield-low';
                        if (m.yield > 20) yieldClass = 'yield-high';
                        else if (m.yield > 10) yieldClass = 'yield-mid';

                        const volStr = m.volume >= 1000 ? (m.volume/1000).toFixed(1) + 'k' : Math.round(m.volume);

                        return `
                        <tr class="hover:bg-green-500/5 transition-all duration-150 group border-l-4 border-transparent hover:border-green-500">
                            <td class="p-5 font-bold text-slate-300 group-hover:text-white leading-tight">
                                <a href="https://polymarket.com/market/${m.slug}" target="_blank" class="block transition-transform hover:translate-x-1">${m.question}</a>
                            </td>
                            <td class="p-5 text-center">
                                <span class="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-700 text-[10px] font-black text-slate-400">${m.side}</span>
                            </td>
                            <td class="p-5 text-right text-slate-500 font-mono italic">$${volStr}</td>
                            <td class="p-5 text-right font-mono text-slate-300 font-medium">${m.price.toFixed(3)}</td>
                            <td class="p-5 text-right font-mono text-orange-400 font-bold">${m.days_left.toFixed(2)}j</td>
                            <td class="p-5 text-right font-mono ${yieldClass} text-base">${m.yield.toFixed(2)}</td>
                        </tr>`;
                    }).join('');
                } catch (e) {
                    document.getElementById('status').innerText = "Timeout ou erreur serveur.";
                }
            }
            load();
        </script>
    </body>
    </html>
    """)

@app.route("/api/markets")
def get_markets():
    all_results = []
    now = datetime.now(timezone.utc)
    
    # On fait 5 requêtes (5000 marchés au total)
    for offset in [0, 1000, 2000, 3000, 4000]:
        try:
            params = {
                "active": "true",
                "closed": "false",
                "limit": 1000,
                "offset": offset,
                "order": "endDate", # On reste sur les échéances proches pour maximiser le Yield
                "ascending": "true"
            }
            # Timeout à 10s par requête, total max théorique 50s (attention sur Railway)
            r = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=12)
            markets = r.json()
            
            if not markets: break

            for m in markets:
                try:
                    # 1. Filtre Volume : Retour à $1000
                    volume = float(m.get("volume", 0) or 0)
                    if volume < 1000: continue

                    # 2. Filtre Temps : Entre 0.5j et 30j
                    end_date_str = m.get("endDate") or m.get("end_date_iso")
                    if not end_date_str: continue
                    end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days = (end_dt - now).total_seconds() / 86400
                    if days <= 0.5 or days > 30: continue

                    # 3. Extraction Prix
                    prices_str = m.get("outcomePrices")
                    if not prices_str: continue
                    prices = json.loads(prices_str)
                    p_yes, p_no = float(prices[0]), float(prices[1])

                    # 4. Logique Yield & Prix [0.90 - 0.99]
                    match = None
                    if 0.90 <= p_yes < 0.99:
                        match = {"side": "YES", "p": p_yes}
                    elif 0.90 <= p_no < 0.99:
                        match = {"side": "NO", "p": p_no}

                    if match:
                        score = (1 / match["p"]) ** (365 / days)
                        if score >= 5:
                            all_results.append({
                                "question": m.get("question"),
                                "slug": m.get("slug"),
                                "side": match["side"],
                                "price": match["p"],
                                "days_left": days,
                                "yield": score,
                                "volume": volume
                            })
                except: continue
            time.sleep(0.05) # Délai très court pour aller vite
        except: break

    # Tri par Yield décroissant
    all_results.sort(key=lambda x: x["yield"], reverse=True)
    return jsonify(all_results[:150])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
