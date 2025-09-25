# Model Card — Telematics Baseline RF (v1.0)

**Purpose.** Predict a driver trip risk score (0–100) from aggregated telematics features.
Used to power the ML path in the POC pricing engine.

**Inputs (features).**  
`distance_km, avg_speed, max_speed, harsh_brakes, night_ratio, speeding_events`  
See `feature_list.json` (order matters).

**Training data.** Synthetic telematics generated to mimic the simulator’s distributions.
Target is a noisy version of the rules score so the model learns a similar mapping.

**Algorithm.** RandomForestRegressor (250 trees, max_depth=10, min_samples_leaf=2, n_jobs=-1).

**Preprocessing.** No scaling; features are numeric and bounded. Missing values not expected.

**Metrics (synthetic holdout).** See `metrics.json` (typical: R² ≈ 0.75–0.85, MAE ≈ 2–4 score points).

**Calibration.** Predictions are clipped to [0,100] by the API after inference.

**Fairness & limitations.**
- No protected attributes used; only driving-behavior aggregates.
- Synthetic data → not representative of real populations. Do **not** deploy without retraining on real data and conducting bias, drift, and calibration checks.

**Versioning.** `rf_v1.0` (see `VERSION`). Reproducible via `python models/train.py`.
