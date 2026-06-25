import numpy as np
from sqlalchemy import create_engine, text
from collections import defaultdict

DATABASE_URL = "postgresql+psycopg2://vkr_user:vkr_password@localhost:5433/vkr_db"


def generate_traffic():
    print("🚀 Генерация плотности трафика...")
    engine = create_engine(DATABASE_URL)

    query = text("""
        SELECT mmsi, EXTRACT(HOUR FROM timestamp) as hour,
               ST_Y(location::geometry) as lat, ST_X(location::geometry) as lon, sog
        FROM ais_records
    """)

    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    print(f"✅ Загружено {len(rows)} записей")

    cell_size = 0.2
    traffic_data = defaultdict(lambda: {'vessels': set(), 'speeds': []})

    for row in rows:
        cell_lat = round(row.lat / cell_size) * cell_size
        cell_lon = round(row.lon / cell_size) * cell_size
        cell_key = (cell_lat, cell_lon, int(row.hour))

        traffic_data[cell_key]['vessels'].add(row.mmsi)
        if row.sog:
            traffic_data[cell_key]['speeds'].append(row.sog)

    traffic_records = []
    for (lat, lon, hour), data in traffic_data.items():
        if len(data['vessels']) >= 3:
            traffic_records.append({
                'lat': lat, 'lon': lon, 'hour': hour,
                'vessel_count': len(data['vessels']),
                'avg_speed': np.mean(data['speeds']) if data['speeds'] else 15.0
            })

    print(f"✅ Найдено {len(traffic_records)} точек трафика")

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM traffic_density"))
        for r in traffic_records:
            # ИСПРАВЛЕНО: используем ST_SetSRID вместо ::geography
            conn.execute(text("""
                INSERT INTO traffic_density (center, hour_of_day, vessel_count, avg_speed)
                VALUES (ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :hour, :count, :speed)
            """), {'lat': r['lat'], 'lon': r['lon'], 'hour': r['hour'], 'count': r['vessel_count'],
                   'speed': r['avg_speed']})
        conn.commit()

    print("🎉 Трафик сохранен в БД!")


if __name__ == "__main__":
    generate_traffic()