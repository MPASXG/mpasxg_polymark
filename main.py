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
        <title>Polymarket > 90c</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-white p-10">
        <h1 class="text-2xl font-bold mb-6">Top 30 Marchés (Prix > 0.90$)</h1>
        <div class="bg-gray-800 rounded-lg overflow-hidden shadow-xl">
            <table class="w-full text-left">
                <thead class="bg-gray-700 text-gray-300 uppercase text-xs">
                    <tr>
                        <th class="p-4">Question</th>
                        <th class="p-4 text-center">Côté</th>
                        <th class="p-4 text-right">Prix</th>
                        <th class="p-4 text-right">Jours restants</th>
                    </tr>
                </thead>
                <tbody id="content">
                    <tr><td colspan="4" class="p-10 text-center text-gray-500">Chargement des données...</td></tr>
                </tbody>
            </table>
        </div>
        <script>
            fetch('/api/markets')
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById('content');
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center">Aucun marché trouvé.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.map(m => `
                        <tr class="border-b border-gray-700 hover:bg-gray-750 transition">
                            <td class="p-4 text-sm font-medium">${m.question}</td>
                            <td class="p-4 text-center">
                                <span class="px-2 py-1 rounded text-[10px] font-bold ${m.side === 'YES' ? 'bg-blue-900 text-blue-300' : 'bg-purple-900 text-purple-300'}">
                                    ${m.side}
                                </span>
                            </td>
                            <td class="p-4 text-right font-mono text-green-400 font-bold">${m.price.toFixed(2)}$</td>
                            <td class="p-4 text-right font-mono text-orange-400">
                                ${m.days_left > 0 ? m.days_left.toFixed(1) + 'j' : 'Expire bientôt'}
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
        "limit": 150, # On augmente la limite de recherche pour trouver nos 30
        "order": "volume",
        "ascending": "false"
    }
    
    try:
        response = requests.get(f"{GAMMA_BASE}/markets", params=params)
        raw_markets = response.json()
        
        filtered_results = []
        now = datetime.now(timezone.utc)
        
        for m in raw_markets:
            if len(filtered_results) >= 30:
                break
                
            try:
                # 1. Extraction des prix
                prices_raw = m.get("outcomePrices")
                if not prices_raw: continue
                prices = eval(prices_raw)
                if len(prices) < 2: continue
                
                price_yes = float(prices[0])
                price_no = float(prices[1])
                
                # 2. Calcul du temps restant
                end_date_str = m.get("endDate")
                days_left = 0
                if end_date_str:
                    # On nettoie la date pour Python (Z -> +00:00)
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days_left = (end_date - now).total_seconds() / 86400

                # 3. Filtre Prix > 0.90
                match = None
                if price_yes >= 0.90:
                    match = {"side": "YES", "price": price_yes}
                elif price_no >= 0.90:
                    match = {"side": "NO", "price": price_no}

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
