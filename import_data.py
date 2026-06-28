#!/usr/bin/env python3
"""
Скрипт для загрузки AIS-данных из Parquet в PostgreSQL с расширением PostGIS.
Читает файл historical_enriched.parquet и вставляет записи в таблицу ais_records.
"""

import pandas as pd
from sqlalchemy import create_engine, text
import os

# Подключение к БД (замените параметры на свои)
DATABASE_URL = "postgresql+psycopg2://vkr_user:vkr_password@localhost:5433/vkr_db"

def load_ais_data():
    """Загрузка данных из Parquet в PostgreSQL"""
    engine = create_engine(DATABASE_URL)
    # Проверка существования файла
    if not os.path.exists("data/historical_enriched.parquet"):
        print("Сначала запустите train.py")
        return
    # Чтение данных
    df = pd.read_parquet("data/historical_enriched.parquet")
    print(f"Загружено {len(df)} записей")
    # Подготовка днных для вставки
    # Преобразуем координаты в формат PostGIS (POINT)
    df['location'] = df.apply(
        lambda row: f"POINT({row.longitude} {row.latitude})", axis=1
    )
    with engine.connect() as conn:
        # Очистка таблицы (опционально)
        # conn.execute(text("TRUNCATE TABLE ais_records RESTART IDENTITY CASCADE"))
        # Пакетная вставка
        for idx, row in df.iterrows():
            insert_sql = """
                INSERT INTO ais_records (
                    mmsi, timestamp, location, sog, cog,
                    risk_score, wind_speed, wave_height, season, vessel_type
                ) VALUES (
                    :mmsi, :timestamp, ST_SetSRID(ST_GeomFromText(:location), 4326),
                    :sog, :cog, :risk_score, :wind_speed, :wave_height, :season, :vessel_type
                )
                ON CONFLICT (id) DO UPDATE SET
                    sog = EXCLUDED.sog,
                    cog = EXCLUDED.cog,
                    risk_score = EXCLUDED.risk_score,
                    wind_speed = EXCLUDED.wind_speed,
                    wave_height = EXCLUDED.wave_height,
                    season = EXCLUDED.season,
                    vessel_type = EXCLUDED.vessel_type
            """
            conn.execute(
                text(insert_sql),
                {
                    "mmsi": row.mmsi,
                    "timestamp": row.base_date_time,
                    "location": row.location,
                    "sog": row.sog,
                    "cog": row.cog,
                    "risk_score": row.risk_score,
                    "wind_speed": row.wind_speed,
                    "wave_height": row.wave_height,
                    "season": row.season,
                    "vessel_type": row.vessel_type
                }
            )
            if idx % 1000 == 0:
                print(f"Обработано {idx+1} записей")

        conn.commit()
        print("Загрузка завершена успешно!")

if __name__ == "__main__":
    load_ais_data()