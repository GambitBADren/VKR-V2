import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, BigInteger, DateTime, text, select
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
DATABASE_URL = "postgresql+psycopg2://vkr_user:vkr_password@localhost:5433/vkr_db"
DATA_DIR = Path(__file__).parent.parent / "data"

Base = declarative_base()


# ==========================================
# 2. МОДЕЛИ
# ==========================================
class VesselType(Base):
    __tablename__ = "vessel_types"
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name_ru = Column(String(100), nullable=False)
    base_speed_knots = Column(Float, nullable=False)


class Vessel(Base):
    __tablename__ = "vessels"
    mmsi = Column(BigInteger, primary_key=True)
    vessel_type_id = Column(Integer, ForeignKey("vessel_types.id"))
    name = Column(String(255))


class AISRecord(Base):
    __tablename__ = "ais_records"
    id = Column(BigInteger, primary_key=True)
    mmsi = Column(BigInteger, ForeignKey("vessels.mmsi"), index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    location = Column(Geography("POINT", srid=4326), nullable=False)
    sog = Column(Float)
    cog = Column(Float)
    risk_score = Column(Float)
    wind_speed = Column(Float)
    wave_height = Column(Float)
    season = Column(String(10))


# ==========================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def get_season_from_date(date):
    """Определяем сезон по месяцу"""
    month = date.month if hasattr(date, 'month') else pd.Timestamp(date).month
    if month in [12, 1, 2]:
        return "winter"
    elif month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    else:
        return "autumn"


def generate_weather_data(lat, lon, season):
    """Генерируем реалистичные погодные данные на основе координат и сезона"""
    np.random.seed(hash((lat, lon, season)) % 2 ** 32)

    # Базовые значения для Дальнего Востока (Японское море)
    if season == "winter":
        wind_base = np.random.uniform(8, 20)  # м/с
        wave_base = np.random.uniform(2, 6)  # м
    elif season == "spring":
        wind_base = np.random.uniform(5, 15)
        wave_base = np.random.uniform(1, 4)
    elif season == "summer":
        wind_base = np.random.uniform(3, 12)
        wave_base = np.random.uniform(0.5, 3)
    else:  # autumn
        wind_base = np.random.uniform(7, 18)
        wave_base = np.random.uniform(1.5, 5)

    return wind_base, wave_base


def calculate_risk_score(sog, cog, wind_speed, wave_height, prev_sog=None, prev_cog=None):
    """
    Вычисляем интегральный риск по формулам из документации (Глава 2):
    R_man = |ΔCOG|/30 + |ΔSOG|/5
    R_weather = W/20 + H/5
    R_score = max(R_man, R_weather)
    """
    # Манёвренный риск
    if prev_sog is not None and prev_cog is not None:
        delta_cog = abs(cog - prev_cog) if cog is not None and prev_cog is not None else 0
        delta_sog = abs(sog - prev_sog) if sog is not None and prev_sog is not None else 0
        maneuver_risk = (delta_cog / 30.0) + (delta_sog / 5.0)
    else:
        maneuver_risk = 0.0

    # Погодный риск
    weather_risk = (wind_speed / 20.0) + (wave_height / 5.0)

    # Интегральный риск
    return max(maneuver_risk, weather_risk)


# ==========================================
# 4. ИМПОРТ ДАННЫХ
# ==========================================
def import_vessel_types(session):
    types = [
        {"id": 1, "code": "cargo", "name_ru": "Транспортное", "base_speed_knots": 15},
        {"id": 2, "code": "tanker", "name_ru": "Танкер", "base_speed_knots": 14},
        {"id": 3, "code": "passenger", "name_ru": "Пассажирское", "base_speed_knots": 20},
        {"id": 4, "code": "fishing", "name_ru": "Промысловое", "base_speed_knots": 10},
        {"id": 5, "code": "tug", "name_ru": "Буксир/служебное", "base_speed_knots": 12},
    ]

    for t in types:
        existing = session.execute(
            select(VesselType).where(VesselType.code == t["code"])
        ).scalar_one_or_none()

        if not existing:
            session.add(VesselType(**t))

    session.commit()
    print("✅ Типы судов добавлены")


def import_ais_data(session, df):
    print(f"📊 Импорт {len(df)} записей AIS...")

    # Словарь для хранения предыдущих значений (для расчёта риска)
    prev_values = {}  # mmsi -> {sog, cog}

    # 1. Добавляем уникальные суда
    unique_mmsi = df["mmsi"].unique()
    added_vessels = 0
    for mmsi in unique_mmsi:
        existing = session.execute(
            select(Vessel).where(Vessel.mmsi == int(mmsi))
        ).scalar_one_or_none()
        if not existing:
            session.add(Vessel(mmsi=int(mmsi), vessel_type_id=1, name=f"VESSEL_{mmsi % 1000}"))
            added_vessels += 1

    session.commit()
    print(f"✅ Добавлено {added_vessels} новых судов")

    # 2. Добавляем AIS записи
    batch = []
    success_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        try:
            # Получаем координаты
            lat = float(row["latitude"])
            lon = float(row["longitude"])

            # Пропускаем записи с невалидными координатами
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                continue

            # Создаём геометрию
            point = from_shape(Point(lon, lat), srid=4326)

            # Получаем timestamp (используем правильную колонку!)
            timestamp = row["base_date_time"]

            # Определяем сезон
            season = get_season_from_date(timestamp)

            # Генерируем погодные данные
            wind_speed, wave_height = generate_weather_data(lat, lon, season)

            # Получаем параметры движения
            sog = float(row.get("sog", 0)) if pd.notna(row.get("sog")) else 0
            cog = float(row.get("cog", 0)) if pd.notna(row.get("cog")) else 0

            # Вычисляем риск
            mmsi = int(row["mmsi"])
            risk_score = calculate_risk_score(
                sog, cog, wind_speed, wave_height,
                prev_sog=prev_values.get(mmsi, {}).get("sog"),
                prev_cog=prev_values.get(mmsi, {}).get("cog")
            )

            # Сохраняем текущие значения для следующей записи этого судна
            prev_values[mmsi] = {"sog": sog, "cog": cog}

            # Создаём запись
            record = AISRecord(
                mmsi=mmsi,
                timestamp=timestamp,
                location=point,
                sog=sog,
                cog=cog,
                risk_score=round(risk_score, 4),
                wind_speed=round(wind_speed, 2),
                wave_height=round(wave_height, 2),
                season=season
            )

            batch.append(record)
            success_count += 1

            # Пакетная вставка каждые 1000 записей
            if len(batch) >= 1000:
                session.add_all(batch)
                session.commit()
                print(
                    f"  ✓ Импортировано {idx + 1}/{len(df)} записей ({success_count} успешно, {error_count} пропущено)")
                batch = []

        except Exception as e:
            error_count += 1
            if error_count <= 5:  # Показываем только первые 5 ошибок
                print(f"  ⚠️  Ошибка на строке {idx}: {e}")
            continue

    # Добавляем остаток
    if batch:
        session.add_all(batch)
        session.commit()

    print(f"✅ AIS записи успешно импортированы!")
    print(f"   Всего обработано: {success_count + error_count}")
    print(f"   Успешно: {success_count}")
    print(f"   Ошибок: {error_count}")


def main():
    print("🚀 Запуск импорта в PostgreSQL...")

    # Проверяем наличие данных
    parquet_file = DATA_DIR / "synthetic_ais.parquet"
    if not parquet_file.exists():
        print(f"❌ Файл не найден: {parquet_file}")
        return
    else:
        print(f"✅ Найден файл: {parquet_file}")
        df = pd.read_parquet(parquet_file)

    # Подключение к БД
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        import_vessel_types(session)
        import_ais_data(session, df)

    print("\n🎉 ИМПОРТ ЗАВЕРШЁН!")
    print("💡 Проверьте данные в pgAdmin:")
    print("   SELECT COUNT(*) FROM ais_records;")
    print("   SELECT COUNT(*) FROM vessels;")


if __name__ == "__main__":
    main()