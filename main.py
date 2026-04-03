from flask import Flask, jsonify, render_template_string
import requests
from datetime import datetime, timezone

app = Flask(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

@app.route("/")
def index():
    # Une interface ultra-simple pour voir la liste
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Polymarket > 90c</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-white p-10">
        <h1 class="text-2xl font-bold mb-6">Top 30 Marchés (Prix > 0.90$)</h1>
        <div class="bg-gray-800 rounded-lg overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-gray-700">
                    <tr>
                        <th class="p-4">Question</th>
                        <th class="p-4">Côté</th>
                        <th class="p-4">Prix</th>
                    </tr>
                </thead>
                <tbody id="content">
                    <tr><td colspan="3" class="p-4">Chargement...</td></tr>
                </tbody>
            </table>
        </div>
        <script>
            fetch('/api/markets')
                .then(res => res.json())
                .then(data => {
                    const html = data.map(m => `
                        <tr class="border-b border-gray-700">
                            <td class="p-4 text-sm">${m.question}</td>
                            <td class="p-4 font-bold text-blue-400">${m.side}</td>
                            <td class="p-4 font-mono">${m.price}$</td>
                        </tr>
                    `).join('');
                    document.getElementById('content').innerHTML = html || '<tr><td colspan="3" class="p-4">Aucun marché trouvé.</td></tr>';
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
        "limit": 100, # On en prend 100 pour être sûr d'en trouver 30 qui matchent
        "order": "volume",
        "ascending": "false"
    }
    
    try:
        response = requests.get(f"{GAMMA_BASE}/markets", params=params)
        raw_markets = response.json()
        
        filtered_results = []
        
        for m in raw_markets:
            if len(filtered_results) >= 30: # Limite à 30
                break
                
            try:
                # Récupération des prix [OUI, NON]
                prices = eval(m.get("outcomePrices", "[]"))
                if not prices or len(prices) < 2: continue
                
                price_yes = float(prices[0])
                price_no = float(prices[1])
                
                # Vérification de la condition > 0.90
                if price_yes >= 0.90:
                    filtered_results.append({
                        "question": m.get("question"),
                        "side": "YES",
                        "price": price_yes
                    })
                elif price_no >= 0.90:
                    filtered_results.append({
                        "question": m.get("question"),
                        "side": "NO",
                        "price": price_no
                    })
            except:
                continue
                
        return jsonify(filtered_results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
