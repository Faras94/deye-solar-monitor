# Deye Solar Monitoring Application

Full-stack solar monitoring dashboard for 3 Deye microinverters (`260605A076`, `260603A1D5`, `260505A373`) using the **DeyeCloud Developer OpenAPI v1.0** (`https://india-developer.deyecloud.com`).

## Architecture

- **Backend (`backend/`)**: Python, FastAPI, SQLite, SQLAlchemy, Pydantic, APScheduler (5-minute background polling), and a dedicated `DeyeCloudClient` (`app/clients/deye_client.py`) separated from business logic (`app/services/`).
- **Frontend (`frontend/`)**: React, TypeScript, Vite, Tailwind CSS, Recharts, with dark/light theme toggle, 5-minute auto-refresh, individual inverter & PV1–PV4 cards, historical analytics, and measurement mapping configuration.
- **Security**: All DeyeCloud credentials (`DEYE_APP_ID`, `DEYE_APP_SECRET`, `DEYE_EMAIL`, `DEYE_PASSWORD`) stay strictly in backend `.env` and are redacted from logs.

## Quick Start (Streamlit App — Recommended)

1. Ensure `.env` is configured with your DeyeCloud Developer credentials (`DEYE_APP_ID`, `DEYE_APP_SECRET`, `DEYE_EMAIL`, `DEYE_PASSWORD`).
2. Install dependencies and run Streamlit:

```bash
# Install into backend/.venv (if not already installed)
backend/.venv/bin/python -m pip install -r requirements.txt

# Launch the Streamlit dashboard
./start-streamlit.sh
# or: backend/.venv/bin/streamlit run streamlit_app.py
```

On Windows, run `start-streamlit.bat`.

## Quick Start (Legacy FastAPI + React)

1. Copy `.env.example` to `.env` and fill in your DeyeCloud Developer credentials:
   - `DEYE_BASE_URL=https://india-developer.deyecloud.com`
   - `DEYE_APP_ID=...`
   - `DEYE_APP_SECRET=...`
   - `DEYE_EMAIL=...`
   - `DEYE_PASSWORD=...` (the backend hashes it with lowercase SHA-256 automatically)
2. Run `start-dev.ps1` in PowerShell (or run `start-backend.bat` and `start-frontend.bat` separately).
3. Open `http://localhost:5173`.

## Quick Start (macOS / Linux)

```bash
cp .env.example .env
# Edit .env with your DeyeCloud credentials

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

## API Endpoints

- `GET /api/health` — Backend & SQLite health + sync status
- `GET /api/devices` — Configured/discovered microinverters
- `GET /api/live` — Latest live telemetry & PV1–PV4 measurements
- `POST /api/collect` — Trigger manual live collection from DeyeCloud
- `POST /api/discover` — Discover stations, devices, and supported `measurePoints`
- `GET /api/history` — Query stored historical readings (`daily`, `monthly`, `yearly`)
- `POST /api/history/fetch` — Fetch historical readings from DeyeCloud into SQLite
- `GET /api/mappings` — List field mappings, discovered points, and unmapped points
- `POST /api/mappings` — Update DeyeCloud key-to-dashboard field mappings

## Running Tests

```bash
cd backend
.venv/bin/pytest -v
```
