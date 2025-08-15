# train_real_model.py
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

df = pd.read_csv("trip_data.csv")

# If you capture real observed arrival times later, use that as y.
# For now using route_time_min as target.
df["hour"] = df["hour"].astype(int)
df["weekday"] = df["weekday"].astype(int)

X = df[["distance_km","route_time_min","hour","weekday"]]
y = df["route_time_min"]  # or later substitute actual observed time

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print("MAE:", mean_absolute_error(y_test, y_pred))

joblib.dump(model, "real_traffic_model.pkl")
