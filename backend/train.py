#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
from geopy.distance import distance
from scipy.spatial import cKDTree
from tqdm import tqdm

# Создаём папки для данных и моделей
os.makedirs("data", exist_ok=True)
os.makedirs("models", exist_ok=True)

from app.synthetic_ais import generate_ais_dataset
from app.meteo import add_meteo_data
from app.risk_calculator import compute_risk_score
from app.ml.risk_zones import cluster_risk_zones, save_zones
from app.ml.similarity import SimilaritySearch
from app.config import CONGESTION_RADIUS_KM, CONGESTION_TIME_WINDOW_MIN
from app.coastline import is_land


def add_congestion_score_optimized(df, radius_km=5, time_window_min=30):
    print("   Индексация данных для расчёта загруженности...")
    df['timestamp_seconds'] = df['base_date_time'].astype('int64') // 10 ** 9
    df = df.sort_values('timestamp_seconds').reset_index(drop=True)
    window_sec = time_window_min * 60
    df['congestion_score'] = 0.0
    time_start = df['timestamp_seconds'].min()
    time_end = df['timestamp_seconds'].max()
    interval = window_sec
    num_intervals = int((time_end - time_start) // interval) + 2
    print(f"   Расчёт загруженности по временным интервалам (интервал = {time_window_min} мин)...")
    for idx in tqdm(range(num_intervals), desc="   Обработка интервалов"):
        t_low = time_start + idx * interval
        t_high = t_low + interval
        mask = (df['timestamp_seconds'] >= t_low) & (df['timestamp_seconds'] < t_high)
        if not mask.any():
            continue
        subdf = df[mask].copy()
        coords = subdf[['latitude', 'longitude']].values
        tree = cKDTree(coords)
        radius_deg = radius_km / 111.0
        for i, row in subdf.iterrows():
            neighbors = tree.query_ball_point([row['latitude'], row['longitude']], radius_deg, p=2)
            count = len(neighbors) - 1
            df.loc[i, 'congestion_score'] = min(1.0, count / 10)
    print("   Загруженность рассчитана.")
    return df


def filter_land_points(df):
    print("   Фильтрация точек на суше...")
    tqdm.pandas(desc="   Проверка суши")
    df['is_on_land'] = df.progress_apply(lambda row: is_land(row['latitude'], row['longitude']), axis=1)
    filtered_df = df[df['is_on_land'] == False].copy()
    filtered_df.drop(columns=['is_on_land'], inplace=True)
    print(f"   Удалено {len(df) - len(filtered_df)} точек на суше, осталось {len(filtered_df)}")
    return filtered_df


def main():
    print("1. Генерация синтетических AIS-записей...")
    df = generate_ais_dataset()
    print("   Фильтрация точек на суше...")
    df = filter_land_points(df)
    df.to_parquet("data/synthetic_ais.parquet", index=False)

    print("2. Добавление метеоданных...")
    df = add_meteo_data(df)

    print("3. Вычисление risk_score...")
    df = compute_risk_score(df)

    print("4. Вычисление загруженности акватории...")
    df = add_congestion_score_optimized(df, radius_km=CONGESTION_RADIUS_KM, time_window_min=CONGESTION_TIME_WINDOW_MIN)

    print("5. Сохранение обогащённых данных...")
    df.to_parquet("data/historical_enriched.parquet", index=False)

    # Убеждаемся, что поле actual_sog существует (оно есть как 'sog')
    df['actual_sog'] = df['sog']  # для ясности

    print("6. Кластеризация зон риска DBSCAN...")
    zones = cluster_risk_zones(df, risk_threshold=0.7, eps_km=20, min_samples=5)
    save_zones(zones, "data/risk_zones.json")
    print(f"   Найдено зон: {len(zones)}")

    print("7. Обучение k-NN модели...")
    sim = SimilaritySearch(k=5)
    sim.fit(df)
    sim.save("models/knn_model.joblib")

    print("Готово! Модели сохранены.")


if __name__ == "__main__":
    main()