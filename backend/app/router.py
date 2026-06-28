import networkx as nx
import numpy as np
import math
import os
import pickle
from sklearn.neighbors import KDTree


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def a_star_search(graph, start, end, edge_weight_func, heuristic_func):
    open_set = {start}
    came_from = {}
    g_score = {start: 0.0}
    f_score = {start: heuristic_func(start)}
    while open_set:
        current = min(open_set, key=lambda n: f_score.get(n, float('inf')))
        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path
        open_set.remove(current)
        for neighbor in graph.neighbors(current):
            tentative_g = g_score[current] + edge_weight_func(current, neighbor)
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic_func(neighbor)
                if neighbor not in open_set:
                    open_set.add(neighbor)
    return None


class MaritimeRouter:
    def __init__(self, min_lat, max_lat, min_lon, max_lon, step_m=10000, cache_dir="data"):
        from pathlib import Path
        PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
        DATA_DIR = PROJECT_ROOT / "data"

        self.cache_full = str(DATA_DIR / "graph_full.pkl")
        self.graph = None
        self.kdtree = None
        self.nodes_list = None
        self._load_graph()
        self._build_kdtree()
        self._precompute_base_weights()

    def _load_graph(self):
        with open(self.cache_full, 'rb') as f:
            self.graph = pickle.load(f)
        print(f"Загружен граф из кэша: {self.cache_full}, узлов: {len(self.graph.nodes)}")

    def _build_kdtree(self):
        coords = np.array([(lat, lon) for (lat, lon) in self.graph.nodes])
        self.kdtree = KDTree(coords, metric='euclidean')
        self.nodes_list = list(self.graph.nodes)
        print(f"KDTree построен для {len(self.nodes_list)} узлов")

    def _precompute_base_weights(self):
        print("Предвычисление базовых весов рёбер...")
        self.time_weight = {}
        self.safety_weight = {}
        for u, v in self.graph.edges():
            dist_km = self.graph[u][v]['weight']
            self.time_weight[(u, v)] = dist_km / (15 * 1.852)
            self.time_weight[(v, u)] = self.time_weight[(u, v)]
            self.safety_weight[(u, v)] = dist_km
            self.safety_weight[(v, u)] = dist_km
        print("Базовые веса предвычислены.")

    def nearest_node(self, point):
        dists, indices = self.kdtree.query([point], k=1)
        return self.nodes_list[indices[0][0]]

    def route(self, start, end, speed_predictor, risk_zones=None, optimization='time',
              vessel_type='cargo', wind_speed=15, wave_height=3, season=1,
              corridors=None, traffic_density=None, hour=None):
        start_node = self.nearest_node(start)
        end_node = self.nearest_node(end)
        base_weights = self.time_weight if optimization == 'time' else self.safety_weight

        def edge_weight(u, v):
            dist_km = self.graph[u][v]['weight']

            if optimization == 'time':
                if speed_predictor is not None:
                    center_lat = (u[0] + v[0]) / 2
                    center_lon = (u[1] + v[1]) / 2
                    try:
                        predicted_speed = speed_predictor(
                            center_lat, center_lon, vessel_type, wind_speed, wave_height, season
                        )
                    except:
                        predicted_speed = 15.0
                else:
                    predicted_speed = 15.0
                return dist_km / (predicted_speed * 1.852)
            else:  # safety
                risk_penalty = 1.0

                # 1. Зоны риска
                if risk_zones:
                    center = ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2)
                    for zone in risk_zones:
                        zone_center = (zone['center']['lat'], zone['center']['lon'])
                        d = haversine(center[0], center[1], zone_center[0], zone_center[1])
                        if d < zone['radius_km']:
                            risk_penalty += zone['avg_risk_score']

                # 2. Морские коридоры (БОНУС - уменьшаем вес)
                if corridors:
                    center = ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2)
                    for corridor in corridors:
                        c_center = (corridor['center']['lat'], corridor['center']['lon'])
                        d = haversine(center[0], center[1], c_center[0], c_center[1])
                        # Если мы в коридоре, уменьшаем штраф (поощряем движение по коридору)
                        if d < corridor['width_km'] / 2:
                            risk_penalty *= 0.8  # 20% бонус
                            break

                # 3. Плотность трафика (ШТРАФ)
                if traffic_density and hour is not None:
                    center = ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2)
                    for traffic in traffic_density:
                        if traffic['hour_of_day'] == hour:
                            t_center = (traffic['center']['lat'], traffic['center']['lon'])
                            d = haversine(center[0], center[1], t_center[0], t_center[1])
                            if d < 10:  # 10 км
                                # Чем больше судов, тем больше штраф
                                traffic_penalty = traffic['vessel_count'] * 0.05
                                risk_penalty += traffic_penalty

                return dist_km * risk_penalty

        def heuristic(node):
            return haversine(node[0], node[1], end_node[0], end_node[1])

        path = a_star_search(self.graph, start_node, end_node, edge_weight, heuristic)
        return path


