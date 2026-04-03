from flask import Flask, jsonify, render_template_string, request
import requests
from datetime import datetime, timezone
import json
import time

app = Flask(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Yield Hunter Ultra-Deep 25k</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#020617] text-slate-200 p-4 md:p-8 font-sans">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-between items-center mb-8 bg-slate-900/40 p-6 rounded-3xl border border-blue-500/10 shadow-2xl backdrop-blur-md">
                <div>
                    <h1 class="text-3xl font-black text-white tracking-tighter italic">🌌 ULTRA-DEEP <span class="text-blue-500" id="scan-count">0</span></h1>
                    <p class="text-slate-500 text-[10px] mt-1 uppercase tracking-[0.3em] font-black">Full Database Scan | Yield > 5 | Vol > $1k</p>
                </div>
                <div id="progress" class="text-blue-400 font-mono text-xs bg-blue-500/5 px-6 py-2 rounded-2xl border border-blue-500/20">
                    Initialisation...
                </div>
            </div>
            
            <div class="bg-slate-900/60 rounded-3xl overflow-hidden border border-white/5 shadow-2xl">
                <table class="w-full text-left border-collapse text-[11px] md:text-xs">
                    <thead class="bg-blue-600/5 text-slate-500 uppercase font-black tracking-widest text-[9px]">
                        <tr>
                            <th class="p-5">Marché</th>
                            <th class="p-5 text-center">Côté</th>
                            <th class="p-4 text-right">Volume</th>
                            <th class="p-4 text-right">Prix</th>
                            <th class="p-4 text-right">Temps</th>
                            <th class="p-5 text-right text-blue-400">Yield Score</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-white/5">
                        </tbody>
                </table>
            </div>
        </div>

        <script>
            let allData = [];
            const tbody = document.getElementById('content');
            const progress = document.getElementById('progress');
            const scanCount = document.getElementById('scan-count');

            async function startUltraScan() {
                // 25 blocs de 1000 = 25,000 marchés
                const totalBlocks = 25;
                
                for (let i = 0; i < totalBlocks; i++) {
                    const offset = i * 1000;
                    progress.innerText = `SCANNING BLOCK ${i+1}/${totalBlocks}...`;
                    scanCount.innerText = (offset + 1000).toLocaleString();

                    try {
                        const res = await fetch(`/api/scan?offset=${offset}`);
                        const chunk = await res.json();
                        
                        if (chunk && chunk.length > 0) {
                            // Fusion intelligente sans doublons
                            chunk.forEach(item => {
                                if(!allData.find(x => x.slug === item.slug)) {
                                    allData.push(item);
                                }
                            });
                            
                            // Tri par Yield décroissant
                            allData.sort((a, b) => b.yield - a.yield);
                            renderTable();
                        }
                    } catch (e) {
                        console.error("Erreur sur bloc " + i);
                    }
                    
                    // Petite pause pour laisser le navigateur respirer
                    if (i % 5 === 0) await new Promise(r => setTimeout(r, 200));
                }
                progress.innerText = "SCAN COMPLET (25k)";
                progress.classList.replace('text-blue-400', 'text-green-400');
                progress.style.borderColor = "rgba(74, 222, 128, 0.3)";
            }

            function renderTable() {
                tbody.innerHTML = allData.map(m => `
                    <tr class="hover:bg-blue-500/[0.03] transition-colors group">
                        <td class="p-5 font-bold text-slate-300">
                            <a href="https://polymarket.com/market/${m.slug}" target="_blank" class="hover:text-blue-400 transition-colors">${m.question}</a>
                        </td>
                        <td class="p-5 text-center">
                            <span class="bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-[9px] font-black group-hover:border-blue-500/30 transition-colors">${m.side}</span>
                        </td>
                        <td class="p-4 text-right text-slate-500 font-mono italic">$${(m.volume/1000).toFixed(1)}k</td>
                        <td class="p-4 text-right font-mono text-slate-400">${m.price.toFixed(3)}</td>
                        <td class="p-4 text-right font-mono text-orange-400/80 font-bold">${m.days_left.toFixed(2)}j</td>
                        <td class="p-5 text-right font-mono text-blue-400 text-sm font-black italic underline decoration-blue-500/20">${m.yield.toFixed(2)}</td>
                    </tr>`).join('');
            }

            startUltraScan();
        </script>
    </body>
    </html>
    """)

@app.route("/api/scan")
def scan_chunk():
    offset = request.args.get('offset', default=0, type=int)
    all_results = []
    now = datetime.now(timezone.utc)
    
    try:
        # On utilise une session pour stabiliser les requêtes répétitives
        with requests.Session() as s:
            params = {
                "active": "true",
                "closed": "false",
                "limit": 1000,
                "offset": offset,
                "order": "volume",
                "ascending": "false"
            }
            r = s.get(f"{GAMMA_BASE}/markets", params=params, timeout=15)
            markets = r.json()

            for m in markets:
                try:
                    vol = float(m.get("volume", 0) or 0)
                    if vol < 1000: continue

                    end_date_str = m.get("endDate") or m.get("end_date_iso")
                    if not end_date_str: continue
                    end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    days = (end_dt - now).total_seconds() / 86400
                    
                    # On élargit un peu la fenêtre temporelle pour le scan profond
                    if days <= 0.5 or days > 60: continue

                    p_raw = m.get("outcomePrices")
                    if not p_raw: continue
                    prices = json.loads(p_raw)
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
        return jsonify(all_results)
    except:
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
