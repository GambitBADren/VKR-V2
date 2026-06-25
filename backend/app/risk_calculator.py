import numpy as np
import pandas as pd

def compute_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(['mmsi', 'base_date_time']).reset_index(drop=True)
    df['prev_cog'] = df.groupby('mmsi')['cog'].shift(1)
    df['prev_sog'] = df.groupby('mmsi')['sog'].shift(1)
    diff_cog = np.abs(df['cog'] - df['prev_cog'])
    diff_cog = np.minimum(diff_cog, 360 - diff_cog)
    risk_maneuver_cog = np.minimum(1, diff_cog / 30)
    diff_sog = np.abs(df['sog'] - df['prev_sog'])
    risk_maneuver_sog = np.minimum(1, diff_sog / 5)
    risk_maneuver = np.maximum(risk_maneuver_cog, risk_maneuver_sog).fillna(0)
    risk_weather = (df['wind_speed'] / 25 + df['wave_height'] / 8) / 2
    risk_weather = np.clip(risk_weather, 0, 1)
    df['risk_score'] = np.maximum(risk_maneuver, risk_weather)
    df = df.drop(columns=['prev_cog', 'prev_sog'])
    return df