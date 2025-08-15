# views.py
import os
import math
import json
import requests
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from .ml_model import predict_eta, model_available

# environment keys
ORS_KEY = os.environ.get("OPENROUTESERVICE_KEY")   # required for route times
OCM_KEY = os.environ.get("OPENCHARGEMAP_KEY")     # optional for OpenChargeMap

def home(request):
    return render(request, 'home.html')

def ev_charging_map(request):
    context = {
        'page_title': 'EV Charging Stations',
        'default_lat': 28.6139,  # Default coordinates (New Delhi)
        'default_lng': 77.2090,
    }
    return render(request, 'ev_map.html', context)

@csrf_exempt
def get_charging_stations_api(request):
    """
    Optional: Use Overpass API to fetch 'amenity=charging_station' POIs near lat/lon
    POST JSON: { lat, lon, radius (meters, optional) }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    try:
        data = json.loads(request.body)
        lat = float(data.get('lat'))
        lon = float(data.get('lon'))
        radius = int(data.get('radius', 2000))
    except Exception as e:
        return JsonResponse({'error': 'Invalid JSON or missing lat/lon: ' + str(e)}, status=400)

    query = f"""
        [out:json][timeout:25];
        (
            node["amenity"="charging_station"](around:{radius},{lat},{lon});
            way["amenity"="charging_station"](around:{radius},{lat},{lon});
            relation["amenity"="charging_station"](around:{radius},{lat},{lon});
        );
        out center;
    """
    url = 'https://overpass-api.de/api/interpreter'
    try:
        # NOTE: using requests.post (not request.post)
        resp = requests.post(url, data={'data': query}, timeout=30)
        resp.raise_for_status()
        return JsonResponse(resp.json())
    except Exception as e:
        return JsonResponse({'error': 'Overpass API error: ' + str(e)}, status=500)


# ---------- OpenChargeMap helper ----------
def query_openchargemap(lat, lon, max_km=10, maxresults=20):
    base = "https://api.openchargemap.io/v3/poi/"
    params = {
        "output": "json",
        "latitude": lat,
        "longitude": lon,
        "distance": max_km,
        "distanceunit": "KM",
        "maxresults": maxresults
    }
    headers = {}
    if OCM_KEY:
        headers["X-API-Key"] = OCM_KEY
    r = requests.get(base, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


# ---------- OpenRouteService routing summary ----------
def get_route_summary_seconds(origin_lat, origin_lon, dest_lat, dest_lon):
    if not ORS_KEY:
        raise RuntimeError("Server missing OPENROUTESERVICE_KEY environment variable.")
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    body = {
        "coordinates": [[origin_lon, origin_lat], [dest_lon, dest_lat]],
        "instructions": False
    }
    headers = {
        "Authorization": ORS_KEY,
        "Content-Type": "application/json"
    }
    r = requests.post(url, json=body, headers=headers, timeout=12)
    r.raise_for_status()
    data = r.json()
    feat = data.get("features", [{}])[0]
    summary = feat.get("properties", {}).get("summary", {})
    duration_s = summary.get("duration")   # seconds
    distance_m = summary.get("distance")   # meters
    return (int(duration_s) if duration_s is not None else None,
            int(distance_m) if distance_m is not None else None)


@csrf_exempt
def predict_best_station_api(request):
    """
    POST JSON: { lat: float, lon: float, battery: float (0-100), fullRange: float, maxStations: int (optional) }
    Response JSON:
      {
        stations: [ { name, lat, lon, distance_km, route_time_min, predicted_time_min, navigation_url } ],
        best_station: { ... },
        model_used: True/False,
      }
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    try:
        data = json.loads(request.body.decode("utf-8"))
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        battery = float(data.get("battery"))
        full_range = float(data.get("fullRange"))
        max_stations = int(data.get("maxStations", 10))
    except Exception as e:
        return HttpResponseBadRequest("Invalid JSON or missing fields: " + str(e))

    # compute reachable radius in km from battery %
    max_km = (battery / 100.0) * full_range
    if max_km <= 0:
        return JsonResponse({"error": "Range computed <= 0. Check battery and fullRange inputs."}, status=400)

    # Query POIs (OpenChargeMap)
    try:
        pois = query_openchargemap(lat, lon, max_km, max_stations)
    except Exception as e:
        return JsonResponse({"error": "Failed to query OpenChargeMap: " + str(e)}, status=500)

    results = []
    model_flag = model_available()  # boolean if real model is available

    for poi in pois:
        try:
            addr = poi.get("AddressInfo", {})
            s_lat = float(addr.get("Latitude"))
            s_lon = float(addr.get("Longitude"))
            name = addr.get("Title") or poi.get("OperatorInfo", {}).get("Title") or "EV Station"

            # haversine straight-line distance (km)
            R = 6371.0
            dlat = math.radians(s_lat - lat)
            dlon = math.radians(s_lon - lon)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(s_lat)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance_km = R * c

            # route summary via ORS (duration seconds, distance meters)
            try:
                route_secs, route_m = get_route_summary_seconds(lat, lon, s_lat, s_lon)
            except Exception:
                # If ORS fails for a POI, skip ORS but keep straight-line distance
                route_secs, route_m = None, None

            route_mins = (route_secs / 60.0) if route_secs is not None else None

            # predict adjusted ETA using ML model (predict_eta has fallback if model missing)
            predicted_minutes = None
            try:
                if route_mins is not None:
                    # predict_eta will use current time automatically if hour/weekday not provided
                    predicted_minutes = predict_eta(distance_km, route_mins)
                else:
                    # if no route time available, try heuristic: distance / 40 km/h * 60
                    predicted_minutes = (distance_km / 40.0) * 60.0
            except Exception:
                predicted_minutes = None

            nav_url = f"https://www.google.com/maps/dir/?api=1&destination={s_lat},{s_lon}"

            results.append({
                "name": name,
                "lat": s_lat,
                "lon": s_lon,
                "distance_km": round(distance_km, 3),
                "route_time_min": round(route_mins, 2) if route_mins is not None else None,
                "predicted_time_min": round(predicted_minutes, 2) if predicted_minutes is not None else None,
                "navigation_url": nav_url
            })
        except Exception:
            # skip any malformed POI entries
            continue

    if not results:
        return JsonResponse({"stations": [], "message": "No stations found within range."})

    # sort by predicted_time_min if available, else route_time_min, else distance
    def sort_key(x):
        if x.get("predicted_time_min") is not None:
            return x["predicted_time_min"]
        if x.get("route_time_min") is not None:
            return x["route_time_min"]
        return x.get("distance_km", 9999)

    results_sorted = sorted(results, key=sort_key)
    best = results_sorted[0]

    return JsonResponse({
        "stations": results_sorted,
        "best_station": best,
        "model_used": model_flag
    })
