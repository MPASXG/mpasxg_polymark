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
        <title>Yield Hunter V3</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-white p-5 font-sans">
        <div class="max-w-5xl mx-auto">
            <h1 class="text-2xl font-bold text-green-400 mb-4 text-center">🚀 Yield Hunter V3 (Stable)</h1>
            <div id="status" class="text-center text-slate-400 mb-6 text-sm italic">Analyse des marchés en cours...</div>
            
            <div class="bg-slate-800 rounded-xl overflow-hidden border border-slate-700 shadow-2xl">
                <table class="w-full text-left text-xs">
                    <thead class="bg-slate-700 text-slate-300 uppercase">
                        <tr>
                            <th class="p-4">Question</th>
                            <th class="p-4">Côté</th>
                            <th class="p-4 text-right">Prix</th>
                            <th class="p-4 text-right">Temps</th>
                            <th class="p-4 text-right text-green-400 font-bold">Yield</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-700">
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
                    
                    if (data.error) {
                        status.innerText = "Erreur: " + data.error;
                        return;
                    }

                    status.innerText = data.length + " marchés trouvés (Scan 2000)";
                    
                    tbody.innerHTML = data.map(m => `
                        <tr class="hover:bg-slate-700/50 transition">
                            <td class="p-4 font-medium"><a href="https://polymarket.com/market/${m.slug}" target="_blank" class="hover:underline text-blue-300">${m.question}</a></td>
                            <td class="p-4 text-center"><span class="px-2 py-1 rounded bg-slate-900 border border-slate-600 text-[10px]">${m.side}</span></td>
                            <td class="p-4 text-right font-mono">${m.price.toFixed(3)}</td>
                            <td class="p-4 text-right font-mono text-orange-400">${m.days_left.toFixed(1)}j</td>
                            <td class="p-4 text-right font-mono font-bold text-green-400 text-sm">${m.yield.toFixed(2)}</td>
                        </tr>
                    `).join('');
                } catch (e) {
                    document.getElementById('status').innerText = "Serveur indisponible ou timeout.";
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
    
    # On limite à 2 requêtes (2000 marchés) pour éviter le timeout de Railway
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
                    # 1. Filtre Temps
                    end_date_str = m.get("endDate") or m.get("end_date_iso")
                    if not end_date_str: continue
                    end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days = (end_dt - now).total_seconds() / 86400
                    if days <= 0.5: continue

                    # 2. Extraction Prix (Méthode robuste)
                    # On teste d'abord outcomePrices qui est le plus stable dans l'API
                    prices_str = m.get("outcomePrices")
                    if not prices_str: continue
                    prices = json.loads(prices_str)
                    
                    p_yes = float(prices[0])
                    p_no = float(prices[1])

                    # 3. Logique Yield
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
                                "yield": score
                            })
                except:
                    continue
        except:
            break

    all_results.sort(key=lambda x: x["yield"], reverse=True)
    return jsonify(all_results[:150])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
