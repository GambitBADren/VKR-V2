"""
Загрузка и кэширование береговой линии (детальная версия 1:50m).
Добавлены ручные корректировки для Дальнего Востока.
"""
import json
import os
import urllib.request
from shapely.geometry import Polygon, MultiPolygon, Point
from shapely.ops import unary_union

# Используем более детальный файл (1:50m вместо 1:110m)
COASTLINE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson"
CACHE_FILE = "data/land_polygons_50m.geojson"

def download_coastline():
    """Скачивает детальный GeoJSON, если его нет."""
    if os.path.exists(CACHE_FILE):
        print(f"Используем кэшированный файл: {CACHE_FILE}")
        return
    os.makedirs("data", exist_ok=True)
    print(f"Загрузка детальной береговой линии (50m) из {COASTLINE_URL}...")
    urllib.request.urlretrieve(COASTLINE_URL, CACHE_FILE)
    print("Готово.")

def load_land_polygons():
    """Загружает мультиполигон суши из GeoJSON."""
    download_coastline()
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    polygons = []
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]
            polygon = Polygon([(lon, lat) for lon, lat in coords])
            polygons.append(polygon)
        elif geom["type"] == "MultiPolygon":
            for poly_coords in geom["coordinates"]:
                coords = poly_coords[0]
                polygon = Polygon([(lon, lat) for lon, lat in coords])
                polygons.append(polygon)
    land = unary_union(polygons)
    print(f"Загружено {len(polygons)} полигонов, объединено в единый мультиполигон.")
    return land

# Глобальный объект
LAND_POLYGON = None

def manual_land_overrides(lat, lon):
    """
    Ручные корректировки для проблемных зон Дальнего Востока.
    Возвращает True, если точка должна считаться сушей, несмотря на данные.
    """
    if 42.9 <= lat <= 43.2 and 131.7 <= lon <= 132.0:
        return True
    if 45.5 <= lat <= 54.5 and 141.5 <= lon <= 145.0:
        return True
    if 51.0 <= lat <= 62.0 and 155.0 <= lon <= 163.0:
        return True
    if 43.0 <= lat <= 51.0 and 145.0 <= lon <= 156.0:
        return True
    return False

def is_land(lat, lon):
    """Проверяет, находится ли точка на суше (с учётом ручных корректировок)."""
    global LAND_POLYGON
    if LAND_POLYGON is None:
        LAND_POLYGON = load_land_polygons()
    if manual_land_overrides(lat, lon):
        return True
    point = Point(lon, lat)
    return LAND_POLYGON.contains(point)