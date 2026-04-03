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
        <title>Yield Hunter Nebula 75k</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: #020617; }
            ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
            .glow-text { text-shadow: 0 0 20px rgba(59, 130, 246, 0.5); }
        </style>
    </head>
    <body class="bg-[#02040a] text-slate-300 p-4 md:p-10 font-sans">
        <div class="max-w-7xl mx-auto">
            <div class="flex flex-col md:flex-row justify-between items-center mb-10 bg-slate-900/20 p-8 rounded-[2.5rem] border border-white/5 shadow-2xl backdrop-blur-3xl">
                <div class="text-center md:text-left">
                    <h1 class="text-4xl font-black text-white tracking-tighter italic glow-text uppercase">🌌 NEBULA-SCAN <span class="text-blue-500" id="scan-count">0</span></h1>
                    <p class="text-slate-500 text-[10px] mt-2 uppercase tracking-[0.4em] font-black opacity-70 italic">
                        Exclus: Temperature, Spread | 0.5j-45j | Limit: 75k
                    </p>
                </div>
                <div class="mt-6 md:mt-0 flex flex-col items-end">
                    <div id="progress" class="text-blue-400 font-mono text-xs bg-blue-500/10 px-8 py-4 rounded-3xl border border-blue-500/20 shadow-lg">
                        Séquence de boot...
                    </div>
                    <div id="match-counter" class="mt-2 text-[10px] font-bold text-slate-600 uppercase tracking-widest">0 opportunités filtrées</div>
                </div>
            </div>
            
            <div class="bg-slate-900/30 rounded-[2.5rem] overflow-hidden border border-white/5 shadow-2xl overflow-x-auto">
                <table class="w-full text-left border-collapse text-[11px] md:text-xs">
                    <thead class="bg-white/[0.01] text-slate-500 uppercase font-black tracking-widest text-[9px]">
                        <tr>
                            <th class="p-6">Marché (Filtré)</th>
                            <th class="p-6 text-center">Côté</th>
                            <th class="p-4 text-right text-slate-400">Volume</th>
                            <th class="p-4 text-right text-slate-400">Prix</th>
                            <th class="p-4 text-right text-orange-500/50">Échéance</th>
                            <th class="p-6 text-right text-blue-500 font-black">Yield</th>
                        </tr>
                    </thead>
                    <tbody id="content" class="divide-y divide-white/[0.02]">
                        </tbody>
                </table>
            </div>
        </div>

        <script>
            let allData = new Map();
            const tbody = document.getElementById('content');
            const progress = document.getElementById('progress');
            const scanCount = document.getElementById('scan-count');
            const matchCounter = document.getElementById('match-counter');

            async function runNebulaScan() {
                const totalBlocks = 75; // 75,000 marchés
                
                for (let i = 0; i < totalBlocks; i++) {
                    const offset = i * 1000;
                    progress.innerText = `EXPLORATION SECTEUR ${i+1}/${totalBlocks}...`;
                    scanCount.innerText = (offset + 1000).toLocaleString();

                    try {
                        const res = await fetch(`/api/scan?offset=${offset}`);
                        const chunk = await res.json();
                        
                        if (chunk && chunk.length > 0) {
                            chunk.forEach(item => allData.set(item.slug, item));
                            
                            const sortedArray = Array.from(allData.values()).sort((a, b) => b.yield - a.yield);
                            matchCounter.innerText = `${sortedArray.length} pépites filtrées`;
                            renderTable(sortedArray);
                        }
                    } catch (e) {
                        console.error("Erreur secteur " + i);
                    }
                    
                    // On laisse souffler le navigateur
                    if (i % 2 === 0) await new Promise(r => setTimeout(r, 80));
                }
                progress.innerText = "EXPLORATION TERMINÉE";
                progress.classList.replace('text-blue-400', 'text-green-400');
            }

            function renderTable(data) {
                tbody.innerHTML = data.map(m => `
                    <tr class="hover:bg-blue-500/[0.04] transition-all duration-300 group">
                        <td class="p-6 font-bold text-slate-300 max-w-lg leading-relaxed">
                            <a href="https://polymarket.com/market/${m.slug}" target="_blank" class="hover:text-blue-400 transition-colors">${m.question}</a>
                        </td>
                        <td class="p-6 text-center">
                            <span class="bg-slate-950 px-3 py-1 rounded-full border border-slate-800 text-[9px] font-black group-hover:border-blue-500/40 uppercase text-slate-500">${m.side}</span>
                        </td>
                        <td class="p-4 text-right text-slate-500 font-mono italic">$${(m.volume/1000).toFixed(1)}k</td>
                        <td class="p-4 text-right font-mono text-slate-400">${m.price.toFixed(3)}</td>
                        <td class="p-4 text-right font-mono text-orange-500/70 font-bold tracking-tighter">${m.days_left.toFixed(2)}j</td>
                        <td class="p-6 text-right font-mono text-blue-500 text-sm font-black italic group-hover:scale-110 transition-transform origin-right leading-none">
                            ${m.yield.toFixed(2)}
                        </td>
                    </tr>`).join('');
            }

            runNebulaScan();
        </script>
    </body>
    </html>
    """)

@app.route("/api/scan")
def scan_chunk():
    offset = request.args.get('offset', default=0, type=int)
    all_results = []
    now = datetime.now(timezone.utc)
    
    # Mots-clés à bannir
    excluded_keywords = ["temperature", "spread"]
    
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        })
        
        params = {
            "active": "true",
            "closed": "false",
            "limit": 1000,
            "offset": offset,
            "order": "volume",
            "ascending": "false"
        }
        r = session.get(f"{GAMMA_BASE}/markets", params=params, timeout=15)
        markets = r.json()

        for m in markets:
            try:
                question = m.get("question", "").lower()
                
                # --- FILTRE D'EXCLUSION ---
                if any(word in question for word in excluded_keywords):
                    continue

                # 1. Filtre Volume $1k
                vol = float(m.get("volume", 0) or 0)
                if vol < 1000: continue

                # 2. Fenêtre de temps [0.5j - 45j]
                end_date_str = m.get("endDate") or m.get("end_date_iso")
                if not end_date_str: continue
                end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                days = (end_dt - now).total_seconds() / 86400
                if days <= 0.5 or days > 45: continue

                # 3. Extraction Prix
                p_raw = m.get("outcomePrices")
                if not p_raw: continue
                prices = json.loads(p_raw)
                if len(prices) < 2: continue
                p_yes, p_no = float(prices[0]), float(prices[1])

                # 4. Calcul Yield [0.90 - 0.99]
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
