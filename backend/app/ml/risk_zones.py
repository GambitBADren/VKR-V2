import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from geopy.distance import distance
import json

def cluster_risk_zones(df: pd.DataFrame, risk_threshold=0.7, eps_km=20, min_samples=5):
    high_risk = df[df['risk_score'] >= risk_threshold].copy()
    if len(high_risk) < min_samples:
        print("Недостаточно точек для кластеризации")
        return []
    coords = high_risk[['latitude', 'longitude']].values
    coords_rad = np.radians(coords)
    db = DBSCAN(eps=eps_km / 6371.0, min_samples=min_samples, metric='haversine')
    labels = db.fit_predict(coords_rad)
    zones = []
    for label in set(labels):
        if label == -1:
            continue
        cluster_points = coords[labels == label]
        center_lat = np.mean(cluster_points[:, 0])
        center_lon = np.mean(cluster_points[:, 1])
        max_dist = 0
        for pt in cluster_points:
            d = distance((center_lat, center_lon), (pt[0], pt[1])).km
            if d > max_dist:
                max_dist = d
        avg_risk = high_risk[labels == label]['risk_score'].mean()
        zones.append({
            "center": [float(center_lat), float(center_lon)],
            "radius_km": float(max_dist),
            "avg_risk": float(avg_risk)
        })
    return zones

def save_zones(zones, path="data/risk_zones.json"):
    with open(path, "w") as f:
        json.dump(zones, f)

def load_zones(path="data/risk_zones.json"):
    with open(path, "r") as f:
        return json.load(f)