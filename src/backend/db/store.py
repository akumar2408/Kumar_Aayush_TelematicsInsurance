from contextlib import contextmanager
from typing import Optional, List
from sqlalchemy import create_engine, String, Integer, Float, DateTime, ForeignKey, func, select
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import os, json

DB_URL = os.environ.get("DB_URL", "sqlite:///./telematics.db")
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

class Base(DeclarativeBase): pass

class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    base_rate: Mapped[float] = mapped_column(Float)
    vehicle: Mapped[str] = mapped_column(String)

class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"))
    start_ts: Mapped[datetime] = mapped_column(DateTime)
    end_ts: Mapped[datetime] = mapped_column(DateTime)
    distance_km: Mapped[float] = mapped_column(Float)
    avg_speed: Mapped[float] = mapped_column(Float)
    max_speed: Mapped[float] = mapped_column(Float)
    harsh_brakes: Mapped[int] = mapped_column(Integer)
    night_ratio: Mapped[float] = mapped_column(Float)
    speeding_events: Mapped[int] = mapped_column(Integer)
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)

class TripScore(Base):
    __tablename__ = "trip_scores"
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    contrib: Mapped[str] = mapped_column(String)

class DriverScore(Base):
    __tablename__ = "driver_scores"
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

class Premium(Base):
    __tablename__ = "premiums"
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    monthly_premium: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

class Enrichment(Base):
    __tablename__ = "enrichment"
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    vehicle_risk: Mapped[float] = mapped_column(Float, default=0.0)
    driver_history_risk: Mapped[float] = mapped_column(Float, default=0.0)
    local_crime_index: Mapped[float] = mapped_column(Float, default=0.0)
    local_crash_rate: Mapped[float] = mapped_column(Float, default=0.0)
    weather_risk: Mapped[float] = mapped_column(Float, default=0.0)

class Gamification(Base):
    __tablename__ = "gamification"
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), primary_key=True)
    safe_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_safe_date: Mapped[str] = mapped_column(String, default="")
    points: Mapped[int] = mapped_column(Integer, default=0)

Base.metadata.create_all(bind=engine)

@contextmanager
def get_session():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback(); raise
    finally:
        s.close()

class DB:
    @staticmethod
    def get_driver(s, driver_id: str) -> Optional[Driver]: return s.get(Driver, driver_id)
    @staticmethod
    def create_driver(s, driver_id: str, name: str, base_rate: float, vehicle: str):
        s.add(Driver(id=driver_id, name=name, base_rate=base_rate, vehicle=vehicle))
        s.merge(Enrichment(driver_id=driver_id)); s.merge(Gamification(driver_id=driver_id))
    @staticmethod
    def create_trip(s, **kwargs):
        t = Trip(**kwargs); s.add(t); s.flush(); return t.id
    @staticmethod
    def last_trip_id(s) -> int:
        tid = s.execute(select(func.max(Trip.id))).scalar_one()
        return int(tid) if tid is not None else 0
    @staticmethod
    def features_for_trip(trip_dict)->dict:
        return {k: trip_dict[k] for k in ["distance_km","avg_speed","max_speed","harsh_brakes","night_ratio","speeding_events"]}
    @staticmethod
    def upsert_trip_score(s, trip_id:int, score:float, contrib:dict):
        s.merge(TripScore(trip_id=trip_id, score=score, contrib=json.dumps(contrib)))
    @staticmethod
    def aggregate_trip_features(s, driver_id:str)->list:
        rows = s.execute(select(Trip).where(Trip.driver_id==driver_id).order_by(Trip.id.desc()).limit(60)).scalars().all()
        return [{
            "distance_km": r.distance_km, "avg_speed": r.avg_speed, "max_speed": r.max_speed,
            "harsh_brakes": r.harsh_brakes, "night_ratio": r.night_ratio, "speeding_events": r.speeding_events
        } for r in rows]
    @staticmethod
    def upsert_driver_score(s, driver_id:str, score:float, breakdown:dict):
        s.merge(DriverScore(driver_id=driver_id, score=score, breakdown=json.dumps(breakdown), updated_at=datetime.utcnow()))
    @staticmethod
    def get_driver_score(s, driver_id:str)->Optional[dict]:
        ds = s.get(DriverScore, driver_id); 
        if not ds: return None
        return {"driver_id":driver_id,"score":ds.score,"breakdown":json.loads(ds.breakdown),"updated_at":ds.updated_at.isoformat()}
    @staticmethod
    def upsert_premium(s, driver_id:str, premium:float, breakdown:dict):
        s.merge(Premium(driver_id=driver_id, monthly_premium=premium, breakdown=json.dumps(breakdown), updated_at=datetime.utcnow()))
    @staticmethod
    def get_premium(s, driver_id:str)->Optional[dict]:
        p = s.get(Premium, driver_id); 
        if not p: return None
        return {"driver_id":driver_id,"monthly_premium":round(p.monthly_premium,2),"breakdown":json.loads(p.breakdown),"updated_at":p.updated_at.isoformat()}
    @staticmethod
    def get_trips(s, driver_id:str)->List[dict]:
        rows = s.execute(select(Trip).where(Trip.driver_id==driver_id).order_by(Trip.start_ts.desc()).limit(50)).scalars().all()
        return [{
            "id": r.id, "start_ts": r.start_ts.isoformat(), "end_ts": r.end_ts.isoformat(),
            "distance_km": r.distance_km, "avg_speed": r.avg_speed, "max_speed": r.max_speed,
            "harsh_brakes": r.harsh_brakes, "night_ratio": r.night_ratio, "speeding_events": r.speeding_events,
            "centroid":[r.centroid_lat, r.centroid_lon]
        } for r in rows]
    @staticmethod
    def set_enrichment(s, driver_id:str, **kwargs):
        row = s.get(Enrichment, driver_id) or Enrichment(driver_id=driver_id)
        for k,v in kwargs.items():
            if hasattr(row,k) and v is not None: setattr(row,k,float(v))
        s.merge(row)
    @staticmethod
    def get_enrichment(s, driver_id:str)->dict:
        row = s.get(Enrichment, driver_id)
        if not row: return {}
        return {"vehicle_risk":row.vehicle_risk,"driver_history_risk":row.driver_history_risk,
                "local_crime_index":row.local_crime_index,"local_crash_rate":row.local_crash_rate,"weather_risk":row.weather_risk}
    @staticmethod
    def get_gamification(s, driver_id:str)->dict:
        g = s.get(Gamification, driver_id)
        if not g: return {"safe_streak_days":0,"points":0,"last_safe_date":""}
        return {"safe_streak_days":g.safe_streak_days,"points":g.points,"last_safe_date":g.last_safe_date}
    @staticmethod
    def update_gamification_on_score(s, driver_id:str, score:float):
        from datetime import datetime as dt
        today = dt.utcnow().date().isoformat()
        g = s.get(Gamification, driver_id) or Gamification(driver_id=driver_id)
        SAFE_THRESHOLD = 20.0
        if score <= SAFE_THRESHOLD:
            if g.last_safe_date != today:
                g.safe_streak_days += 1; g.last_safe_date = today; g.points += 5
        else:
            g.safe_streak_days = 0
        s.merge(g)
