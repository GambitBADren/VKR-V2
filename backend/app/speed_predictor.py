import numpy as np
from sklearn.neighbors import KDTree
from geopy.distance import distance

class SpeedPredictor:
    def __init__(self, historical_df, default_speeds=None):
        self.df = historical_df
        coords = self.df[['latitude', 'longitude']].values
        self.kdtree = KDTree(coords, metric='euclidean')
        if default_speeds is None:
            self.default_speeds = {
                'cargo': 15,
                'tanker': 14,
                'passenger': 20,
                'fishing': 12,
                'tug': 10,
                'other': 15
            }
        else:
            self.default_speeds = default_speeds

    def predict_speed(self, lat, lon, vessel_type, wind_speed, wave_height, season, radius_km=10):
        radius_deg = radius_km / 111.0
        indices = self.kdtree.query_radius([[lat, lon]], r=radius_deg)[0]
        if len(indices) == 0:
            return self.default_speeds.get(vessel_type, 15)
        subdf = self.df.iloc[indices]
        # Фильтр по типу судна (если есть)
        subdf = subdf[subdf['vessel_type'].apply(lambda x: x == vessel_type)]
        if len(subdf) == 0:
            return self.default_speeds.get(vessel_type, 15)
        mean_speed = subdf['actual_sog'].mean()
        return float(mean_speed)
