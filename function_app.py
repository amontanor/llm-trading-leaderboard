import azure.functions as func
import json
import logging
import os
from datetime import datetime, date
from azure.storage.blob import BlobServiceClient, BlobClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

CONN_STR = os.environ.get("STORAGE_CONNECTION_STRING", "")
CONTAINER = os.environ.get("STORAGE_CONTAINER_NAME", "trading-data")
BLOB_NAME = os.environ.get("STORAGE_BLOB_NAME", "leaderboard.json")

EMPTY_DATA: dict = {"models": {}}


def _get_blob_client() -> BlobClient:
    svc = BlobServiceClient.from_connection_string(CONN_STR)
    container_client = svc.get_container_client(CONTAINER)
    try:
        container_client.create_container()
    except Exception:
        pass  # already exists
    return svc.get_blob_client(CONTAINER, BLOB_NAME)


def load_data() -> dict:
    try:
        blob = _get_blob_client()
        raw = blob.download_blob().readall()
        return json.loads(raw)
    except Exception:
        return dict(EMPTY_DATA)


def save_data(data: dict) -> None:
    blob = _get_blob_client()
    blob.upload_blob(json.dumps(data, indent=2), overwrite=True)


def _json_response(body, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body, ensure_ascii=False),
        status_code=status,
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


def _error(msg: str, status: int = 400) -> func.HttpResponse:
    return _json_response({"error": msg}, status)


# ---------------------------------------------------------------------------
# POST /api/submit
# ---------------------------------------------------------------------------

@app.route(route="submit", methods=["POST", "OPTIONS"])
def submit(req: func.HttpRequest) -> func.HttpResponse:
    """Submit a gain percentage for a model on a given date."""
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )

    try:
        body = req.get_json()
    except ValueError:
        return _error("Body must be valid JSON")

    model: str = body.get("model", "").strip()
    gain_pct = body.get("gain_pct")
    entry_date: str = body.get("date", date.today().isoformat())

    if not model:
        return _error("'model' is required")
    if gain_pct is None:
        return _error("'gain_pct' is required")
    try:
        gain_pct = float(gain_pct)
    except (TypeError, ValueError):
        return _error("'gain_pct' must be a number")

    # Validate date format
    try:
        datetime.strptime(entry_date, "%Y-%m-%d")
    except ValueError:
        return _error("'date' must be in YYYY-MM-DD format")

    data = load_data()
    if model not in data["models"]:
        data["models"][model] = []

    # Update or append entry for this date
    entries = data["models"][model]
    for entry in entries:
        if entry["date"] == entry_date:
            entry["gain_pct"] = gain_pct
            break
    else:
        entries.append({"date": entry_date, "gain_pct": gain_pct})

    # Keep sorted by date
    data["models"][model] = sorted(entries, key=lambda e: e["date"])

    save_data(data)
    logging.info(f"Submitted: model={model}, date={entry_date}, gain_pct={gain_pct}")

    return _json_response(
        {"message": "OK", "model": model, "date": entry_date, "gain_pct": gain_pct},
        status=201,
    )


# ---------------------------------------------------------------------------
# GET /api/data  — all models
# ---------------------------------------------------------------------------

@app.route(route="data", methods=["GET"])
def get_data(req: func.HttpRequest) -> func.HttpResponse:
    """Return all models' historical gain data."""
    data = load_data()
    return _json_response(data)


# ---------------------------------------------------------------------------
# GET /api/data/{model}  — single model
# ---------------------------------------------------------------------------

@app.route(route="data/{model}", methods=["GET"])
def get_model_data(req: func.HttpRequest) -> func.HttpResponse:
    """Return historical gain data for a specific model."""
    model = req.route_params.get("model", "")
    data = load_data()

    if model not in data["models"]:
        return _error(f"Model '{model}' not found", 404)

    return _json_response({"model": model, "entries": data["models"][model]})


# ---------------------------------------------------------------------------
# DELETE /api/data/{model}  — remove a model
# ---------------------------------------------------------------------------

@app.route(route="data/{model}", methods=["DELETE"])
def delete_model(req: func.HttpRequest) -> func.HttpResponse:
    """Delete all data for a model."""
    model = req.route_params.get("model", "")
    data = load_data()

    if model not in data["models"]:
        return _error(f"Model '{model}' not found", 404)

    del data["models"][model]
    save_data(data)
    return _json_response({"message": f"Model '{model}' deleted"})


# ---------------------------------------------------------------------------
# GET /  — frontend
# ---------------------------------------------------------------------------

@app.route(route="", methods=["GET"])
def index(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the leaderboard frontend."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        return func.HttpResponse(html, mimetype="text/html")
    except FileNotFoundError:
        return func.HttpResponse("Frontend not found", status_code=404)


# ---------------------------------------------------------------------------
# GET /docs  — Swagger UI
# ---------------------------------------------------------------------------

@app.route(route="docs", methods=["GET"])
def docs(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the Swagger UI."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "swagger.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        return func.HttpResponse(html, mimetype="text/html")
    except FileNotFoundError:
        return func.HttpResponse("Swagger UI not found", status_code=404)


# ---------------------------------------------------------------------------
# GET /api/openapi.json  — OpenAPI spec
# ---------------------------------------------------------------------------

@app.route(route="openapi.json", methods=["GET"])
def openapi_spec(req: func.HttpRequest) -> func.HttpResponse:
    """Return the OpenAPI 3.0 specification."""
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "LLM Trading Leaderboard API",
            "description": "API para registrar y consultar el rendimiento de modelos LLM en trading.",
            "version": "1.0.0",
        },
        "servers": [{"url": "/api"}],
        "paths": {
            "/submit": {
                "post": {
                    "summary": "Enviar ganancia de un modelo",
                    "description": "Registra el porcentaje de ganancia acumulada de un modelo para una fecha concreta.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SubmitRequest"},
                                "example": {
                                    "model": "gpt-4o",
                                    "gain_pct": 12.5,
                                    "date": "2024-06-01",
                                },
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Datos guardados correctamente",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SubmitResponse"}
                                }
                            },
                        },
                        "400": {"description": "Parámetros inválidos"},
                    },
                    "tags": ["Datos"],
                }
            },
            "/data": {
                "get": {
                    "summary": "Obtener todos los modelos",
                    "description": "Devuelve el historial completo de todos los modelos.",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/AllData"}
                                }
                            },
                        }
                    },
                    "tags": ["Datos"],
                }
            },
            "/data/{model}": {
                "get": {
                    "summary": "Obtener datos de un modelo",
                    "parameters": [
                        {
                            "name": "model",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "example": "gpt-4o",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ModelData"}
                                }
                            },
                        },
                        "404": {"description": "Modelo no encontrado"},
                    },
                    "tags": ["Datos"],
                },
                "delete": {
                    "summary": "Eliminar un modelo",
                    "parameters": [
                        {
                            "name": "model",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Modelo eliminado"},
                        "404": {"description": "Modelo no encontrado"},
                    },
                    "tags": ["Datos"],
                },
            },
        },
        "components": {
            "schemas": {
                "SubmitRequest": {
                    "type": "object",
                    "required": ["model", "gain_pct"],
                    "properties": {
                        "model": {
                            "type": "string",
                            "description": "Nombre del modelo LLM",
                            "example": "gpt-4o",
                        },
                        "gain_pct": {
                            "type": "number",
                            "description": "Ganancia acumulada en % desde el día 1",
                            "example": 12.5,
                        },
                        "date": {
                            "type": "string",
                            "format": "date",
                            "description": "Fecha de la entrada (YYYY-MM-DD). Por defecto: hoy.",
                            "example": "2024-06-01",
                        },
                    },
                },
                "SubmitResponse": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "model": {"type": "string"},
                        "date": {"type": "string"},
                        "gain_pct": {"type": "number"},
                    },
                },
                "Entry": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "format": "date"},
                        "gain_pct": {"type": "number"},
                    },
                },
                "ModelData": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "entries": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Entry"},
                        },
                    },
                },
                "AllData": {
                    "type": "object",
                    "properties": {
                        "models": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Entry"},
                            },
                        }
                    },
                },
            }
        },
    }
    return _json_response(spec)
