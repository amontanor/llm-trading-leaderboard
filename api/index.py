import json
import os
from datetime import datetime, date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

from upstash_redis import Redis

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LLM Trading Leaderboard API",
    description="API para registrar y consultar el rendimiento de modelos LLM en trading.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Storage (Upstash Redis via Vercel KV)
# ---------------------------------------------------------------------------

REDIS_KEY = "leaderboard"


def get_redis() -> Redis:
    return Redis(
        url=os.environ["KV_REST_API_URL"],
        token=os.environ["KV_REST_API_TOKEN"],
    )


def load_data() -> dict:
    try:
        r = get_redis()
        raw = r.get(REDIS_KEY)
        if raw is None:
            return {"models": {}}
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {"models": {}}


def save_data(data: dict) -> None:
    r = get_redis()
    r.set(REDIS_KEY, json.dumps(data))


# ---------------------------------------------------------------------------
# Frontend (HTML embebido para evitar problemas de rutas en Vercel)
# ---------------------------------------------------------------------------

FRONTEND_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>LLM Trading Leaderboard</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    :root {
      --bg: #0f1117;
      --surface: #1a1d27;
      --border: #2a2d3e;
      --accent: #6c63ff;
      --accent2: #00d4aa;
      --text: #e2e8f0;
      --muted: #8892a4;
      --positive: #22c55e;
      --negative: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; min-height: 100vh; }
    header { border-bottom: 1px solid var(--border); padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.4rem; font-weight: 700; background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    header .badge { font-size: 0.7rem; background: var(--accent); color: #fff; padding: 2px 8px; border-radius: 999px; font-weight: 600; }
    header .spacer { flex: 1; }
    header a { font-size: 0.8rem; color: var(--muted); text-decoration: none; border: 1px solid var(--border); padding: 4px 12px; border-radius: 6px; transition: all 0.2s; }
    header a:hover { color: var(--text); border-color: var(--accent); }
    main { padding: 2rem; max-width: 1400px; margin: 0 auto; }
    .controls { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
    .controls label { font-size: 0.85rem; color: var(--muted); }
    .controls select { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 6px 32px 6px 12px; font-size: 0.9rem; cursor: pointer; appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%238892a4' viewBox='0 0 16 16'%3E%3Cpath d='M7.247 11.14L2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 10px center; min-width: 180px; }
    .refresh-btn { margin-left: auto; background: var(--surface); border: 1px solid var(--border); color: var(--muted); border-radius: 8px; padding: 6px 14px; font-size: 0.85rem; cursor: pointer; transition: all 0.2s; }
    .refresh-btn:hover { color: var(--text); border-color: var(--accent); }
    .chart-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem 1rem 1rem; margin-bottom: 2rem; }
    #chart { width: 100%; height: 480px; }
    .leaderboard h2 { font-size: 1rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 1rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    thead th { text-align: left; padding: 0.6rem 1rem; color: var(--muted); font-weight: 500; border-bottom: 1px solid var(--border); }
    tbody tr { border-bottom: 1px solid var(--border); transition: background 0.15s; }
    tbody tr:hover { background: rgba(108,99,255,0.05); }
    tbody td { padding: 0.75rem 1rem; }
    .rank { color: var(--muted); font-weight: 600; width: 50px; }
    .model-name { font-weight: 600; }
    .gain { font-weight: 700; }
    .gain.pos { color: var(--positive); }
    .gain.neg { color: var(--negative); }
    .entries { color: var(--muted); }
    .empty { text-align: center; padding: 4rem; color: var(--muted); font-size: 0.95rem; }
    .empty code { display: block; margin-top: 0.75rem; background: var(--surface); border: 1px solid var(--border); padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.8rem; color: var(--accent2); max-width: 480px; margin: 0.75rem auto 0; }
  </style>
</head>
<body>
<header>
  <h1>LLM Trading Leaderboard</h1>
  <span class="badge">LIVE</span>
  <span class="spacer"></span>
  <a href="/docs">API Docs</a>
</header>
<main>
  <div class="controls">
    <label for="modelFilter">Modelo:</label>
    <select id="modelFilter"><option value="all">Todos los modelos</option></select>
    <button class="refresh-btn" onclick="fetchData()">↻ Actualizar</button>
  </div>
  <div class="chart-card"><div id="chart"></div></div>
  <div class="leaderboard">
    <h2>Clasificación</h2>
    <div id="tableContainer"></div>
  </div>
</main>
<script>
  const COLORS = ['#6c63ff','#00d4aa','#f59e0b','#ef4444','#3b82f6','#ec4899','#10b981','#f97316','#8b5cf6','#06b6d4'];
  let allData = {}, colorMap = {};

  async function fetchData() {
    try {
      const res = await fetch('/api/data');
      const json = await res.json();
      allData = json.models || {};
      Object.keys(allData).forEach((m, i) => { if (!colorMap[m]) colorMap[m] = COLORS[i % COLORS.length]; });
      const sel = document.getElementById('modelFilter');
      const cur = sel.value;
      sel.innerHTML = '<option value="all">Todos los modelos</option>';
      Object.keys(allData).sort().forEach(m => { const o = document.createElement('option'); o.value = o.textContent = m; sel.appendChild(o); });
      if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
      render();
    } catch(e) { console.error(e); }
  }

  function render() {
    const val = document.getElementById('modelFilter').value;
    const models = val === 'all' ? allData : (val in allData ? {[val]: allData[val]} : {});
    const traces = Object.entries(models).map(([name, entries]) => ({
      x: entries.map(e => e.date), y: entries.map(e => e.gain_pct),
      mode: 'lines+markers', name,
      line: { color: colorMap[name], width: 2.5 }, marker: { size: 5 },
      hovertemplate: '<b>%{fullData.name}</b><br>%{x}<br><b>%{y:.2f}%</b><extra></extra>',
    }));
    const layout = {
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      font: { color: '#e2e8f0', family: 'Inter, system-ui' },
      margin: { t: 20, b: 60, l: 60, r: 20 },
      xaxis: { gridcolor: '#2a2d3e', linecolor: '#2a2d3e', zeroline: false },
      yaxis: { gridcolor: '#2a2d3e', linecolor: '#2a2d3e', zeroline: true, zerolinecolor: '#4a5568', ticksuffix: '%' },
      legend: { bgcolor: 'rgba(26,29,39,0.8)', bordercolor: '#2a2d3e', borderwidth: 1, x: 0.01, y: 0.99 },
      hovermode: 'x unified',
    };
    Plotly.react('chart', traces.length ? traces : [{x:[],y:[],mode:'lines',line:{color:'transparent'},showlegend:false}], layout, {responsive:true,displayModeBar:false});

    const container = document.getElementById('tableContainer');
    const entries = Object.entries(models);
    if (!entries.length) {
      container.innerHTML = '<div class="empty">No hay datos aún. Envía resultados a la API:<code>POST /api/submit  {"model":"gpt-4o","gain_pct":12.5,"date":"2024-06-01"}</code></div>';
      return;
    }
    const ranked = entries.map(([name, data]) => ({ name, gain: (data[data.length-1]||{gain_pct:0}).gain_pct, count: data.length })).sort((a,b) => b.gain - a.gain);
    container.innerHTML = '<table><thead><tr><th>Pos.</th><th>Modelo</th><th>Ganancia acum.</th><th>Datos</th></tr></thead><tbody>' +
      ranked.map((m,i) => `<tr><td class="rank">#${i+1}</td><td class="model-name"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${colorMap[m.name]};margin-right:8px;vertical-align:middle"></span>${m.name}</td><td class="gain ${m.gain>=0?'pos':'neg'}">${m.gain>=0?'+':''}${m.gain.toFixed(2)}%</td><td class="entries">${m.count} registros</td></tr>`).join('') +
      '</tbody></table>';
  }

  document.getElementById('modelFilter').addEventListener('change', render);
  fetchData();
  setInterval(fetchData, 30000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    return FRONTEND_HTML


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SubmitRequest(BaseModel):
    model: str
    gain_pct: float
    date: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/submit", status_code=201, summary="Enviar ganancia de un modelo")
async def submit(body: SubmitRequest):
    """
    Registra el porcentaje de ganancia **acumulada** de un modelo para una fecha concreta.

    - **model**: nombre del modelo LLM (ej. `gpt-4o`)
    - **gain_pct**: ganancia acumulada en % desde el día 1
    - **date**: fecha en formato `YYYY-MM-DD` (opcional, por defecto hoy)
    """
    entry_date = body.date or date.today().isoformat()
    try:
        datetime.strptime(entry_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="'date' debe tener formato YYYY-MM-DD")

    model = body.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail="'model' no puede estar vacío")

    data = load_data()
    if model not in data["models"]:
        data["models"][model] = []

    entries = data["models"][model]
    for entry in entries:
        if entry["date"] == entry_date:
            entry["gain_pct"] = body.gain_pct
            break
    else:
        entries.append({"date": entry_date, "gain_pct": body.gain_pct})

    data["models"][model] = sorted(entries, key=lambda e: e["date"])
    save_data(data)
    return {"message": "OK", "model": model, "date": entry_date, "gain_pct": body.gain_pct}


@app.get("/api/data", summary="Obtener todos los modelos")
async def get_data():
    """Devuelve el historial completo de todos los modelos."""
    return load_data()


@app.get("/api/data/{model}", summary="Obtener datos de un modelo")
async def get_model_data(model: str):
    """Devuelve el historial de ganancias de un modelo concreto."""
    data = load_data()
    if model not in data["models"]:
        raise HTTPException(status_code=404, detail=f"Modelo '{model}' no encontrado")
    return {"model": model, "entries": data["models"][model]}


@app.delete("/api/data/{model}", summary="Eliminar un modelo")
async def delete_model(model: str):
    """Elimina todos los datos de un modelo."""
    data = load_data()
    if model not in data["models"]:
        raise HTTPException(status_code=404, detail=f"Modelo '{model}' no encontrado")
    del data["models"][model]
    save_data(data)
    return {"message": f"Modelo '{model}' eliminado"}
