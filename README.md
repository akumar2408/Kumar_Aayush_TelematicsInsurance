# Telematics Insurance – POC+

**Repo:** [https://github.com/akumar2408/Kumar\_Aayush\_TelematicsInsurance](https://github.com/akumar2408/Kumar_Aayush_TelematicsInsurance)

A hands-on prototype of a telematics-driven auto-insurance stack:

* FastAPI backend for **telemetry ingest → trip summarization → risk scoring → pricing**
* Transparent **rules model** + optional **ML baseline** (Random Forest)
* Streamlit **driver dashboard** with score explainability, recent trips, gamification & coaching
* Simple **API-key auth**, clean data schemas, easy local run or Docker

---

## 1) Quick Start (Local, Python)

> Tested with Python 3.11 on macOS. Everything runs locally—no external services.

### A. Clone & setup

```bash
git clone https://github.com/akumar2408/Kumar_Aayush_TelematicsInsurance.git
cd Kumar_Aayush_TelematicsInsurance

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### B. Configure env

Create a `.env` in the repo root (or copy from `.env.example`) with:

```
API_KEY=changeme
DB_URL=sqlite:///./data/telematics.db
USE_ML=true
```

> To **reset to a blank system**, delete the local DB:

```bash
rm -f data/telematics.db
```

### C. Start the API

```bash
# start with the venv's interpreter (avoids sklearn import issues)
python -m uvicorn src.backend.api.app:app --port 8000
```

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → `{"status":"ok"}`

### D. Simulate telemetry (ingest trips)

Open a **second terminal** in the project root:

```bash
source .venv/bin/activate
export API_KEY=changeme
python bin/generate_data.py --days 3 --driver-id D001
```

### E. Open the dashboard

```bash
streamlit run src/dashboard/dashboard.py --server.port 8501
```

Dashboard: [http://127.0.0.1:8501](http://127.0.0.1:8501)
Use driver id `D001`, click **Refresh Score & Premium**.

---

## 2) Optional: Docker Compose

1. Ensure Docker Desktop is running.

2. Create `.env` in repo root (same keys as above).

3. Build & run:

   ```bash
   docker compose up --build
   ```

   * API: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
   * Dashboard: [http://127.0.0.1:8501](http://127.0.0.1:8501)

4. Simulate data from host:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   export API_KEY=changeme
   python bin/generate_data.py --days 3 --driver-id D001
   ```

Stop:

```bash
docker compose down
```

---

## 3) Evaluate the System

**Pipeline**

* `POST /ingest/telemetry` → trip features:

  * `distance_km, avg_speed, max_speed, harsh_brakes, night_ratio, speeding_events, centroid`

**Risk Scoring**

* **Rules model** (deterministic, interpretable).
* **ML baseline** (toggle with `USE_ML=true`): `RandomForestRegressor`, auto-trains on first run, saved to `models/rf_baseline.joblib`.
  Code: `src/backend/ml/scoring.py`.

**Pricing**

* Maps risk score (0–100) to monthly premium (base + risk load).
  Code: `src/backend/ml/pricing.py`.

**Driver UX**

* Dashboard shows current score, premium, recent trips, “Why this score?”, **Coach me on last trip**, gamification.

**Security & Privacy**

* API-key header `x-api-key`.
* Pydantic validation.
* Synthetic data only; all local.

**Scalability**

* Clean FastAPI + SQLAlchemy.
* `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.dashboard`.
* Swap SQLite → Postgres by changing `DB_URL`.

**Manual checklist**

* [ ] `GET /health` returns `{"status":"ok"}`
* [ ] `bin/generate_data.py` ingests without errors
* [ ] Dashboard shows score, premium, trips, explanations
* [ ] “Coach me on last trip” returns guidance
* [ ] Toggle rule vs ML by setting `USE_ML=false/true` and restarting the API:

  ```bash
  python -m uvicorn src.backend.api.app:app --port 8000
  ```

---

## 4) Project Structure

```
/bin
  generate_data.py
/data
  telematics.db              # created on first run
/docs
  api.md
  architecture.md
  data_schema.md
  privacy_security.md
  scoring_and_pricing.md
  /img                       # screenshots (dashboard, health, etc.)
/models
  rf_baseline.joblib         # created on first ML run (or pre-saved)
/src
  /backend
    /api/app.py
    /db/store.py
    /ml/scoring.py
    /ml/pricing.py
    /utils/...
  /dashboard/dashboard.py
Dockerfile.api
Dockerfile.dashboard
docker-compose.yml
.env.example
requirements.txt
```

---

## 5) Notes on Models, Data, External Services

* **Data:** Synthetic telemetry; no external APIs.
* **Rules model:** Weighted, capped penalties (harsh brakes, speeding density, night share, etc.).
* **ML baseline:** Quick Random Forest on engineered features; saves to `/models`.
* **Pricing:** Simple, explainable mapping—easy to swap for GLM/GBM.
* **Security:** API key now; real system would add JWT/OAuth, TLS, rate limiting, PII controls.

---

## 6) Troubleshooting

**`ModuleNotFoundError: sklearn`**
Start uvicorn with the venv Python (no `--reload` during ML testing):

```bash
python -m uvicorn src.backend.api.app:app --port 8000
```

**Clear local data**

```bash
rm -f data/telematics.db
```

Re-start API and re-run the simulator.

**References**
```bash
Third-party libraries 
- FastAPI (MIT) — https://fastapi.tiangolo.com/
- Uvicorn (BSD) — https://www.uvicorn.org/
- SQLAlchemy (MIT) — https://www.sqlalchemy.org/
- Pydantic (MIT) — https://docs.pydantic.dev/
- scikit-learn (BSD-3) — https://scikit-learn.org/
- Streamlit (Apache-2.0) — https://streamlit.io/
- NumPy (BSD-3) — https://numpy.org/
- Pandas (BSD-3) — https://pandas.pydata.org/
- Requests (Apache-2.0) — https://requests.readthedocs.io/
```

---

