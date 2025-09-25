# Architecture
- Ingest (FastAPI) → Trip Aggregation → Scoring (rules or ML) → Pricing → Dashboard.
- Optional enrichment: vehicle/history/crime/crash/weather.
- Docker Compose brings up Postgres + API + Dashboard.
