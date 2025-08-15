# train_model.py
import random
import math
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

def generate_synthetic_data(n=5000, seed=42):
    random.seed(seed)
    rows = []
    for _ in range(n):
        # distance in km (0.2 - 60 km)
        dist = round(random.uniform(0.2, 60.0), 3)
        # base free-flow speed (km/h) vary across sample
        free_flow_speed = random.uniform(40, 100)
        # route_time minutes if free-flow
        route_time_min = dist / (free_flow_speed / 60.0)  # minutes

        # traffic factor (>=1.0); higher during rush hours
        hour = random.randint(0, 23)
        weekday = random.randint(0, 6)
        rush = 1.0
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            rush += random.uniform(0.2, 0.6)  # rush hour slowdown
        # random incident noise
        incident = random.choice([0.0, random.uniform(0.0, 0.5)])
        traffic_multiplier = rush + incident + random.uniform(-0.05, 0.08)

        # observed_time is route_time_min * traffic_multiplier + measurement noise
        observed_time_min = route_time_min * traffic_multiplier * (1 + random.uniform(-0.06, 0.06))

        rows.append([dist, route_time_min, hour, weekday, observed_time_min])

    df = pd.DataFrame(rows, columns=["distance_km", "route_time_min", "hour", "weekday", "observed_time_min"])
    return df

def train_and_save(path="traffic_predictor.pkl"):
    print("Generating synthetic dataset...")
    df = generate_synthetic_data()
    X = df[["distance_km", "route_time_min", "hour", "weekday"]]
    y = df["observed_time_min"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)

    print("Training RandomForestRegressor...")
    model = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, pred)
    print(f"Model trained. Test MAE = {mae:.2f} minutes")

    joblib.dump(model, path)
    print(f"Saved model to {path}")
    return path

if __name__ == "__main__":
    train_and_save()
