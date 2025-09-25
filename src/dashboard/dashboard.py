import streamlit as st, requests, pandas as pd, os
API = os.environ.get("API_URL","http://localhost:8000")
st.set_page_config(page_title="Telematics (POC+)", layout="wide")
st.title("Telematics Insurance – Driver Dashboard (POC+)")
driver_id = st.text_input("Driver ID", value="D001")

colA, colB = st.columns(2)
with colA:
    if st.button("Refresh Score & Premium"): pass
    try:
        score = requests.get(f"{API}/drivers/{driver_id}/score", timeout=5).json()
        premium = requests.get(f"{API}/drivers/{driver_id}/premium", timeout=5).json()
    except Exception:
        st.warning("Could not reach API. Start FastAPI on :8000 and try again."); st.stop()
    if "score" in score: st.metric("Risk Score (0-100)", score["score"])
    if "monthly_premium" in premium: st.metric("Current Monthly Premium ($)", premium["monthly_premium"])

with colB:
    st.subheader("Why this score?")
    if score and "breakdown" in score:
        trips = score["breakdown"].get("trips", [])
        if trips:
            df = pd.DataFrame([{
                "Trip Score": t["score"],
                "Distance (km)": t["distance_km"],
                "Harsh per 100km": t["breakdown"]["norms"]["harsh_per_100km"],
                "Speeding per 100km": t["breakdown"]["norms"]["speeding_per_100km"]
            } for t in trips])
            st.dataframe(df, use_container_width=True, height=280)
        else:
            st.info("No trips yet. Ingest a trip with the simulator.")

st.divider()
st.subheader("Recent trips")
try:
    trips = requests.get(f"{API}/drivers/{driver_id}/trips", timeout=5).json().get("trips", [])
    if trips:
        st.dataframe(pd.DataFrame(trips), use_container_width=True, height=300)
    else:
        st.info("No trips yet.")
except Exception:
    st.warning("Could not load trips.")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Gamification")
    try:
        p = requests.get(f"{API}/drivers/{driver_id}/premium", timeout=5).json()
        gam = p.get("gamification", {})
        st.write(f"Safe streak days: **{gam.get('safe_streak_days',0)}**")
        st.write(f"Points: **{gam.get('points',0)}**")
    except Exception:
        st.info("Start the API to see gamification.")

with col2:
    st.subheader("Coach")
    if st.button("Coach me on last trip"):
        try:
            hints = requests.get(f"{API}/drivers/{driver_id}/coach", timeout=5).json().get("hints", [])
            for h in hints:
                st.write("• " + h)
        except Exception:
            st.info("No coaching available yet.")
