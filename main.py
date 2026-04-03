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
        <title>Screener Polymarket Pro</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-slate-100 p-6 md:p-12">
        <div class="max-w-5xl mx-auto">
            <h1 class="text-2xl font-bold mb-2">🎯 Opportunités Filtrées</h1>
            <p class="text-slate-400 text-sm mb-6">Prix entre 0.90$ et 0.99$ | Temps > 12h (0.5j)</p>
            
            <div class="bg-slate-800 rounded-xl shadow-2xl overflow-hidden border border-slate-700">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-slate-700/50 text-slate-400 text-xs uppercase tracking-wider">
                        <tr>
                            <th class="p-4">Marché</th>
                            <th class="p-4 text-center">Côté</th>
                            <th class="p-4 text-right">Prix actuel</th>
                            <th class="p-4 text-right">Échéance</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-slate-700">
                        <tr><td colspan="4" class="p-10 text-center text-slate-500 italic text-sm">Analyse des marchés en cours...</td></tr>
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
                        tbody.innerHTML = '<tr><td colspan="4" class="p-10 text-center text-slate-500">Aucun marché ne correspond aux critères actuellement.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.map(m => `
                        <tr class="hover:bg-slate-700/40 transition">
                            <td class="p-4 text-sm font-medium leading-snug">${m.question}</td>
                            <td class="p-4 text-center">
                                <span class="px-2 py-1 rounded text-[10px] font-bold ${m.side === 'YES' ? 'bg-blue-500/20 text-blue-400' : 'bg-purple-500/20 text-purple-400'} border ${m.side === 'YES' ? 'border-blue-500/30' : 'border-purple-500/30'}">
                                    ${m.side}
                                </span>
                            </td>
                            <td class="p-4 text-right font-mono font-bold text-green-400">${m.price.toFixed(3)}$</td>
                            <td class="p-4 text-right font-mono text-orange-300 text-sm italic">${m.days_left.toFixed(1)}j</td>
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
        "limit": 200, # On scanne large pour trouver les pépites
        "order": "volume",
        "ascending": "false"
    }
    
    try:
        response = requests.get(f"{GAMMA_BASE}/markets", params=params, timeout=10)
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

                # Condition de temps : > 0.5 jour
                if days_left <= 0.5: continue

                # 2. Extraction et vérification des prix
                prices_raw = m.get("outcomePrices")
                if not prices_raw: continue
                prices = eval(prices_raw)
                
                p_yes = float(prices[0])
                p_no = float(prices[1])
                
                # Condition de prix : entre 0.90 et 0.99 (exclu)
                match = None
                if 0.90 <= p_yes < 0.99:
                    match = {"side": "YES", "price": p_yes}
                elif 0.90 <= p_no < 0.99:
                    match = {"side": "NO", "price": p_no}

                if match:
                    filtered_results.append({
                        "question": m.get("question"),
                        "side": match["side"],
                        "price": match["price"],
                        "days_left": days_left
                    })
            except:
                continue
                
        return jsonify(filtered_results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
