# ml_model.py
import os
import joblib
import numpy as np
from datetime import datetime

MODEL_PATH = os.environ.get("REAL_MODEL_PATH", "real_traffic_model.pkl")

_model = None

def load_model():
    global _model
    if _model is not None:
        return _model
    if os.path.exists(MODEL_PATH):
        try:
            _model = joblib.load(MODEL_PATH)
            return _model
        except Exception as e:
            # can't load model - proceed without it
            _model = None
            return None
    else:
        _model = None
        return None

def model_available():
    """Return True if a trained model is present and loadable."""
    return load_model() is not None

def predict_eta(distance_km, route_time_min, hour=None, weekday=None):
    """
    Predict ETA (minutes). If model exists, use it. Otherwise, use a heuristic:
      heuristic = route_time_min * (1 + traffic_factor)
    where traffic_factor depends on hour/weekday.
    """
    if hour is None or weekday is None:
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

    model = load_model()
    if model is not None:
        X = np.array([[distance_km, route_time_min, hour, weekday]], dtype=float)
        try:
            eta = float(model.predict(X)[0])
            return max(0.0, round(eta, 2))
        except Exception:
            pass

    # Fallback heuristic:
    # base is route_time_min; add slowdowns during rush hours
    traffic_multiplier = 1.0
    if 7 <= hour <= 9 or 17 <= hour <= 19:
        traffic_multiplier += 0.3  # typical rush slowdown
    # slightly slower on weekdays (Mon-Fri)
    if weekday < 5:
        traffic_multiplier += 0.05
    eta = route_time_min * traffic_multiplier
    return max(0.0, round(float(eta), 2))
