import os
from dotenv import load_dotenv

load_dotenv()

# Географические границы Дальнего Востока (только восточная долгота)
MIN_LAT = 42.5
MAX_LAT = 66.1
MIN_LON = 130.0
MAX_LON = 180.0   # не переходим через 180, чтобы избежать разрыва карты

# Параметры синтетических данных (можно уменьшить для теста)
NUM_AIS_RECORDS = 350_000

# Параметры сетки для графа (рекомендую 20 км для скорости)
GRID_STEP_M = 20_000   # 20 км

# ML параметры
RISK_ZONE_THRESHOLD = 0.7
DBSCAN_EPS_KM = 20
DBSCAN_MIN_SAMPLES = 5
KNN_K = 5

# Параметры загруженности акватории
CONGESTION_RADIUS_KM = 5
CONGESTION_TIME_WINDOW_MIN = 30
