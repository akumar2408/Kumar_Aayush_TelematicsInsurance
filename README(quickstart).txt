Telematics Insurance – POC+ (Reviewer Quick Start)

1) Setup
   - Python 3.11
   - python -m venv .venv && source .venv/bin/activate
   - pip install -r requirements.txt
   - cp .env.example .env  (ensure API_KEY=changeme, USE_ML=true)
   - rm -f data/telematics.db

2) Run API (no --reload)
   - python -m uvicorn src.backend.api.app:app --port 8000
   - Health: http://127.0.0.1:8000/health

3) Generate data (new terminal)
   - source .venv/bin/activate
   - export API_KEY=changeme
   - python bin/generate_data.py --days 3 --driver-id D001

4) Dashboard
   - streamlit run src/dashboard/dashboard.py --server.port 8501
   - Open http://127.0.0.1:8501 (driver: D001)

