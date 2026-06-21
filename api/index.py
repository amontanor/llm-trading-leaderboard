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
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #f0f2f8;
      --surface: #ffffff;
      --border: #e8eaf0;
      --accent: #5b5bd6;
      --accent2: #00c9a7;
      --accent3: #ff6b6b;
      --text: #1a1d2e;
      --muted: #8b8fa8;
      --positive: #00b37e;
      --negative: #e54d2e;
      --shadow: 0 2px 12px rgba(91,91,214,0.08);
      --shadow-lg: 0 8px 32px rgba(91,91,214,0.12);
    }
    body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; min-height: 100vh; }

    /* HEADER */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0 2rem;
      height: 64px;
      display: flex;
      align-items: center;
      gap: 1rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      position: sticky; top: 0; z-index: 10;
    }
    .logo { display: flex; align-items: center; gap: 10px; }
    .logo-icon {
      width: 36px; height: 36px; border-radius: 10px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      display: flex; align-items: center; justify-content: center;
      font-size: 1.1rem;
    }
    .logo h1 { font-size: 1.05rem; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
    .logo h1 span { color: var(--accent); }
    .badge-live {
      font-size: 0.65rem; font-weight: 700; letter-spacing: 0.06em;
      background: #dcfce7; color: #15803d;
      padding: 2px 8px; border-radius: 999px;
      border: 1px solid #bbf7d0;
    }
    .spacer { flex: 1; }
    .header-actions { display: flex; align-items: center; gap: 0.75rem; }
    .btn-ghost {
      font-size: 0.82rem; font-weight: 500; color: var(--muted);
      text-decoration: none; padding: 6px 14px; border-radius: 8px;
      border: 1px solid var(--border); background: transparent;
      cursor: pointer; transition: all 0.15s;
    }
    .btn-ghost:hover { color: var(--accent); border-color: var(--accent); background: #f0f0ff; }
    .btn-primary {
      font-size: 0.82rem; font-weight: 600; color: #fff;
      padding: 6px 16px; border-radius: 8px;
      border: none; background: var(--accent);
      cursor: pointer; transition: all 0.15s;
    }
    .btn-primary:hover { background: #4a4abf; }

    /* MAIN */
    main { padding: 2rem; max-width: 1400px; margin: 0 auto; }

    /* KPI CARDS */
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 1.75rem; }
    .kpi-card {
      background: var(--surface); border-radius: 14px;
      padding: 1.25rem 1.5rem; box-shadow: var(--shadow);
      border: 1px solid var(--border);
      display: flex; flex-direction: column; gap: 0.35rem;
    }
    .kpi-label { font-size: 0.78rem; font-weight: 500; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi-value { font-size: 1.75rem; font-weight: 700; color: var(--text); letter-spacing: -0.03em; }
    .kpi-sub { font-size: 0.8rem; font-weight: 500; }
    .kpi-sub.pos { color: var(--positive); }
    .kpi-sub.neg { color: var(--negative); }
    .kpi-sub.neu { color: var(--muted); }
    .kpi-bar { height: 3px; border-radius: 99px; background: var(--border); margin-top: 0.5rem; overflow: hidden; }
    .kpi-bar-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--accent), var(--accent2)); transition: width 0.6s ease; }

    /* CHART CARD */
    .chart-section { background: var(--surface); border-radius: 16px; box-shadow: var(--shadow); border: 1px solid var(--border); margin-bottom: 1.75rem; overflow: hidden; }
    .chart-header { padding: 1.25rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
    .chart-title { font-size: 0.95rem; font-weight: 600; color: var(--text); }
    .chart-subtitle { font-size: 0.8rem; color: var(--muted); margin-top: 1px; }
    .chart-controls { margin-left: auto; display: flex; align-items: center; gap: 0.75rem; }
    .select-wrap { position: relative; }
    .select-wrap select {
      appearance: none; background: var(--bg); color: var(--text);
      border: 1px solid var(--border); border-radius: 8px;
      padding: 6px 30px 6px 12px; font-size: 0.82rem; font-family: inherit;
      cursor: pointer; outline: none;
    }
    .select-wrap::after {
      content: '▾'; position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
      color: var(--muted); pointer-events: none; font-size: 0.75rem;
    }
    #chart { width: 100%; height: 400px; }

    /* TABLE */
    .table-section { background: var(--surface); border-radius: 16px; box-shadow: var(--shadow); border: 1px solid var(--border); overflow: hidden; }
    .table-header { padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; }
    .table-header h2 { font-size: 0.95rem; font-weight: 600; color: var(--text); }
    table { width: 100%; border-collapse: collapse; }
    thead th { padding: 0.75rem 1.5rem; text-align: left; font-size: 0.75rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; background: #fafbfe; border-bottom: 1px solid var(--border); }
    tbody tr { transition: background 0.12s; }
    tbody tr:not(:last-child) { border-bottom: 1px solid var(--border); }
    tbody tr:hover { background: #f7f8ff; }
    tbody td { padding: 1rem 1.5rem; font-size: 0.88rem; }
    .rank-badge {
      display: inline-flex; align-items: center; justify-content: center;
      width: 28px; height: 28px; border-radius: 8px;
      font-size: 0.78rem; font-weight: 700;
    }
    .rank-1 { background: #fef9c3; color: #a16207; }
    .rank-2 { background: #f1f5f9; color: #475569; }
    .rank-3 { background: #fff7ed; color: #c2410c; }
    .rank-n { background: var(--bg); color: var(--muted); }
    .model-cell { display: flex; align-items: center; gap: 10px; }
    .model-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .model-name { font-weight: 600; color: var(--text); }
    .gain-pill {
      display: inline-block; padding: 3px 10px; border-radius: 999px;
      font-size: 0.82rem; font-weight: 700;
    }
    .gain-pill.pos { background: #dcfce7; color: #15803d; }
    .gain-pill.neg { background: #fee2e2; color: #b91c1c; }
    .entries-cell { color: var(--muted); font-size: 0.82rem; }
    .empty { text-align: center; padding: 4rem 2rem; color: var(--muted); }
    .empty-icon { font-size: 2.5rem; margin-bottom: 1rem; }
    .empty p { margin-bottom: 0.5rem; font-size: 0.9rem; }
    .empty code { display: inline-block; margin-top: 0.75rem; background: var(--bg); border: 1px solid var(--border); padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.78rem; color: var(--accent); }
  </style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">📈</div>
    <div>
      <h1>LLM <span>Trading</span> Leaderboard</h1>
    </div>
  </div>
  <span class="badge-live">● LIVE</span>
  <div class="spacer"></div>
  <div class="header-actions">
    <a href="/docs" class="btn-ghost">API Docs</a>
    <button class="btn-primary" onclick="fetchData()">↻ Actualizar</button>
  </div>
</header>

<main>
  <!-- KPI CARDS -->
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Modelos activos</div>
      <div class="kpi-value" id="kpi-models">—</div>
      <div class="kpi-sub neu" id="kpi-models-sub">cargando...</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Mejor rendimiento</div>
      <div class="kpi-value" id="kpi-best-val">—</div>
      <div class="kpi-sub pos" id="kpi-best-name"> </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Peor rendimiento</div>
      <div class="kpi-value" id="kpi-worst-val">—</div>
      <div class="kpi-sub neg" id="kpi-worst-name"> </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Total registros</div>
      <div class="kpi-value" id="kpi-records">—</div>
      <div class="kpi-sub neu">entradas de datos</div>
    </div>
  </div>

  <!-- CHART -->
  <div class="chart-section">
    <div class="chart-header">
      <div>
        <div class="chart-title">Evolución de ganancias acumuladas</div>
        <div class="chart-subtitle">Porcentaje desde el inicio de la competición</div>
      </div>
      <div class="chart-controls">
        <div class="select-wrap">
          <select id="modelFilter">
            <option value="all">Todos los modelos</option>
          </select>
        </div>
      </div>
    </div>
    <div id="chart"></div>
  </div>

  <!-- TABLE -->
  <div class="table-section">
    <div class="table-header">
      <h2>Clasificación general</h2>
    </div>
    <div id="tableContainer"></div>
  </div>
</main>

<script>
  const COLORS = ['#5b5bd6','#00c9a7','#f59e0b','#ff6b6b','#3b82f6','#ec4899','#10b981','#f97316','#8b5cf6','#06b6d4'];
  let allData = {}, colorMap = {};

  async function fetchData() {
    try {
      const res = await fetch('/api/data');
      const json = await res.json();
      allData = json.models || {};
      let i = 0;
      Object.keys(allData).forEach(m => { if (!colorMap[m]) colorMap[m] = COLORS[i++ % COLORS.length]; });
      updateKPIs();
      updateFilter();
      render();
    } catch(e) { console.error(e); }
  }

  function updateKPIs() {
    const models = Object.entries(allData);
    document.getElementById('kpi-models').textContent = models.length || '0';
    document.getElementById('kpi-models-sub').textContent = models.length === 1 ? '1 competidor' : `${models.length} competidores`;

    let totalRecords = 0;
    const ranked = models.map(([name, entries]) => {
      totalRecords += entries.length;
      const last = entries[entries.length - 1];
      return { name, gain: last ? last.gain_pct : 0 };
    }).sort((a, b) => b.gain - a.gain);

    document.getElementById('kpi-records').textContent = totalRecords || '—';

    if (ranked.length) {
      const best = ranked[0], worst = ranked[ranked.length - 1];
      document.getElementById('kpi-best-val').textContent = (best.gain >= 0 ? '+' : '') + best.gain.toFixed(2) + '%';
      document.getElementById('kpi-best-name').textContent = best.name;
      document.getElementById('kpi-worst-val').textContent = (worst.gain >= 0 ? '+' : '') + worst.gain.toFixed(2) + '%';
      document.getElementById('kpi-worst-name').textContent = worst.name;
    } else {
      ['kpi-best-val','kpi-worst-val'].forEach(id => document.getElementById(id).textContent = '—');
    }
  }

  function updateFilter() {
    const sel = document.getElementById('modelFilter');
    const cur = sel.value;
    sel.innerHTML = '<option value="all">Todos los modelos</option>';
    Object.keys(allData).sort().forEach(m => {
      const o = document.createElement('option');
      o.value = o.textContent = m;
      sel.appendChild(o);
    });
    if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
  }

  function getFiltered() {
    const val = document.getElementById('modelFilter').value;
    return val === 'all' ? allData : (val in allData ? {[val]: allData[val]} : {});
  }

  function render() {
    const models = getFiltered();
    // Chart
    const traces = Object.entries(models).map(([name, entries]) => ({
      x: entries.map(e => e.date),
      y: entries.map(e => e.gain_pct),
      mode: 'lines+markers', name,
      line: { color: colorMap[name], width: 2.5, shape: 'spline' },
      marker: { size: 6, color: colorMap[name], line: { color: '#fff', width: 1.5 } },
      fill: Object.keys(models).length === 1 ? 'tozeroy' : 'none',
      fillcolor: Object.keys(models).length === 1 ? colorMap[name].replace(')', ',0.08)').replace('rgb','rgba') : 'transparent',
      hovertemplate: '<b>%{fullData.name}</b><br>%{x}<br><b>%{y:.2f}%</b><extra></extra>',
    }));

    const layout = {
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      font: { color: '#8b8fa8', family: 'Inter, system-ui', size: 12 },
      margin: { t: 20, b: 50, l: 55, r: 20 },
      xaxis: {
        gridcolor: '#e8eaf0', linecolor: '#e8eaf0', zeroline: false,
        tickfont: { size: 11 },
      },
      yaxis: {
        gridcolor: '#e8eaf0', linecolor: '#e8eaf0',
        zeroline: true, zerolinecolor: '#c8cadb', zerolinewidth: 1.5,
        ticksuffix: '%', tickfont: { size: 11 },
      },
      legend: {
        bgcolor: 'rgba(255,255,255,0.9)', bordercolor: '#e8eaf0', borderwidth: 1,
        x: 0.01, y: 0.99, xanchor: 'left', yanchor: 'top',
        font: { size: 12, color: '#1a1d2e' },
      },
      hovermode: 'x unified',
      hoverlabel: { bgcolor: '#fff', bordercolor: '#e8eaf0', font: { color: '#1a1d2e', size: 12 } },
    };

    Plotly.react('chart',
      traces.length ? traces : [{x:[],y:[],mode:'lines',line:{color:'transparent'},showlegend:false}],
      layout, { responsive: true, displayModeBar: false }
    );

    // Table
    const container = document.getElementById('tableContainer');
    const entries = Object.entries(models);
    if (!entries.length) {
      container.innerHTML = `<div class="empty">
        <div class="empty-icon">📭</div>
        <p>No hay datos aún.</p>
        <p>Envía el primer resultado a la API:</p>
        <code>POST /api/submit  {"model":"gpt-4o","gain_pct":12.5,"date":"2024-06-01"}</code>
      </div>`;
      return;
    }
    const ranked = entries.map(([name, data]) => ({
      name, gain: (data[data.length-1]||{gain_pct:0}).gain_pct, count: data.length
    })).sort((a,b) => b.gain - a.gain);

    const rankClass = i => i===0?'rank-1':i===1?'rank-2':i===2?'rank-3':'rank-n';
    const rankLabel = i => i===0?'🥇':i===1?'🥈':i===2?'🥉':`#${i+1}`;

    container.innerHTML = `<table>
      <thead><tr>
        <th>Pos.</th><th>Modelo</th><th>Ganancia acum.</th><th>Registros</th>
      </tr></thead>
      <tbody>${ranked.map((m,i) => `<tr>
        <td><span class="rank-badge ${rankClass(i)}">${rankLabel(i)}</span></td>
        <td><div class="model-cell"><span class="model-dot" style="background:${colorMap[m.name]}"></span><span class="model-name">${m.name}</span></div></td>
        <td><span class="gain-pill ${m.gain>=0?'pos':'neg'}">${m.gain>=0?'+':''}${m.gain.toFixed(2)}%</span></td>
        <td class="entries-cell">${m.count} entradas</td>
      </tr>`).join('')}</tbody>
    </table>`;
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


@app.delete("/api/data", summary="Borrar todos los datos")
async def delete_all():
    """Elimina todos los modelos y sus datos. Útil para pruebas."""
    save_data({"models": {}})
    return {"message": "Todos los datos eliminados"}


@app.delete("/api/data/{model}", summary="Eliminar un modelo")
async def delete_model(model: str):
    """Elimina todos los datos de un modelo concreto."""
    data = load_data()
    if model not in data["models"]:
        raise HTTPException(status_code=404, detail=f"Modelo '{model}' no encontrado")
    del data["models"][model]
    save_data(data)
    return {"message": f"Modelo '{model}' eliminado"}
