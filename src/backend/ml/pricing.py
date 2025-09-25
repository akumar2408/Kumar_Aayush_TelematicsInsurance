from typing import Dict, Tuple
def premium_from_score(base_rate: float, score: float) -> Tuple[float, Dict]:
    if score <= 25:
        multiplier = 0.8 + 0.2*(score/25.0)
    elif score >= 85:
        multiplier = 1.4 + 0.2*((score-85)/15.0)
    else:
        multiplier = 1.0 + 0.4*((score-25)/60.0)
    premium = base_rate * multiplier
    breakdown = {"base_rate": round(base_rate,2), "risk_score": round(score,2), "multiplier": round(multiplier,3)}
    return float(round(premium,2)), breakdown
