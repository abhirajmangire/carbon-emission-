# Energy Efficiency & Carbon Emissions API

Flask backend for bill ingestion, energy usage summaries, current-month report, trend analysis, predictions, and efficiency advice.

## Quickstart (Flask)

1. Create and activate a virtual environment (Windows PowerShell):
```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
```

2. Install dependencies:
```powershell
pip install -r energy_backend/requirements.txt
```

3. Run the Flask server:
```powershell
python energy_backend/flask_app.py
```

4. Health check: `http://localhost:8000/health`

### Environment settings (optional)
- Create `.env` in project root (same folder where you run `python energy_backend/flask_app.py`):
```
DATA_PATH=energy_backend_data.json
CORS_ALLOW_ORIGINS=["*"]
```

## API Overview

- POST `/api/v1/bills/` — add a bill
- GET `/api/v1/bills/` — list bills
- GET `/api/v1/usage/recent?limit=6` — recent usage points
- GET `/api/v1/summary/` — aggregate summary
- GET `/api/v1/current-month/` — current month report
- GET `/api/v1/analysis/trends` — trend analysis
- GET `/api/v1/analysis/predict?horizon_months=3` — usage prediction
- GET `/api/v1/advice/` — efficiency advice

### Bill payload example
```json
{
  "year": 2025,
  "month": 9,
  "kilowatt_hours": 320.5,
  "cost": 185.75,
  "emission_factor_kg_per_kwh": 0.7
}
```

Notes:
- Emissions are estimated as `kWh * emission_factor_kg_per_kwh`.
- Storage is in-memory for demo; replace `InMemoryStorage` with a database for persistence.

## Docker (Flask)

Build and run:
```powershell
docker build -t energy-api -f energy_backend/Dockerfile .
docker run --rm -p 8000:8000 -v ${PWD}\energy_backend_data.json:/app/energy_backend_data.json energy-api
```

## Frontend

Static UI lives in `energy_frontend/`. Open `energy_frontend/index.html` in your browser.
If your backend runs on a different host/port, edit `energy_frontend/config.js` and change `baseUrl`.

### Auth (demo)
- Sign in on the frontend to obtain a bearer token (`/auth/login`).
- Creating a bill requires the `Authorization: Bearer <token>` header; reads are public.

### Charts
- Trends and predictions are visualized using Chart.js on the Analysis page.
