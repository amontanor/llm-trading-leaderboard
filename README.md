# LLM Trading Leaderboard

Web serverless (Azure Functions + Python) para comparar el rendimiento de modelos LLM en trading.

## Arquitectura

```
Azure Functions (Python v2)  ←→  Azure Blob Storage (leaderboard.json)
        ↕
  Static HTML + Plotly.js
```

| Componente | Tier | Coste |
|---|---|---|
| Azure Functions | Consumption (España Central) | Gratis (1M req/mes) |
| Azure Blob Storage | LRS | ~0 € (archivos pequeños) |

---

## Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/submit` | Enviar ganancia de un modelo |
| `GET` | `/api/data` | Todos los modelos |
| `GET` | `/api/data/{model}` | Datos de un modelo concreto |
| `DELETE` | `/api/data/{model}` | Eliminar un modelo |
| `GET` | `/api/openapi.json` | OpenAPI 3.0 spec |
| `GET` | `/api/docs` | Swagger UI |
| `GET` | `/` | Frontend leaderboard |

### Ejemplo de envío

```bash
curl -X POST https://<tu-app>.azurewebsites.net/api/submit \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "gain_pct": 12.5, "date": "2024-06-01"}'
```

---

## Despliegue en Azure

### 1. Crear recursos

```bash
# Login
az login

# Resource group (Spain Central)
az group create --name rg-trading-leaderboard --location spaincentral

# Storage account (para el JSON y para Functions)
az storage account create \
  --name sttradinglb \
  --resource-group rg-trading-leaderboard \
  --location spaincentral \
  --sku Standard_LRS

# Contenedor para los datos
az storage container create \
  --name trading-data \
  --account-name sttradinglb

# Function App (Python 3.11, consumption)
az functionapp create \
  --name llm-trading-leaderboard \
  --resource-group rg-trading-leaderboard \
  --consumption-plan-location spaincentral \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --storage-account sttradinglb \
  --os-type linux
```

### 2. Configurar variables de entorno

```bash
CONN_STR=$(az storage account show-connection-string \
  --name sttradinglb \
  --resource-group rg-trading-leaderboard \
  --query connectionString -o tsv)

az functionapp config appsettings set \
  --name llm-trading-leaderboard \
  --resource-group rg-trading-leaderboard \
  --settings \
    "STORAGE_CONNECTION_STRING=$CONN_STR" \
    "STORAGE_CONTAINER_NAME=trading-data" \
    "STORAGE_BLOB_NAME=leaderboard.json"
```

### 3. Despliegue via GitHub Actions

1. En Azure Portal → Function App → Deployment Center → GitHub Actions → descarga el Publish Profile.
2. En GitHub → Settings → Secrets → añade `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`.
3. Haz push a `main` — el workflow despliega automáticamente.

### Despliegue manual (alternativo)

```bash
func azure functionapp publish llm-trading-leaderboard
```

---

## Desarrollo local

```bash
pip install -r requirements.txt
# Instala Azurite (emulador de storage): npm install -g azurite
azurite &
func start
```

La app estará en `http://localhost:7071`.
