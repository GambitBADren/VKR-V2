import numpy as np
import pandas as pd

def add_meteo_data(df: pd.DataFrame) -> pd.DataFrame:
    df['month'] = pd.DatetimeIndex(df['base_date_time']).month
    df['season'] = (df['month'] % 12 // 3).astype(int)
    lat_min, lat_max = df['latitude'].min(), df['latitude'].max()
    lat_norm = (df['latitude'] - lat_min) / (lat_max - lat_min)
    wind_base = 5 + 15 * lat_norm
    season_factor = 1 + 0.5 * (df['season'] == 3).astype(float)
    wind_speed = wind_base * season_factor + np.random.normal(0, 2, size=len(df))
    wind_speed = np.clip(wind_speed, 0, 30)
    wave_height = 0.25 * wind_speed + np.random.normal(0, 0.5, size=len(df))
    wave_height = np.clip(wave_height, 0, 8)
    current_speed = np.random.uniform(0, 3, size=len(df))
    df['wind_speed'] = wind_speed
    df['wave_height'] = wave_height
    df['current_speed'] = current_speed
    return df