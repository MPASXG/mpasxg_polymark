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
        <title>Yield Hunter 10k Deep</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#050810] text-slate-200 p-4 md:p-8 font-sans">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-between items-center mb-8 bg-slate-900/50 p-6 rounded-2xl border border-slate-800">
                <div>
                    <h1 class="text-3xl font-black text-white tracking-tighter">🧠 DEEP-SCAN <span class="text-purple-500">10,000</span></h1>
                    <p class="text-slate-500 text-xs mt-1 uppercase tracking-widest font-bold">Volume > $1k | Scan Intégral</p>
                </div>
                <div id="status" class="text-purple-400 font-mono text-sm bg-purple-900/20 px-4 py-2 rounded-lg border border-purple-800/30">
                    Calcul en cours...
                </div>
            </div>
            
            <div class="bg-slate-900/80 rounded-3xl overflow-hidden border border-white/5 shadow-2xl">
                <table class="w-full text-left text-[11px] md:text-xs">
                    <thead class="bg-white/5 text-slate-400 uppercase font-black">
                        <tr>
                            <th class="p-5">Marché</th>
                            <th class="p-5">Côté</th>
                            <th class="p-4 text-right">Volume</th>
                            <th class="p-4 text-right">Prix</th>
                            <th class="p-4 text-right text-orange-400">Temps</th>
                            <th class="p-5 text-right text-purple-400">Yield</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-white/5">
                        <tr><td colspan="6" class="p-32 text-center text-slate-500 italic">Analyse massive de 10 blocs de données...</td></tr>
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
                    if (data.error) { tbody.innerHTML = `<tr><td colspan="6" class="p-10 text-center text-red-400">${data.error}</td></tr>`; return; }
                    
                    document.getElementById('status').innerText = data.length + " MATCHES";
                    tbody.innerHTML = data.map(m => `
                        <tr class="hover:bg-purple-500/5 transition group">
                            <td class="p-5 font-bold text-slate-300 leading-tight">
                                <a href="https://polymarket.com/market/${m.slug}" target="_blank" class="hover:text-purple-400 transition inline-block">${m.question}</a>
                            </td>
                            <td class="p-5 text-center"><span class="bg-black px-2 py-1 rounded border border-slate-800 text-[9px]">${m.side}</span></td>
                            <td class="p-4 text-right text-slate-500">$${m.volume >= 1000 ? (m.volume/1000).toFixed(0)+'k' : m.volume}</td>
                            <td class="p-4 text-right font-mono text-slate-400">${m.price.toFixed(3)}</td>
                            <td class="p-4 text-right font-mono text-orange-500 font-bold">${m.days_left.toFixed(2)}j</td>
                            <td class="p-5 text-right font-mono text-purple-400 text-base font-black">${m.yield.toFixed(2)}</td>
                        </tr>`).join('');
                } catch (e) { document.getElementById('status').innerText = "TIMEOUT"; }
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
    session = requests.Session() # Session persistante pour la vitesse
    
    # 10 blocs de 1000 pour atteindre 10,000
    for offset in range(0, 10000, 1000):
        try:
            params = {
                "active": "true",
                "closed": "false",
                "limit": 1000,
                "offset": offset,
                "order": "endDate",
                "ascending": "true"
            }
            r = session.get(f"{GAMMA_BASE}/markets", params=params, timeout=10)
            markets = r.json()
            if not markets: break

            for m in markets:
                try:
                    vol = float(m.get("volume", 0) or 0)
                    if vol < 1000: continue

                    end_date_str = m.get("endDate") or m.get("end_date_iso")
                    if not end_date_str: continue
                    end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days = (end_dt - now).total_seconds() / 86400
                    if days <= 0.5 or days > 45: continue

                    prices = json.loads(m.get("outcomePrices", "[]"))
                    if len(prices) < 2: continue
                    p_yes, p_no = float(prices[0]), float(prices[1])

                    match = None
                    if 0.90 <= p_yes < 0.99: match = {"side": "YES", "p": p_yes}
                    elif 0.90 <= p_no < 0.99: match = {"side": "NO", "p": p_no}

                    if match:
                        score = (1 / match["p"]) ** (365 / days)
                        if score >= 5:
                            all_results.append({
                                "question": m.get("question"), "slug": m.get("slug"),
                                "side": match["side"], "price": match["p"],
                                "days_left": days, "yield": score, "volume": vol
                            })
                except: continue
        except: break

    all_results.sort(key=lambda x: x["yield"], reverse=True)
    return jsonify(all_results[:200])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
