# models/train.py
# trains the baseline RF on synthetic telematics features and saves artifacts to /models
import json, os, pathlib, math, random
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

HERE = pathlib.Path(__file__).resolve().parent
ARTIFACT_DIR = HERE
FEATURES = [
    "distance_km",
    "avg_speed",
    "max_speed",
    "harsh_brakes",
    "night_ratio",
    "speeding_events",
]

def synthesize(n=8000, seed=42):
    rng = np.random.default_rng(seed)

    # distance: short urban hops + a tail of longer trips
    distance_km = np.round(np.clip(rng.exponential(6.0, n), 0.3, 120.0), 4)

    # average speed: mostly urban/highway mix
    avg_speed = np.round(np.clip(rng.normal(60, 12, n), 10, 120), 4)

    # max speed: above average speed; bounded
    max_speed = np.round(np.clip(avg_speed + rng.normal(20, 8, n), 20, 150), 4)

    # harsh brakes: Poisson with rate tied to distance + bad style
    harsh_base = rng.poisson(lam=np.clip(distance_km/8, 0.1, 7.0))
    harsh_style = rng.poisson(lam=rng.uniform(0, 2.0, n))
    harsh_brakes = np.clip(harsh_base + harsh_style, 0, 25).astype(float)

    # night_ratio: portion (0..1) of trip at night, skewed low but with tail
    night_ratio = np.clip(rng.beta(1.5, 4.0, n), 0, 1)

    # speeding events: correlated with max_speed and avg_speed
    speed_pressure = np.maximum(0, (max_speed - 85)/10) + np.maximum(0, (avg_speed - 70)/12)
    speeding_events = np.clip(rng.poisson(lam=1.5 + speed_pressure), 0, 30).astype(float)

    df = pd.DataFrame({
        "distance_km": distance_km,
        "avg_speed": avg_speed,
        "max_speed": max_speed,
        "harsh_brakes": harsh_brakes,
        "night_ratio": night_ratio,
        "speeding_events": speeding_events,
    })

    # Synthetic target: mirror your rules logic to give the RF something learnable.
    # (weights roughly match the rules engine; add noise to avoid overfitting)
    harsh_per_100 = (df["harsh_brakes"] / np.maximum(df["distance_km"], 0.001)) * 100
    speeding_per_100 = (df["speeding_events"] / np.maximum(df["distance_km"], 0.001)) * 100

    score = (
        0.45 * np.clip(harsh_per_100 / 12.0 * 100, 0, 100) +
        0.35 * np.clip(speeding_per_100 / 10.0 * 100, 0, 100) +
        0.20 * np.clip(df["night_ratio"] * 100, 0, 100)
    )

    # Add modest dependence on max_speed/avg_speed directly (regularization of proxy)
    score = score * 0.9 + 0.1 * np.clip((df["max_speed"] - 60) * 1.2, 0, 100)

    # Noise
    score = np.clip(score + np.random.normal(0, 3.0, size=n), 0, 100)

    return df, score

def main():
    X, y = synthesize(n=8000, seed=42)
    X_train, X_test, y_train, y_test = train_test_split(X[FEATURES], y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(
        n_estimators=250, max_depth=10, random_state=42, n_jobs=-1, min_samples_leaf=2
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred))
    r2  = float(r2_score(y_test, y_pred))

    # Save artifacts
    joblib.dump(model, ARTIFACT_DIR / "baseline_rf.pkl")
    with open(ARTIFACT_DIR / "feature_list.json", "w") as f:
        json.dump(FEATURES, f, indent=2)
    with open(ARTIFACT_DIR / "metrics.json", "w") as f:
        json.dump({"mae": mae, "r2": r2, "n_test": len(y_test)}, f, indent=2)
    with open(ARTIFACT_DIR / "VERSION", "w") as f:
        f.write("rf_v1.0\n")

    print(f"[models] saved baseline_rf.pkl  | MAE={mae:.2f}  R2={r2:.3f}")

if __name__ == "__main__":
    main()
