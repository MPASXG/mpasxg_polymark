from flask import Flask, jsonify, render_template_string
import requests
from datetime import datetime, timezone

app = Flask(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Screener Yield 150</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-slate-100 p-4 md:p-12 font-sans text-xs">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-between items-end mb-6">
                <div>
                    <h1 class="text-3xl font-bold">🚀 Polymarket <span class="text-green-400">Yield Hunter</span></h1>
                    <p class="text-slate-400 mt-1 italic font-medium text-sm">Filtres : Prix [0.90 - 0.99] | Échéance > 0.5j | Yield > 5 | Max 150</p>
                </div>
                <div id="count-badge" class="bg-slate-800 px-4 py-2 rounded-lg border border-slate-700 text-slate-300 font-bold text-sm italic">
                    Scan en cours...
                </div>
            </div>
            
            <div class="bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-700/70 text-slate-300 uppercase font-bold sticky top-0">
                        <tr>
                            <th class="p-4">Marché</th>
                            <th class="p-4 text-center">Côté</th>
                            <th class="p-4 text-right">Prix</th>
                            <th class="p-4 text-right text-orange-300 text-xs">Échéance</th>
                            <th class="p-4 text-right text-green-400">Yield (Score)</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-700">
                        <tr><td colspan="5" class="p-20 text-center text-slate-500 animate-pulse text-lg font-medium italic">Analyse massive de l'API (1000 marchés)...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        <script>
            fetch('/api/markets')
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById('content');
                    document.getElementById('count-badge').innerText = data.length + ' opportunités trouvées';
                    
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="p-10 text-center text-slate-500 font-medium">Aucun marché ne correspond aux critères.</td></tr>';
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
                            <td class="p-4 text-right font-mono font-bold text-slate-300 text-sm italic">${m.price.toFixed(3)}$</td>
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
    # On demande 1000 marchés pour filtrer au maximum
    params = {
        "active": "true",
        "closed": "false",
        "limit": 1000, 
        "order": "volume",
        "ascending": "false"
    }
    
    try:
        # Timeout augmenté car 1000 items c'est lourd
        response = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=20)
        raw_markets = response.json()
        
        filtered_results = []
        now = datetime.now(timezone.utc)
        
        for m in raw_markets:
            if len(filtered_results) >= 150: # Limite à 150 marchés extraits
                break
                
            try:
                # 1. Temps restant
                end_date_str = m.get("endDate") or m.get("end_date_iso")
                if not end_date_str: continue
                
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                days_left = (end_date - now).total_seconds() / 86400

                if days_left <= 0.5: continue

                # 2. Prix
                prices_raw = m.get("outcomePrices")
                if not prices_raw: continue
                prices = eval(prices_raw)
                p_yes, p_no = float(prices[0]), float(prices[1])
                
                # 3. Sélection & Calcul
                match = None
                if 0.90 <= p_yes < 0.99:
                    match = {"side": "YES", "p": p_yes}
                elif 0.90 <= p_no < 0.99:
                    match = {"side": "NO", "p": p_no}

                if match:
                    # Formule (1/price)^(365/days)
                    annual_yield = (1 / match["p"]) ** (365 / days_left)
                    
                    # Filtre Yield > 5
                    if annual_yield >= 5:
                        filtered_results.append({
                            "question": m.get("question"),
                            "side": match["side"],
                            "price": match["p"],
                            "days_left": days_left,
                            "yield": annual_yield
                        })
            except:
                continue
                
        # Tri par Yield décroissant
        filtered_results.sort(key=lambda x: x["yield"], reverse=True)
        return jsonify(filtered_results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
