from flask import Flask, jsonify, render_template_string
import requests
from datetime import datetime, timezone
import json

app = Flask(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Yield Hunter Pro</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .yield-low { color: #4ade80; } /* Vert */
            .yield-mid { color: #fbbf24; } /* Orange */
            .yield-high { color: #f87171; font-weight: 900; text-decoration: underline; } /* Rouge */
        </style>
    </head>
    <body class="bg-slate-900 text-white p-5 font-sans">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-between items-center mb-8 border-b border-slate-700 pb-4">
                <h1 class="text-2xl font-bold italic tracking-tighter text-blue-400">🚀 Yield Hunter <span class="text-white text-sm not-italic ml-2 opacity-50">Volume > $1k</span></h1>
                <div id="status" class="text-xs bg-slate-800 px-3 py-1 rounded-full border border-slate-600">Scan initial...</div>
            </div>
            
            <div class="bg-slate-800 rounded-xl overflow-hidden border border-slate-700 shadow-2xl">
                <table class="w-full text-left text-[11px] md:text-xs">
                    <thead class="bg-slate-700 text-slate-400 uppercase tracking-widest">
                        <tr>
                            <th class="p-4">Question</th>
                            <th class="p-4">Side</th>
                            <th class="p-4 text-right">Volume</th>
                            <th class="p-4 text-right">Prix</th>
                            <th class="p-4 text-right">Temps</th>
                            <th class="p-4 text-right">Yield Score</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-700">
                        <tr><td colspan="6" class="p-20 text-center animate-pulse">Filtrage des marchés actifs...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        <script>
            async function load() {
                try {
                    const res = await fetch('/api/markets');
                    const data = await res.json();
                    const tbody = document.getElementById('content');
                    const status = document.getElementById('status');
                    
                    status.innerText = data.length + " opportunités (Scan 2000)";
                    
                    tbody.innerHTML = data.map(m => {
                        let yieldClass = 'yield-low';
                        if (m.yield > 20) yieldClass = 'yield-high';
                        else if (m.yield > 10) yieldClass = 'yield-mid';

                        const volStr = m.volume >= 1000 ? (m.volume/1000).toFixed(1) + 'k' : m.volume;

                        return `
                        <tr class="hover:bg-slate-700/50 transition border-l-2 border-transparent hover:border-blue-500">
                            <td class="p-4 font-medium"><a href="https://polymarket.com/market/${m.slug}" target="_blank" class="hover:text-blue-400 transition">${m.question}</a></td>
                            <td class="p-4 text-center"><span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[9px] font-bold">${m.side}</span></td>
                            <td class="p-4 text-right text-slate-400">$${volStr}</td>
                            <td class="p-4 text-right font-mono">${m.price.toFixed(3)}</td>
                            <td class="p-4 text-right font-mono text-orange-400">${m.days_left.toFixed(1)}j</td>
                            <td class="p-4 text-right font-mono ${yieldClass} text-sm">${m.yield.toFixed(2)}</td>
                        </tr>`;
                    }).join('');
                } catch (e) {
                    document.getElementById('status').innerText = "Erreur de connexion.";
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
    
    for offset in [0, 1000]:
        try:
            params = {
                "active": "true",
                "closed": "false",
                "limit": 1000,
                "offset": offset,
                "order": "volume",
                "ascending": "false"
            }
            r = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=10)
            markets = r.json()
            
            for m in markets:
                try:
                    # 1. Filtre Volume ($1000 minimum)
                    volume = float(m.get("volume", 0) or 0)
                    if volume < 1000: continue

                    # 2. Filtre Temps (> 0.5 jour)
                    end_date_str = m.get("endDate") or m.get("end_date_iso")
                    if not end_date_str: continue
                    end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days = (end_dt - now).total_seconds() / 86400
                    if days <= 0.5: continue

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
                except:
                    continue
        except:
            break

    # Tri par Yield décroissant
    all_results.sort(key=lambda x: x["yield"], reverse=True)
    return jsonify(all_results[:150])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
