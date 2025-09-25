import os
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from ..db.store import DB, get_session
from ..ml.scoring import aggregate_driver_score, coaching_hints, score_trip_rules, score_trip_ml
from ..ml.pricing import premium_from_score

API_KEY = os.getenv("API_KEY","devkey")
app = FastAPI(title="Telematics Insurance API", version="0.2.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class TripPoint(BaseModel):
    ts: datetime; speed_kph: float; accel_mps2: float; lat: float; lon: float
class TripIn(BaseModel):
    driver_id: str = Field(..., json_schema_extra={"examples":["D001"]})
    start_ts: datetime; end_ts: datetime; distance_km: float; avg_speed: float; max_speed: float
    harsh_brakes: int; night_ratio: float; speeding_events: int; centroid_lat: float; centroid_lon: float
class TripPointsIn(BaseModel):
    driver_id: str; points: List[TripPoint] = Field(min_length=2)
class EnrichmentIn(BaseModel):
    vehicle_risk: Optional[float]=0.0; driver_history_risk: Optional[float]=0.0
    local_crime_index: Optional[float]=0.0; local_crash_rate: Optional[float]=0.0; weather_risk: Optional[float]=0.0

@app.get("/health") 
def health(): return {"status":"ok"}

def _auth_or_401(x_api_key: str | None):
    if x_api_key != API_KEY: raise HTTPException(401,"Unauthorized")

@app.post("/ingest/trip")
def ingest_trip(trip: TripIn, x_api_key: str | None = Header(None)):
    _auth_or_401(x_api_key)
    with get_session() as s:
        if not DB.get_driver(s, trip.driver_id):
            DB.create_driver(s, driver_id=trip.driver_id, name="Demo Driver", base_rate=120.0, vehicle="Sedan")
        DB.create_trip(s, **trip.model_dump())
        use_ml = (os.getenv("USE_ML","false").lower()=="true")
        features = DB.features_for_trip(trip.model_dump())
        trip_score, contrib = (score_trip_ml if use_ml else score_trip_rules)(features)
        DB.upsert_trip_score(s, trip_id=DB.last_trip_id(s), score=trip_score, contrib=contrib)
        driver_score, driver_breakdown = aggregate_driver_score(s, trip.driver_id)
        DB.upsert_driver_score(s, driver_id=trip.driver_id, score=driver_score, breakdown=driver_breakdown)
        DB.update_gamification_on_score(s, trip.driver_id, driver_score)
        premium, breakdown = premium_from_score(base_rate=DB.get_driver(s, trip.driver_id).base_rate, score=driver_score)
        DB.upsert_premium(s, driver_id=trip.driver_id, premium=premium, breakdown=breakdown)
    return {"ok": True}

@app.post("/ingest/telemetry")
def ingest_points(batch: TripPointsIn, x_api_key: str | None = Header(None)):
    _auth_or_401(x_api_key)
    pts = batch.points
    if len(pts) < 2: raise HTTPException(400,"Need at least 2 points")
    pts_sorted = sorted(pts, key=lambda p: p.ts)
    distance_km=0.0
    for i in range(1,len(pts_sorted)):
        dt_min=(pts_sorted[i].ts-pts_sorted[i-1].ts).total_seconds()/60.0
        distance_km += pts_sorted[i-1].speed_kph * (dt_min/60.0)
    avg_speed=sum(p.speed_kph for p in pts)/len(pts)
    max_speed=max(p.speed_kph for p in pts)
    harsh_brakes=sum(1 for p in pts if p.accel_mps2<-3.5)
    night_ratio=sum(1 for p in pts if p.ts.hour<6 or p.ts.hour>=22)/len(pts)
    SPEED_LIMIT=70
    speeding_events=sum(1 for p in pts if p.speed_kph>SPEED_LIMIT)
    centroid_lat=sum(p.lat for p in pts)/len(pts); centroid_lon=sum(p.lon for p in pts)/len(pts)
    trip=TripIn(driver_id=batch.driver_id, start_ts=min(p.ts for p in pts), end_ts=max(p.ts for p in pts),
                distance_km=distance_km, avg_speed=avg_speed, max_speed=max_speed, harsh_brakes=harsh_brakes,
                night_ratio=night_ratio, speeding_events=speeding_events, centroid_lat=centroid_lat, centroid_lon=centroid_lon)
    resp = ingest_trip(trip, x_api_key=x_api_key)
    hints = coaching_hints([p.model_dump() for p in pts])
    resp.update({"hints":hints})
    return resp

@app.get("/drivers/{driver_id}/score")
def get_score(driver_id:str):
    with get_session() as s:
        ds = DB.get_driver_score(s, driver_id)
        if not ds: raise HTTPException(404,"No score yet for driver")
        return ds

@app.get("/drivers/{driver_id}/premium")
def get_premium(driver_id:str):
    with get_session() as s:
        p = DB.get_premium(s, driver_id)
        if not p: raise HTTPException(404,"No premium yet for driver")
        p["gamification"] = DB.get_gamification(s, driver_id)
        return p

@app.get("/drivers/{driver_id}/trips")
def get_trips(driver_id:str):
    with get_session() as s:
        return {"trips": DB.get_trips(s, driver_id)}

@app.get("/drivers/{driver_id}/coach")
def coach_last_trip(driver_id:str):
    with get_session() as s:
        trips = DB.get_trips(s, driver_id)
        if not trips: raise HTTPException(404,"No trips")
        last = trips[0]
        pts=[{"ts": datetime.utcnow(), "speed_kph": last["avg_speed"], "accel_mps2": -0.2, "lat": last["centroid"][0], "lon": last["centroid"][1]} for _ in range(10)]
        return {"hints": coaching_hints(pts)}

@app.post("/enrich/{driver_id}")
def set_enrichment(driver_id:str, payload: EnrichmentIn, x_api_key: str | None = Header(None)):
    _auth_or_401(x_api_key)
    with get_session() as s:
        if not DB.get_driver(s, driver_id):
            DB.create_driver(s, driver_id=driver_id, name="Demo Driver", base_rate=120.0, vehicle="Sedan")
        DB.set_enrichment(s, driver_id, **payload.model_dump())
    return {"ok": True, "enrichment": payload.model_dump()}
