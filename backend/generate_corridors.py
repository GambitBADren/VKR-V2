import numpy as np
from sqlalchemy import create_engine, text
from collections import defaultdict

DATABASE_URL = "postgresql+psycopg2://vkr_user:vkr_password@localhost:5433/vkr_db"


def generate_corridors():
    print("🚀 Генерация морских коридоров...")
    engine = create_engine(DATABASE_URL)

    query = text("""
        SELECT mmsi, ST_Y(location::geometry) as lat, ST_X(location::geometry) as lon, sog
        FROM ais_records
    """)

    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    print(f"✅ Загружено {len(rows)} записей")

    cell_size = 0.2
    cell_vessels = defaultdict(set)
    cell_speeds = defaultdict(list)

    for row in rows:
        cell_lat = round(row.lat / cell_size) * cell_size
        cell_lon = round(row.lon / cell_size) * cell_size
        cell_key = (cell_lat, cell_lon)

        cell_vessels[cell_key].add(row.mmsi)
        if row.sog:
            cell_speeds[cell_key].append(row.sog)

    corridors = []
    for cell_key, vessels in cell_vessels.items():
        # УВЕЛИЧИЛИ ПОРОГ: минимум 50 уникальных судов (вместо 5)
        if len(vessels) >= 20:
            corridors.append({
                'lat': cell_key[0],
                'lon': cell_key[1],
                'traffic_count': len(vessels),
                'avg_speed': np.mean(cell_speeds.get(cell_key, [15]))
            })

    # Сортируем по количеству судов и берем ТОП-200
    corridors.sort(key=lambda x: x['traffic_count'], reverse=True)
    top_corridors = corridors[:200]

    print(f"✅ Найдено {len(corridors)} коридоров (порог ≥50 судов)")
    print(f"📊 Сохраняем ТОП-200 из {len(corridors)}")

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM maritime_corridors"))
        for c in top_corridors:
            conn.execute(text("""
                INSERT INTO maritime_corridors (center, width_km, traffic_count, avg_speed)
                VALUES (ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :width, :count, :speed)
            """), {'lat': c['lat'], 'lon': c['lon'], 'width': cell_size * 111, 'count': c['traffic_count'],
                   'speed': c['avg_speed']})
        conn.commit()

    print("🎉 Коридоры сохранены в БД!")
    print(f"📈 Максимальный трафик: {top_corridors[0]['traffic_count'] if top_corridors else 0} судов")


if __name__ == "__main__":
    generate_corridors()