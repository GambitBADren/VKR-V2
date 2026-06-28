from sqlalchemy import create_engine, text, Column, Integer, Float, DateTime, Date, func
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional, Tuple
import numpy as np
import math
from datetime import datetime

DATABASE_URL = "postgresql+psycopg2://vkr_user:vkr_password@localhost:5433/vkr_db"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(bind=engine)


class DatabaseRepository:
    """Репозиторий для работы с PostgreSQL + PostGIS"""

    def get_heatmap_data(
            self,
            source: str = "retrospective",
            grid_size: float = 0.1,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            start_hour: Optional[int] = None,
            end_hour: Optional[int] = None
    ) -> List[List]:
        """Получение данных для тепловой карты с фильтрацией по дате и часу"""
        print(
            f"get_heatmap_data: start_date={start_date}, end_date={end_date}, start_hour={start_hour}, end_hour={end_hour}")

        with SessionLocal() as session:
            if source == "retrospective":
                query = """
                    SELECT 
                        ROUND(ST_Y(location::geometry) / :grid_size) * :grid_size as lat,
                        ROUND(ST_X(location::geometry) / :grid_size) * :grid_size as lon,
                        AVG(risk_score) as intensity
                    FROM ais_records
                    WHERE 1=1
                """

                params = {"grid_size": grid_size}

                if start_date:
                    query += " AND timestamp >= CAST(:start_date AS timestamp)"
                    params["start_date"] = start_date

                if end_date:
                    query += " AND timestamp <= CAST(:end_date AS timestamp) + INTERVAL '1 day'"
                    params["end_date"] = end_date

                if start_hour is not None:
                    query += " AND EXTRACT(HOUR FROM timestamp) >= :start_hour"
                    params["start_hour"] = start_hour

                if end_hour is not None:
                    query += " AND EXTRACT(HOUR FROM timestamp) <= :end_hour"
                    params["end_hour"] = end_hour

                query += " GROUP BY lat, lon"

                result = session.execute(text(query), params)
            else:
                query = text("""
                    SELECT 
                        ROUND(ST_Y(location::geometry) / :grid_size) * :grid_size as lat,
                        ROUND(ST_X(location::geometry) / :grid_size) * :grid_size as lon,
                        COUNT(*) as intensity
                    FROM current_vessels
                    GROUP BY lat, lon
                """)
                result = session.execute(query, {"grid_size": grid_size})

            points = [[float(row.lat), float(row.lon), float(row.intensity)] for row in result]

            if points:
                max_intensity = max(p[2] for p in points)
                if max_intensity > 0:
                    points = [[p[0], p[1], p[2] / max_intensity] for p in points]

            return points

    def get_risk_zones(self) -> List[Dict]:
        """Получение зон риска"""
        with SessionLocal() as session:
            query = text("""
                SELECT 
                    id,
                    ST_Y(center::geometry) as lat,
                    ST_X(center::geometry) as lon,
                    radius_km,
                    avg_risk_score,
                    points_count
                FROM risk_zones
                ORDER BY avg_risk_score DESC
            """)
            result = session.execute(query)
            return [
                {
                    "id": row.id,
                    "center": {"lat": float(row.lat), "lon": float(row.lon)},
                    "radius_km": float(row.radius_km),
                    "avg_risk_score": float(row.avg_risk_score),
                    "points_count": int(row.points_count)
                }
                for row in result
            ]

    def get_maritime_corridors(self) -> List[Dict]:
        """Получение морских коридоров"""
        with SessionLocal() as session:
            query = text("""
                SELECT 
                    id,
                    ST_Y(center::geometry) as lat,
                    ST_X(center::geometry) as lon,
                    width_km,
                    traffic_count,
                    avg_speed
                FROM maritime_corridors
                ORDER BY traffic_count DESC
            """)
            result = session.execute(query)
            return [
                {
                    "id": row.id,
                    "center": {"lat": float(row.lat), "lon": float(row.lon)},
                    "width_km": float(row.width_km),
                    "traffic_count": int(row.traffic_count),
                    "avg_speed": float(row.avg_speed)
                }
                for row in result
            ]

    # --- ИСПРАВЛЕННЫЙ МЕТОД get_traffic_density ---
    def get_traffic_density(
        self,
        hour: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Получение данных о плотности трафика с фильтрацией по часу и дате"""
        with SessionLocal() as session:
            # Используем сырой SQL-запрос для гибкости
            sql = """
                SELECT 
                    ST_Y(center::geometry) as lat,
                    ST_X(center::geometry) as lon,
                    vessel_count as intensity,
                    hour_of_day as hour,
                    date
                FROM traffic_density
                WHERE 1=1
            """
            params = {}
            if hour is not None:
                sql += " AND hour_of_day = :hour"
                params["hour"] = hour
            if start_date is not None:
                sql += " AND date >= :start_date"
                params["start_date"] = start_date
            if end_date is not None:
                sql += " AND date <= :end_date"
                params["end_date"] = end_date

            result = session.execute(text(sql), params)
            rows = result.fetchall()
            traffic = []
            for row in rows:
                if row.lat is not None and row.lon is not None:
                    traffic.append({
                        "lat": float(row.lat),
                        "lon": float(row.lon),
                        "intensity": int(row.intensity),
                        "hour": row.hour,
                        "date": str(row.date) if row.date else None
                    })
            print(f"Traffic density: {len(traffic)} points")
            return traffic
    # --- КОНЕЦ ИСПРАВЛЕННОГО МЕТОДА ---

    def get_weather_for_point(self, lat: float, lon: float, date: Optional[str] = None) -> Dict:
        """Получение погодных условий для точки"""
        with SessionLocal() as session:
            query = """
                SELECT 
                    AVG(wind_speed) as avg_wind,
                    AVG(wave_height) as avg_wave,
                    AVG(risk_score) as avg_risk
                FROM ais_records
                WHERE ST_DWithin(
                    location,
                    ST_MakePoint(:lon, :lat)::geography,
                    10000
                )
            """
            params = {"lat": lat, "lon": lon}

            if date:
                query += " AND DATE(timestamp) = CAST(:date AS date)"
                params["date"] = date

            result = session.execute(text(query), params)
            row = result.one()

            return {
                "wind_speed": float(row.avg_wind) if row.avg_wind else 0,
                "wave_height": float(row.avg_wave) if row.avg_wave else 0,
                "risk_score": float(row.avg_risk) if row.avg_risk else 0
            }

    def get_nearby_records(
            self,
            lat: float,
            lon: float,
            radius_km: float = 10.0,
            limit: int = 100
    ) -> List[Dict]:
        """Поиск AIS-записей в радиусе"""
        with SessionLocal() as session:
            query = text("""
                SELECT 
                    id, mmsi, timestamp,
                    sog, cog, risk_score,
                    wind_speed, wave_height, season,
                    ST_Distance(
                        location, 
                        ST_MakePoint(:lon, :lat)::geography
                    ) as distance_m
                FROM ais_records
                WHERE ST_DWithin(
                    location,
                    ST_MakePoint(:lon, :lat)::geography,
                    :radius_m
                )
                ORDER BY distance_m
                LIMIT :limit
            """)
            result = session.execute(query, {
                "lat": lat,
                "lon": lon,
                "radius_m": radius_km * 1000,
                "limit": limit
            })
            return [
                {
                    "id": row.id,
                    "mmsi": int(row.mmsi),
                    "timestamp": str(row.timestamp),
                    "sog": float(row.sog) if row.sog else None,
                    "cog": float(row.cog) if row.cog else None,
                    "risk_score": float(row.risk_score) if row.risk_score else None,
                    "wind_speed": float(row.wind_speed) if row.wind_speed else None,
                    "wave_height": float(row.wave_height) if row.wave_height else None,
                    "season": row.season,
                    "distance_m": float(row.distance_m)
                }
                for row in result
            ]

    def predict_speed_at_point(
            self,
            lat: float,
            lon: float,
            vessel_type: str = "cargo",
            radius_km: float = 10.0
    ) -> float:
        """Предсказание скорости в точке"""
        nearby = self.get_nearby_records(lat, lon, radius_km, limit=50)

        if not nearby:
            base_speeds = {
                "cargo": 15, "tanker": 14, "passenger": 20,
                "fishing": 10, "tug": 12, "sports": 25, "small": 18
            }
            return float(base_speeds.get(vessel_type, 15))

        speeds = [r["sog"] for r in nearby if r["sog"] is not None]
        if speeds:
            return sum(speeds) / len(speeds)

        return 15.0

    def find_similar_situations(
            self,
            risk_score: float,
            wind_speed: float,
            wave_height: float,
            vessel_type: str = "cargo",
            season: str = "summer",
            k: int = 10
    ) -> Tuple[List[Dict], Optional[Dict]]:
        """Поиск похожих исторических ситуаций"""
        with SessionLocal() as session:
            query = text("""
                SELECT 
                    id, mmsi, timestamp,
                    sog, cog, risk_score,
                    wind_speed, wave_height, season,
                    ST_Y(location::geometry) as lat,
                    ST_X(location::geometry) as lon,
                    SQRT(
                        POWER((risk_score - :risk_score) / 1.0, 2) +
                        POWER((wind_speed - :wind_speed) / 20.0, 2) +
                        POWER((wave_height - :wave_height) / 5.0, 2) +
                        CASE WHEN season = :season THEN 0 ELSE 1 END
                    ) as similarity_distance
                FROM ais_records
                WHERE season = :season
                ORDER BY similarity_distance ASC
                LIMIT :k
            """)
            result = session.execute(query, {
                "risk_score": risk_score,
                "wind_speed": wind_speed,
                "wave_height": wave_height,
                "season": season,
                "k": k
            })

            situations = [
                {
                    "id": row.id,
                    "mmsi": int(row.mmsi),
                    "timestamp": str(row.timestamp),
                    "latitude": float(row.lat),
                    "longitude": float(row.lon),
                    "sog": float(row.sog) if row.sog else None,
                    "cog": float(row.cog) if row.cog else None,
                    "risk_score": float(row.risk_score) if row.risk_score else None,
                    "wind_speed": float(row.wind_speed) if row.wind_speed else None,
                    "wave_height": float(row.wave_height) if row.wave_height else None,
                    "season": row.season,
                    "similarity_distance": float(row.similarity_distance)
                }
                for row in result
            ]

            recommended = None
            if situations:
                min_risk_idx = min(range(len(situations)),
                                   key=lambda i: situations[i]["risk_score"] or float('inf'))
                recommended = situations[min_risk_idx]

            return situations, recommended

    def get_historical_stats(self) -> Dict:
        """Статистика по историческим данным"""
        with SessionLocal() as session:
            query = text("""
                SELECT 
                    AVG(risk_score) as avg_risk,
                    AVG(wind_speed) as avg_wind,
                    AVG(wave_height) as avg_wave,
                    COUNT(*) as total_records
                FROM ais_records
            """)
            result = session.execute(query)
            row = result.one()
            return {
                "avg_risk": float(row.avg_risk) if row.avg_risk else 0,
                "avg_wind": float(row.avg_wind) if row.avg_wind else 0,
                "avg_wave": float(row.avg_wave) if row.avg_wave else 0,
                "total_records": int(row.total_records)
            }