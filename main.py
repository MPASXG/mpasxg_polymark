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
        <title>Deep Scan Précision 10k</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-slate-100 p-4 md:p-12 font-sans text-xs">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-between items-end mb-6">
                <div>
                    <h1 class="text-3xl font-bold italic tracking-tighter">🚀 PRECISION SCAN <span class="text-green-500">10,000</span></h1>
                    <p class="text-slate-400 mt-1 font-medium text-sm">Filtres : Prix Réel [0.90-0.99] | Échéance > 0.5j | Yield > 5</p>
                </div>
                <div id="status-badge" class="bg-slate-800 px-4 py-2 rounded-lg border border-slate-700 text-slate-300 font-bold text-sm">
                    Recherche des prix réels...
                </div>
            </div>
            
            <div class="bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-700/70 text-slate-300 uppercase font-bold sticky top-0">
                        <tr>
                            <th class="p-4">Marché</th>
                            <th class="p-4 text-center">Côté</th>
                            <th class="p-4 text-right">Vrai Prix</th>
                            <th class="p-4 text-right text-orange-300">Échéance</th>
                            <th class="p-4 text-right text-green-400">Yield (Score)</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-700">
                        <tr><td colspan="5" class="p-20 text-center text-slate-500 animate-pulse text-lg font-medium italic">
                            Calcul des rendements basés sur le carnet d'ordres...
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
                    document.getElementById('status-badge').innerText = data.length + ' opportunités réelles';
                    
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="p-10 text-center text-slate-500 font-medium">Aucun prix valide trouvé dans les 10k marchés.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.map(m => `
                        <tr class="hover:bg-slate-700/50 transition border-l-4 border-transparent hover:border-green-500">
                            <td class="p-4 text-sm font-semibold leading-tight max-w-lg">
                                <a href="https://polymarket.com/market/${m.slug}" target="_blank" class="hover:text-blue-400">${m.question}</a>
                            </td>
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
    
    # On scanne par blocs
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
            if not markets: break

            for m in markets:
                if len(all_filtered) >= 150: break
                
                try:
                    # 1. Vérification du temps (on élimine direct si expiré ou trop proche)
                    end_date_str = m.get("endDate") or m.get("end_date_iso")
                    if not end_date_str: continue
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days_left = (end_date - now).total_seconds() / 86400
                    if days_left <= 0.5: continue

                    # 2. RÉCUPÉRATION DES PRIX RÉELS (Ordres de vente les plus bas)
                    # bestAsk[0] = Prix pour YES, bestAsk[1] = Prix pour NO
                    asks_raw = m.get("bestAsk")
                    if not asks_raw: continue
                    
                    # On utilise le prix de vente (Ask) car c'est le prix auquel tu achètes
                    p_yes = float(m.get("bestAsk", [0,0])[0])
                    p_no = float(m.get("bestAsk", [0,0])[1])
                    
                    # Si les asks sont à 0, on se rabat sur outcomePrices (moins précis)
                    if p_yes == 0 or p_no == 0:
                        prices_raw = m.get("outcomePrices")
                        if not prices_raw: continue
                        prices = eval(prices_raw)
                        p_yes = p_yes if p_yes > 0 else float(prices[0])
                        p_no = p_no if p_no > 0 else float(prices[1])

                    # 3. Sélection et Calcul
                    match = None
                    if 0.90 <= p_yes < 0.99:
                        match = {"side": "YES", "p": p_yes}
                    elif 0.90 <= p_no < 0.99:
                        match = {"side": "NO", "p": p_no}

                    if match:
                        annual_yield = (1 / match["p"]) ** (365 / days_left)
                        if annual_yield >= 5:
                            all_filtered.append({
                                "question": m.get("question"),
                                "slug": m.get("slug"),
                                "side": match["side"],
                                "price": match["p"],
                                "days_left": days_left,
                                "yield": annual_yield
                            })
                except:
                    continue
            time.sleep(0.1)
        except:
            break

    all_filtered.sort(key=lambda x: x["yield"], reverse=True)
    return jsonify(all_filtered)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
