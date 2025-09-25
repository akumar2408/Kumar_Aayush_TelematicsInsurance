import argparse, random
from datetime import datetime, timedelta
import requests, os, math

API = os.environ.get("API_URL", "http://localhost:8000")

def simulate_trip(driver_id: str, start: datetime, minutes: int = 30):
    rng = random.Random(driver_id + start.isoformat())
    points = []
    lat, lon = 33.4255, -111.94
    hour = start.hour
    for i in range(minutes):
        base = 55 + 10*math.sin(i/10.0)
        speed = max(0, rng.gauss(base + (5 if hour>=22 or hour<6 else 0), 8))
        accel = rng.gauss(-0.2, 1.2)
        if rng.random() < 0.10 and speed > 50:
            accel = -5.0 - 2.0*rng.random()
        lat += rng.uniform(-0.0005, 0.0005); lon += rng.uniform(-0.0005, 0.0005)
        points.append({"ts": (start + timedelta(minutes=i)).isoformat(),
                       "speed_kph": speed, "accel_mps2": accel, "lat": lat, "lon": lon})
    r = requests.post(f"{API}/ingest/telemetry",
                      json={"driver_id": driver_id, "points": points},
                      headers={"x-api-key": os.getenv("API_KEY","devkey")},
                      timeout=10)
    if r.ok: print(f"Ingested simulated trip for {driver_id} starting {start}")
    else: print("Ingest failed:", r.text)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=3); ap.add_argument("--driver-id", type=str, default="D001")
    args = ap.parse_args(); now = datetime.now().replace(second=0, microsecond=0)
    for d in range(args.days):
        day = now - timedelta(days=d+1)
        for hr in [8, 18, 23]:
            start = day.replace(hour=hr, minute=0)
            simulate_trip(args.driver_id, start, minutes=35 if hr==18 else 25)

if __name__ == "__main__": main()
