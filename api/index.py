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
# Storage (Vercel KV / Upstash Redis)
# ---------------------------------------------------------------------------

REDIS_KEY = "leaderboard"

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "..", "public", "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Frontend not found")

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
# Schemas
# ---------------------------------------------------------------------------

class SubmitRequest(BaseModel):
    model: str
    gain_pct: float
    date: Optional[str] = None  # YYYY-MM-DD, default today


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
