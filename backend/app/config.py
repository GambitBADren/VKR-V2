import os
from dotenv import load_dotenv

load_dotenv()

# Географические границы Дальнего Востока (только восточная долгота)
MIN_LAT = 42.5
MAX_LAT = 66.1
MIN_LON = 130.0
MAX_LON = 180.0

# Параметры синтетических данных
NUM_AIS_RECORDS = 350_000

# Параметры сетки для графа (20 км)
GRID_STEP_M = 20_000

# ML параметры
RISK_ZONE_THRESHOLD = 0.7
DBSCAN_EPS_KM = 20
DBSCAN_MIN_SAMPLES = 5
KNN_K = 5

# Параметры загруженности акватории
CONGESTION_RADIUS_KM = 5
CONGESTION_TIME_WINDOW_MIN = 30

# Режим хранения данных: True – PostgreSQL, False – файлы (Parquet/JSON)
USE_DATABASE = False

# Пути к файлам (для файлового режима)
DATA_DIR = "data"
HISTORICAL_DATA_FILE = os.path.join(DATA_DIR, "historical_enriched.parquet")
RISK_ZONES_FILE = os.path.join(DATA_DIR, "risk_zones.json")
CURRENT_VESSELS_FILE = os.path.join(DATA_DIR, "current_vessels.json")
TRAFFIC_DENSITY_FILE = os.path.join(DATA_DIR, "traffic_density.parquet")  # если есть
MARITIME_CORRIDORS_FILE = os.path.join(DATA_DIR, "maritime_corridors.json")

# PostgreSQL (если USE_DATABASE = True)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://vkr_user:vkr_password@localhost:5433/vkr_db")