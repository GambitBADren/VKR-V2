"""
Запуск DBSCAN на AIS-данных из PostgreSQL для выявления зон риска.
Результат сохраняется в таблицу risk_zones.
"""
import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy import create_engine, text
from pathlib import Path

# Подключение к БД
DATABASE_URL = "postgresql+psycopg2://vkr_user:vkr_password@localhost:5433/vkr_db"


def run_dbscan_on_risk_points():
    """Запуск DBSCAN на точках с высоким риском"""
    print("🚀 Запуск DBSCAN для выявления зон риска...")

    engine = create_engine(DATABASE_URL)

    # 1. Загружаем точки с высоким риском из БД
    print("📊 Загрузка точек с risk_score > 0.5...")
    query = text("""
        SELECT 
            id,
            ST_Y(location::geometry) as lat,
            ST_X(location::geometry) as lon,
            risk_score
        FROM ais_records
        WHERE risk_score > 0.5
        LIMIT 50000
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()

    if not rows:
        print("⚠️  Точек с высоким риском не найдено!")
        return

    print(f"✅ Загружено {len(rows)} точек")

    # 2. Преобразуем в numpy array
    coords = np.array([[row.lat, row.lon] for row in rows])
    risk_scores = np.array([row.risk_score for row in rows])

    # 3. Запускаем DBSCAN
    # ε = 20 км ≈ 0.18° (приблизительно)
    # minPts = 5 (согласно REQ_D_04)
    print("🔍 Запуск DBSCAN (eps=0.18°, minPts=5)...")

    # Используем метрику haversine для географических координат
    # Переводим координаты в радианы
    coords_rad = np.radians(coords)

    # eps в радианах: 20 км / 6371 км (радиус Земли)
    eps_rad = 20.0 / 6371.0

    db = DBSCAN(eps=eps_rad, min_samples=5, metric='haversine')
    labels = db.fit_predict(coords_rad)

    # 4. Анализируем результаты
    unique_labels = set(labels)
    n_clusters = len(unique_labels - {-1})
    n_noise = list(labels).count(-1)

    print(f"✅ Найдено кластеров: {n_clusters}")
    print(f"⚠️  Шумовых точек: {n_noise}")

    # 5. Сохраняем кластеры в БД
    print("💾 Сохранение зон риска в БД...")

    with engine.connect() as conn:
        # Очищаем старые зоны
        conn.execute(text("DELETE FROM risk_zones"))

        for cluster_id in range(n_clusters):
            mask = labels == cluster_id
            cluster_coords = coords[mask]
            cluster_risks = risk_scores[mask]

            # Центр кластера
            center_lat = float(np.mean(cluster_coords[:, 0]))
            center_lon = float(np.mean(cluster_coords[:, 1]))

            # Радиус (максимальное расстояние от центра до точки)
            center_point = np.array([center_lat, center_lon])
            distances = np.linalg.norm(cluster_coords - center_point, axis=1)
            radius_deg = float(np.max(distances))
            radius_km = radius_deg * 111.0  # приблизительно

            # Средний риск
            avg_risk = float(np.mean(cluster_risks))

            # Количество точек
            points_count = int(np.sum(mask))

            # Вставляем в БД
            insert_query = text("""
                INSERT INTO risk_zones (center, radius_km, avg_risk_score, points_count)
                VALUES (
                    ST_MakePoint(:lon, :lat)::geography,
                    :radius,
                    :risk,
                    :count
                )
            """)

            conn.execute(insert_query, {
                "lat": center_lat,
                "lon": center_lon,
                "radius": radius_km,
                "risk": avg_risk,
                "count": points_count
            })

        conn.commit()

    print(f"\n🎉 Готово! Сохранено {n_clusters} зон риска в таблицу risk_zones")
    print("💡 Теперь endpoint /api/risk_zones будет возвращать реальные зоны")


if __name__ == "__main__":
    run_dbscan_on_risk_points()