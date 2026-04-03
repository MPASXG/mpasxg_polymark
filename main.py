from flask import Flask, jsonify, render_template_string
import requests
from datetime import datetime, timezone
import time

app = Flask(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Deep Scan Yield 10k</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-slate-100 p-4 md:p-12 font-sans text-xs">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-between items-end mb-6">
                <div>
                    <h1 class="text-3xl font-bold italic tracking-tighter">🚀 DEEP SCAN <span class="text-green-500">10,000</span></h1>
                    <p class="text-slate-400 mt-1 font-medium text-sm">Filtres : Prix [0.90-0.99] | Échéance > 0.5j | Yield > 5 | Top 150</p>
                </div>
                <div id="status-badge" class="bg-slate-800 px-4 py-2 rounded-lg border border-slate-700 text-slate-300 font-bold text-sm">
                    Initialisation du scan...
                </div>
            </div>
            
            <div class="bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-700/70 text-slate-300 uppercase font-bold sticky top-0">
                        <tr>
                            <th class="p-4">Marché</th>
                            <th class="p-4 text-center">Côté</th>
                            <th class="p-4 text-right">Prix</th>
                            <th class="p-4 text-right text-orange-300">Échéance</th>
                            <th class="p-4 text-right text-green-400">Yield (Score)</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-700">
                        <tr><td colspan="5" class="p-20 text-center text-slate-500 animate-pulse text-lg font-medium italic">
                            Pagination de l'API en cours (Scan profond des 10,000 marchés)...
                        </td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        <script>
            fetch('/api/markets')
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById('content');
                    document.getElementById('status-badge').innerText = data.length + ' opportunités extraites';
                    
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="p-10 text-center text-slate-500 font-medium">Aucun marché trouvé dans les 10k derniers.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.map(m => `
                        <tr class="hover:bg-slate-700/50 transition border-l-4 border-transparent hover:border-green-500">
                            <td class="p-4 text-sm font-semibold leading-tight max-w-lg">${m.question}</td>
                            <td class="p-4 text-center">
                                <span class="px-2 py-1 rounded-md text-[10px] font-black tracking-tighter ${m.side === 'YES' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' : 'bg-purple-500/20 text-purple-400 border border-purple-500/40'}">
                                    ${m.side}
                                </span>
                            </td>
                            <td class="p-4 text-right font-mono font-bold text-slate-300 italic">${m.price.toFixed(3)}$</td>
                            <td class="p-4 text-right font-mono text-orange-300 font-medium">${m.days_left.toFixed(1)}j</td>
                            <td class="p-4 text-right font-mono font-black text-green-400 text-lg">
                                ${m.yield.toFixed(2)}
                            </td>
                        </tr>
                    `).join('');
                });
        </script>
    </body>
    </html>
    """)

@app.route("/api/markets")
def get_markets():
    all_filtered = []
    now = datetime.now(timezone.utc)
    
    # On va faire 10 requêtes de 1000 marchés pour atteindre 10,000
    for offset in range(0, 10000, 1000):
        if len(all_filtered) >= 150:
            break
            
        params = {
            "active": "true",
            "closed": "false",
            "limit": 1000,
            "offset": offset,
            "order": "volume",
            "ascending": "false"
        }
        
        try:
            response = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=15)
            markets = response.json()
            
            if not markets:
                break

            for m in markets:
                if len(all_filtered) >= 150:
                    break
                
                try:
                    # Temps restant
                    end_date_str = m.get("endDate") or m.get("end_date_iso")
                    if not end_date_str: continue
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days_left = (end_date - now).total_seconds() / 86400
                    if days_left <= 0.5: continue

                    # Prix
                    prices_raw = m.get("outcomePrices")
                    if not prices_raw: continue
                    prices = eval(prices_raw)
                    p_yes, p_no = float(prices[0]), float(prices[1])
                    
                    # Sélection
                    match = None
                    if 0.90 <= p_yes < 0.99:
                        match = {"side": "YES", "p": p_yes}
                    elif 0.90 <= p_no < 0.99:
                        match = {"side": "NO", "p": p_no}

                    if match:
                        # Yield Score
                        annual_yield = (1 / match["p"]) ** (365 / days_left)
                        if annual_yield >= 5:
                            all_filtered.append({
                                "question": m.get("question"),
                                "side": match["side"],
                                "price": match["p"],
                                "days_left": days_left,
                                "yield": annual_yield
                            })
                except:
                    continue
            
            # Petit délai pour ne pas se faire bannir par l'API
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Erreur à l'offset {offset}: {e}")
            break

    # Tri final
    all_filtered.sort(key=lambda x: x["yield"], reverse=True)
    return jsonify(all_filtered)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
