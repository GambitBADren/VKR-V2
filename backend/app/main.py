from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Dict, List, Optional
import numpy as np
from geopy.distance import distance
from app.config import MIN_LAT, MAX_LAT, MIN_LON, MAX_LON, GRID_STEP_M
from app.router import MaritimeRouter
from app.repositories.db_repository import DatabaseRepository, SessionLocal
from sqlalchemy import text
from pathlib import Path
# --- ИМПОРТЫ ДЛЯ АВТОРИЗАЦИИ ---
from app.auth import (
    UserCreate, UserLogin, Token, UserResponse,
    get_password_hash, verify_password, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from datetime import timedelta
import os

from app.config import USE_DATABASE
from app.repositories.file_repository import FileRepository

# Глобальные переменные
router = None
db_repo = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global router, db_repo

    if USE_DATABASE:
        try:
            db_repo = DatabaseRepository()
            print("✅ Database repository initialized (PostgreSQL)")
        except Exception as e:
            print(f"❌ Failed to initialize database repository: {e}")
            db_repo = None
    else:
        try:
            db_repo = FileRepository()
            print("✅ File repository initialized (Parquet/JSON)")
        except Exception as e:
            print(f"❌ Failed to initialize file repository: {e}")
            db_repo = None

    router = MaritimeRouter(MIN_LAT, MAX_LAT, MIN_LON, MAX_LON, step_m=GRID_STEP_M)
    print("✅ Maritime router initialized")
    print("🚀 Application startup complete.")

    yield
    print("👋 Application shutting down...")


app = FastAPI(title="Maritime Route Optimization API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Point(BaseModel):
    lat: float
    lon: float


class RouteRequest(BaseModel):
    start: Point
    end: Point
    waypoints: Optional[List[Point]] = None
    vessel_type: str = "cargo"
    optimization: str = "time"
    wind_speed: float = 15.0
    wave_height: float = 2.5
    season: int = 1
    date: Optional[str] = None
    hour: Optional[int] = None


class SimilarRequest(BaseModel):
    risk_score: float
    wind_speed: float
    wave_height: float
    vessel_type: str
    season: int
    k: int = 5


class AnalyzeRequest(BaseModel):
    segments: List[Dict]
    vessel_type: str


def build_full_path(start, waypoints, end):
    points = [(start.lat, start.lon)]
    if waypoints:
        points.extend([(wp.lat, wp.lon) for wp in waypoints])
    points.append((end.lat, end.lon))
    return points


def season_int_to_str(season_int: int) -> str:
    """Преобразование номера сезона в строку"""
    seasons = {1: "winter", 2: "spring", 3: "summer", 4: "autumn"}
    return seasons.get(season_int, "summer")


@app.post("/api/route")
async def get_route(req: RouteRequest):
    if router is None:
        raise HTTPException(status_code=500, detail="Router not initialized")

    full_points = build_full_path(req.start, req.waypoints, req.end)
    all_segments = []
    total_dist = 0

    weather_risk = min(1.0, (req.wind_speed / 25.0 + req.wave_height / 8.0) / 2.0)

    risk_zones = []
    if db_repo:
        try:
            risk_zones = db_repo.get_risk_zones()
        except Exception as e:
            print(f"Warning: Could not load risk zones: {e}")

    for i in range(len(full_points) - 1):
        start = full_points[i]
        end = full_points[i + 1]

        def speed_predictor_fn(lat, lon, vessel_type, wind_speed, wave_height, season):
            if db_repo:
                try:
                    return db_repo.predict_speed_at_point(lat, lon, vessel_type, radius_km=10.0)
                except:
                    pass
            return 15.0

        path = router.route(
            start, end,
            speed_predictor=speed_predictor_fn,
            risk_zones=risk_zones,
            optimization=req.optimization,
            vessel_type=req.vessel_type,
            wind_speed=req.wind_speed,
            wave_height=req.wave_height,
            season=req.season
        )

        if path is None:
            raise HTTPException(status_code=404, detail=f"No route found between {start} and {end}")

        for j in range(len(path) - 1):
            p1 = path[j]
            p2 = path[j + 1]
            dist = distance(p1, p2).km
            total_dist += dist

            center_lat = (p1[0] + p2[0]) / 2
            center_lon = (p1[1] + p2[1]) / 2

            # Получаем погодные условия для сегмента
            weather_data = {}
            if db_repo:
                try:
                    weather_data = db_repo.get_weather_for_point(
                        center_lat, center_lon, req.date
                    )
                except:
                    pass

            predicted_speed = speed_predictor_fn(
                center_lat, center_lon, req.vessel_type,
                req.wind_speed, req.wave_height, req.season
            )

            all_segments.append({
                "start": {"lat": p1[0], "lon": p1[1]},
                "end": {"lat": p2[0], "lon": p2[1]},
                "distance_km": dist,
                "recommended_speed_knots": predicted_speed,
                "risk_level": weather_risk,
                "course_deg": np.arctan2(p2[1] - p1[1], p2[0] - p1[0]) * 180 / np.pi,
                "warning": "High waves" if req.wave_height > 4 else None,
                "weather": weather_data
            })

    return {
        "segments": all_segments,
        "total_distance_km": total_dist,
        "optimization": req.optimization
    }


@app.post("/api/similar")
async def find_similar(req: SimilarRequest):
    if db_repo is None:
        raise HTTPException(status_code=500, detail="Database repository not initialized")

    season_str = season_int_to_str(req.season)

    try:
        situations, recommended = db_repo.find_similar_situations(
            risk_score=req.risk_score,
            wind_speed=req.wind_speed,
            wave_height=req.wave_height,
            vessel_type=req.vessel_type,
            season=season_str,
            k=req.k
        )

        distances = [s["similarity_distance"] for s in situations]

        return {
            "similar_situations": situations,
            "distances": distances,
            "recommended": recommended
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding similar situations: {e}")


@app.post("/api/analyze_route")
async def analyze_route(req: AnalyzeRequest):
    if db_repo is None:
        raise HTTPException(status_code=500, detail="Database repository not initialized")

    try:
        stats = db_repo.get_historical_stats()

        import datetime
        current_season = (datetime.datetime.now().month % 12 // 3) + 1
        season_str = season_int_to_str(current_season)

        situations, recommended = db_repo.find_similar_situations(
            risk_score=stats["avg_risk"],
            wind_speed=stats["avg_wind"],
            wave_height=stats["avg_wave"],
            vessel_type=req.vessel_type,
            season=season_str,
            k=5
        )

        return {
            "avg_risk": stats["avg_risk"],
            "avg_wind": stats["avg_wind"],
            "avg_wave": stats["avg_wave"],
            "similar_count": len(situations),
            "best_match": recommended
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing route: {e}")


@app.get("/api/risk_zones")
async def get_risk_zones():
    if db_repo is None:
        return {"zones": []}

    try:
        zones = db_repo.get_risk_zones()
        return {"zones": zones}
    except Exception as e:
        print(f"Error loading risk zones: {e}")
        return {"zones": []}


@app.get("/api/maritime_corridors")
async def get_maritime_corridors():
    if db_repo is None:
        return {"corridors": []}

    try:
        corridors = db_repo.get_maritime_corridors()
        return {"corridors": corridors}
    except Exception as e:
        print(f"Error loading corridors: {e}")
        return {"corridors": []}


@app.get("/api/traffic_density")
async def get_traffic_density(
    hour: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    if db_repo is None:
        return {"traffic": []}
    try:
        traffic = db_repo.get_traffic_density(hour, start_date, end_date)
        return {"traffic": traffic}
    except Exception as e:
        print(f"Error loading traffic density: {e}")
        return {"traffic": []}


@app.get("/api/land.geojson")
async def get_land_geojson():
    try:
        # Абсолютный путь: backend/app/main.py → parent.parent.parent = корень проекта
        project_root = Path(__file__).resolve().parent.parent.parent
        land_file = project_root / "data" / "land_polygons_far_east.geojson"

        if not land_file.exists():
            print(f"❌ Файл не найден: {land_file}")
            return {"error": f"Land polygons file not found: {land_file}"}

        return FileResponse(str(land_file), media_type="application/json")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"error": str(e)}


@app.get("/api/heatmap_data")
async def get_heatmap_data(
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        start_hour: Optional[int] = Query(None),
        end_hour: Optional[int] = Query(None)
):
    if db_repo is None:
        return {"points": []}

    try:
        points = db_repo.get_heatmap_data(
            source="retrospective",
            grid_size=0.1,
            start_date=start_date,
            end_date=end_date,
            start_hour=start_hour,
            end_hour=end_hour
        )
        return {"points": points}
    except Exception as e:
        print(f"Error loading heatmap data: {e}")
        return {"points": []}


@app.get("/api/current_vessels")
async def get_current_vessels():
    if db_repo is None:
        return {"vessels": []}

    try:
        vessels = db_repo.get_current_vessels()
        return {"vessels": vessels}
    except Exception as e:
        print(f"Error loading current vessels: {e}")
        return {"vessels": []}


@app.get("/api/current_heatmap_data")
async def get_current_heatmap_data():
    if db_repo is None:
        return {"points": []}

    try:
        points = db_repo.get_heatmap_data(source="current_vessels", grid_size=0.1)
        return {"points": points}
    except Exception as e:
        print(f"Error loading current heatmap data: {e}")
        return {"points": []}


@app.get("/api/available_dates")
async def get_available_dates():
    if db_repo is None:
        return {"dates": []}

    try:
        with SessionLocal() as session:
            query = text("""
                SELECT DISTINCT DATE(timestamp) as date
                FROM ais_records
                ORDER BY date DESC
            """)
            result = session.execute(query)
            dates = [str(row.date) for row in result]

        return {"dates": dates}
    except Exception as e:
        print(f"Error loading available dates: {e}")
        return {"dates": []}





# --- ENDPOINTS АВТОРИЗАЦИИ ---

@app.post("/api/register", response_model=UserResponse)
async def register(user: UserCreate):
    with SessionLocal() as session:
        # Проверка уникальности
        existing = session.execute(text("SELECT id FROM users WHERE username = :u OR email = :e"),
                                   {"u": user.username, "e": user.email}).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username or email already registered")

        hashed_pwd = get_password_hash(user.password)
        session.execute(
            text("INSERT INTO users (username, email, password_hash, role) VALUES (:u, :e, :p, :r)"),
            {"u": user.username, "e": user.email, "p": hashed_pwd, "r": user.role}
        )
        session.commit()

        result = session.execute(text("SELECT id, username, email, role FROM users WHERE username = :u"),
                                 {"u": user.username}).fetchone()
        return {"id": result.id, "username": result.username, "email": result.email, "role": result.role}


@app.post("/api/login", response_model=Token)
async def login(user: UserLogin):
    with SessionLocal() as session:
        result = session.execute(text("SELECT username, password_hash, role FROM users WHERE username = :u"),
                                 {"u": user.username}).fetchone()
        if not result or not verify_password(user.password, result.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": result.username, "role": result.role}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer", "role": result.role}


@app.get("/api/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


# Защищенный endpoint (пример для специалиста)
@app.get("/api/specialist/data")
async def get_specialist_data(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "specialist":
        raise HTTPException(status_code=403, detail="Only specialists can access this")
    return {"message": "Secret specialist data", "user": current_user["username"]}


@app.get("/api/available_dates")
async def get_available_dates():
    """Получить список дат, за которые есть данные"""
    if db_repo is None:
        return {"dates": []}

    try:
        with SessionLocal() as session:
            query = text("""
                SELECT DISTINCT DATE(timestamp) as date, COUNT(*) as count
                FROM ais_records
                GROUP BY date
                ORDER BY date DESC
            """)
            result = session.execute(query)
            dates = [{"date": str(row.date), "count": row.count} for row in result]

        return {"dates": dates}
    except Exception as e:
        print(f"Error loading available dates: {e}")
        return {"dates": []}


# ============================================================
# ENDPOINTS ДЛЯ СПЕЦИАЛИСТОВ (ADMIN)
# ============================================================

@app.get("/api/admin/statistics")
async def get_system_statistics(current_user: dict = Depends(get_current_user)):
    """Статистика системы (только для специалистов)"""
    if current_user["role"] != "specialist":
        raise HTTPException(status_code=403, detail="Доступ только для специалистов")

    try:
        with SessionLocal() as session:
            stats = {}

            # Количество AIS-записей
            stats["ais_records"] = session.execute(text("SELECT COUNT(*) FROM ais_records")).scalar()

            # Количество зон риска
            stats["risk_zones"] = session.execute(text("SELECT COUNT(*) FROM risk_zones")).scalar()

            # Количество коридоров
            stats["corridors"] = session.execute(text("SELECT COUNT(*) FROM maritime_corridors")).scalar()

            # Количество точек трафика
            stats["traffic_points"] = session.execute(text("SELECT COUNT(*) FROM traffic_density")).scalar()

            # Количество пользователей
            stats["users"] = session.execute(text("SELECT COUNT(*) FROM users")).scalar()

            # Диапазон дат
            result = session.execute(text("""
                SELECT MIN(timestamp)::date, MAX(timestamp)::date 
                FROM ais_records
            """)).fetchone()
            stats["date_range"] = {
                "min": str(result[0]) if result[0] else None,
                "max": str(result[1]) if result[1] else None
            }

            return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@app.post("/api/admin/recalculate_risk_zones")
async def recalculate_risk_zones(current_user: dict = Depends(get_current_user)):
    """Пересчёт зон риска через DBSCAN (только для специалистов)"""
    if current_user["role"] != "specialist":
        raise HTTPException(status_code=403, detail="Доступ только для специалистов")

    import subprocess
    import os

    try:
        # Скрипт лежит в папке backend
        script_path = os.path.join(os.path.dirname(__file__), "..", "run_dbscan.py")
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 минут максимум
        )

        if result.returncode == 0:
            return {"status": "success", "message": "Зоны риска успешно пересчитаны", "output": result.stdout}
        else:
            raise HTTPException(status_code=500, detail=f"Ошибка выполнения: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Превышено время выполнения (5 минут)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.post("/api/admin/recalculate_corridors")
async def recalculate_corridors(current_user: dict = Depends(get_current_user)):
    """Пересчёт морских коридоров (только для специалистов)"""
    if current_user["role"] != "specialist":
        raise HTTPException(status_code=403, detail="Доступ только для специалистов")

    import subprocess
    import os

    try:
        script_path = os.path.join(os.path.dirname(__file__), "generate_corridors.py")
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            return {"status": "success", "message": "Морские коридоры успешно пересчитаны", "output": result.stdout}
        else:
            raise HTTPException(status_code=500, detail=f"Ошибка выполнения: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Превышено время выполнения (5 минут)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.post("/api/admin/recalculate_traffic")
async def recalculate_traffic(current_user: dict = Depends(get_current_user)):
    """Пересчёт плотности трафика (только для специалистов)"""
    if current_user["role"] != "specialist":
        raise HTTPException(status_code=403, detail="Доступ только для специалистов")

    import subprocess
    import os

    try:
        script_path = os.path.join(os.path.dirname(__file__), "generate_traffic.py")
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            return {"status": "success", "message": "Плотность трафика успешно пересчитана", "output": result.stdout}
        else:
            raise HTTPException(status_code=500, detail=f"Ошибка выполнения: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Превышено время выполнения (5 минут)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.get("/api/admin/users")
async def get_users_list(current_user: dict = Depends(get_current_user)):
    """Список пользователей (только для специалистов)"""
    if current_user["role"] != "specialist":
        raise HTTPException(status_code=403, detail="Доступ только для специалистов")

    try:
        with SessionLocal() as session:
            result = session.execute(text("""
                SELECT id, username, email, role, created_at 
                FROM users 
                ORDER BY created_at DESC
            """))
            users = [
                {
                    "id": row.id,
                    "username": row.username,
                    "email": row.email,
                    "role": row.role,
                    "created_at": str(row.created_at)
                }
                for row in result
            ]
            return {"users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.get("/api/russia_border.geojson")
async def get_russia_border():
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        file_path = project_root / "data" / "russia_border.geojson"
        if not file_path.exists():
            return {"error": "Russia border file not found"}
        return FileResponse(str(file_path), media_type="application/json")
    except Exception as e:
        return {"error": str(e)}