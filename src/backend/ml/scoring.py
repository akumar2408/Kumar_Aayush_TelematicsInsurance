from typing import Dict, Tuple
import math, os

def clamp(x, lo, hi): return max(lo, min(hi, x))
def sigmoid(x): return 1/(1+math.exp(-x))

def _base_features(f:Dict):
    dist = max(f.get("distance_km",0.1),0.1)
    return (100.0*f.get("harsh_brakes",0)/dist,
            100.0*f.get("speeding_events",0)/dist,
            clamp(f.get("night_ratio",0.0),0.0,1.0))

def score_trip_rules(f:Dict)->Tuple[float,Dict]:
    avg_speed, max_speed = f.get("avg_speed",0.0), f.get("max_speed",0.0)
    harsh_per_100, speeding_per_100, night = _base_features(f)
    c_speed = 0.25*clamp(max(avg_speed-60,0)/40,0,1) + 0.35*clamp(max(max_speed-80,0)/40,0,1)
    c_brake = 0.30*sigmoid((harsh_per_100-6)/2.0)
    c_night = 0.20*night
    c_speeding = 0.35*sigmoid((speeding_per_100-5)/2.0)
    linear = 30*c_speed + 25*c_brake + 20*c_night + 25*c_speeding
    score = float(clamp(linear,0,100))
    contrib = {"model":"rules","avg_speed_over_60":round(c_speed*100,1),
               "harsh_brakes_per_100km":round(c_brake*100,1),"night_ratio":round(c_night*100,1),
               "speeding_events_per_100km":round(c_speeding*100,1),
               "norms":{"harsh_per_100km":round(harsh_per_100,2),"speeding_per_100km":round(speeding_per_100,2)}}
    return score, contrib

_model=None
def _load_or_train_model():
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    global _model
    if _model is not None: return _model
    rng = np.random.RandomState(42)
    X = rng.uniform([40,70,0,0,0],[85,130,20,1,20], size=(1200,5))
    y = (0.35*np.clip((X[:,0]-60)/40,0,1) + 0.45*np.clip((X[:,1]-80)/40,0,1)
         + 0.4*(1/(1+np.exp(-(X[:,2]-6)/2))) + 0.3*X[:,3]
         + 0.45*(1/(1+np.exp(-(X[:,4]-5)/2)))) * 25
    rf = RandomForestRegressor(n_estimators=120, random_state=42); rf.fit(X,y); _model=rf; return _model

def score_trip_ml(f:Dict)->Tuple[float,Dict]:
    import numpy as np
    harsh_per_100, speeding_per_100, night = _base_features(f)
    x = np.array([[f.get("avg_speed",0.0), f.get("max_speed",0.0), harsh_per_100, night, speeding_per_100]])
    model = _load_or_train_model()
    score = float(np.clip(model.predict(x)[0],0,100))
    return score, {"model":"RandomForestRegressor (synthetic)","norms":{"harsh_per_100km":round(harsh_per_100,2),"speeding_per_100km":round(speeding_per_100,2)}}

def apply_enrichment_offsets(score:float, enrich:Dict)->Tuple[float,Dict]:
    weights={"vehicle_risk":5.0,"driver_history_risk":7.0,"local_crime_index":3.0,"local_crash_rate":4.0,"weather_risk":6.0}
    offsets={}
    for k,w in weights.items():
        v=float(enrich.get(k,0.0) or 0.0)
        if v!=0.0: score+=w*v; offsets[k]=round(w*v,2)
    score=float(clamp(score,0,100))
    return score, {"enrichment_offsets":offsets}

def aggregate_driver_score(db_session, driver_id:str)->Tuple[float,Dict]:
    from ..db.store import DB
    feats = DB.aggregate_trip_features(db_session, driver_id)
    if not feats: return 0.0, {"note":"no trips"}
    total=0.0; weighted=0.0; parts={"trips":[]}
    use_ml=(os.getenv("USE_ML","false").lower()=="true")
    for f in feats:
        s, br = (score_trip_ml if use_ml else score_trip_rules)(f)
        d=max(f.get("distance_km",0.1),0.1); weighted+=s*d; total+=d; parts["trips"].append({"score":s,"distance_km":d,"breakdown":br})
    overall=weighted/max(total,0.1)
    enrich = DB.get_enrichment(db_session, driver_id)
    overall2, enr = apply_enrichment_offsets(overall, enrich)
    parts.update(enr)
    return float(round(overall2,2)), parts

def coaching_hints(points):
    hints=[]; 
    if not points: return hints
    over = sum(1 for p in points if p.get("speed_kph",0)>75)
    hard = sum(1 for p in points if p.get("accel_mps2",0)<-3.5)
    night = sum(1 for p in points if p["ts"].hour<6 or p["ts"].hour>=22)/len(points)
    if over>5: hints.append("You're frequently over the limit—ease off to reduce risk and premium.")
    if hard>3: hints.append("Lots of hard braking—leave more following distance and plan earlier.")
    if night>0.5: hints.append("High share of night driving—consider avoiding late hours when possible.")
    if not hints: hints.append("Nice work—smooth driving detected 👍")
    return hints
