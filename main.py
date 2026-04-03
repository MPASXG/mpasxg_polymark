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
        <title>Screener Yield Polymarket</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-slate-100 p-4 md:p-12 font-sans">
        <div class="max-w-6xl mx-auto">
            <h1 class="text-3xl font-bold mb-2">🚀 Polymarket <span class="text-green-400">Yield Hunter</span></h1>
            <p class="text-slate-400 text-sm mb-8 tracking-wide italic">Filtres : Prix [0.90 - 0.99] | Échéance > 0.5j | Yield Annualisé > 10</p>
            
            <div class="bg-slate-800 rounded-2xl shadow-2xl overflow-hidden border border-slate-700">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-700/70 text-slate-300 text-xs uppercase font-bold">
                        <tr>
                            <th class="p-5">Marché</th>
                            <th class="p-5 text-center">Côté</th>
                            <th class="p-5 text-right">Prix</th>
                            <th class="p-5 text-right">Temps</th>
                            <th class="p-5 text-right text-green-400">Yield (Score)</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-700">
                        <tr><td colspan="5" class="p-20 text-center text-slate-500 animate-pulse text-lg">Scan des opportunités en cours...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        <script>
            fetch('/api/markets')
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById('content');
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="p-10 text-center text-slate-500 font-medium text-lg">Aucun yield > 10 détecté avec ces critères.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.map(m => `
                        <tr class="hover:bg-slate-700/50 transition cursor-default">
                            <td class="p-5 text-sm font-semibold leading-tight">${m.question}</td>
                            <td class="p-5 text-center">
                                <span class="px-3 py-1 rounded-full text-[10px] font-black tracking-tighter ${m.side === 'YES' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' : 'bg-purple-500/20 text-purple-400 border border-purple-500/40'}">
                                    ${m.side}
                                </span>
                            </td>
                            <td class="p-5 text-right font-mono font-bold text-slate-300">${m.price.toFixed(3)}$</td>
                            <td class="p-5 text-right font-mono text-orange-300 text-sm italic">${m.days_left.toFixed(1)}j</td>
                            <td class="p-5 text-right font-mono font-black text-green-400 text-xl">
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
    params = {
        "active": "true",
        "closed": "false",
        "limit": 300, # On augmente le scan car le filtre > 10 est sélectif
        "order": "volume",
        "ascending": "false"
    }
    
    try:
        response = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=15)
        raw_markets = response.json()
        
        filtered_results = []
        now = datetime.now(timezone.utc)
        
        for m in raw_markets:
            if len(filtered_results) >= 30:
                break
                
            try:
                # 1. Calcul du temps restant
                end_date_str = m.get("endDate") or m.get("end_date_iso")
                if not end_date_str: continue
                
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                days_left = (end_date - now).total_seconds() / 86400

                # Critère de temps > 0.5 jour
                if days_left <= 0.5: continue

                # 2. Extraction des prix
                prices_raw = m.get("outcomePrices")
                if not prices_raw: continue
                prices = eval(prices_raw)
                
                p_yes = float(prices[0])
                p_no = float(prices[1])
                
                # 3. Logique de sélection (Prix entre 0.90 et 0.99)
                match = None
                if 0.90 <= p_yes < 0.99:
                    match = {"side": "YES", "price": p_yes}
                elif 0.90 <= p_no < 0.99:
                    match = {"side": "NO", "price": p_no}

                if match:
                    # Calcul de la formule : (1 / price) ^ (365 / days_left)
                    # On retire le "-1" et le "*100" pour avoir le chiffre brut
                    annual_yield_brut = (1 / match["price"]) ** (365 / days_left)
                    
                    # Filtre : Yield supérieur à 10
                    if annual_yield_brut >= 10:
                        filtered_results.append({
                            "question": m.get("question"),
                            "side": match["side"],
                            "price": match["price"],
                            "days_left": days_left,
                            "yield": annual_yield_brut
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
