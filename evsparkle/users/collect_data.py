# collect_data.py
import requests
import csv
import time
from datetime import datetime

ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJhYjRlYjI1YzQxMjRkY2NiYjFiZmEzNTlmNDdkY2YxIiwiaCI6Im11cm11cjY0In0="

def get_route_time(lat1, lon1, lat2, lon2):
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    payload = {"coordinates": [[lon1, lat1], [lon2, lat2]], "instructions": False}
    headers = {"Authorization": ORS_KEY, "Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    summary = data.get("features", [{}])[0].get("properties", {}).get("summary", {})
    return summary.get("duration", None) / 60.0, summary.get("distance", None) / 1000.0

# Example origin/destination list
trips = [
    {"origin": (12.9611, 77.6387), "dest": (12.9716,77.5946)},
    {"origin": (12.9611, 77.6387), "dest": (12.9352,77.6245)},
]

# CSV header: timestamp,hour,weekday,origin_lat,origin_lon,dest_lat,dest_lon,distance_km,route_time_min
with open("trip_data.csv", "a", newline="") as f:
    writer = csv.writer(f)
    for t in trips:
        now = datetime.now()
        route_time, dist = get_route_time(*t["origin"], *t["dest"])
        if route_time is None:
            continue
        writer.writerow([
            now.isoformat(),
            now.hour,
            now.weekday(),
            *t["origin"],
            *t["dest"],
            round(dist, 3),
            round(route_time, 2)
        ])
        time.sleep(1)  # avoid rate limit
