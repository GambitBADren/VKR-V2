import React, { useState, useRef, useEffect } from 'react';
import MapComponent from './components/MapComponent';
import Sidebar from './components/Sidebar';
import AuthComponent from './components/AuthComponent';
import './App.css';

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [startPoint, setStartPoint] = useState(null);
  const [endPoint, setEndPoint] = useState(null);
  const [waypoints, setWaypoints] = useState([]);
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [focusPoint, setFocusPoint] = useState(null);
  const [heatmapSource, setHeatmapSource] = useState('retrospective');
  const abortControllerRef = useRef(null);

  const [showRiskZones, setShowRiskZones] = useState(true);
  const [showCorridors, setShowCorridors] = useState(false);
  const [showTraffic, setShowTraffic] = useState(false);
  const [dateFilter, setDateFilter] = useState({ startDate: '', endDate: '' });
  const [hourFilter, setHourFilter] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const username = localStorage.getItem('username');
    const role = localStorage.getItem('role');
    if (token && username && role) {
      setCurrentUser({ username, role });
    }
  }, []);

  const handleLogin = (user) => {
    setCurrentUser(user);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    setCurrentUser(null);
  };

  const fetchRoute = async (params) => {
    if (!startPoint || !endPoint) {
      setError('Укажите точки старта и финиша на карте');
      return;
    }
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setLoading(true);
    setError(null);
    setAnalysis(null);
    setRoute(null);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortController.signal,
        body: JSON.stringify({
          start: { lat: startPoint.lat, lon: startPoint.lng },
          end: { lat: endPoint.lat, lon: endPoint.lng },
          waypoints: waypoints.map(wp => ({ lat: wp.lat, lon: wp.lng })),
          vessel_type: params.vesselType,
          optimization: params.optimization,
          wind_speed: params.wind_speed,
          wave_height: params.wave_height,
          season: params.season
        })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.segments) {
        setRoute(data);
        analyzeRoute(data.segments, params.vesselType);
      } else {
        setError('Маршрут не найден');
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Построение маршрута отменено');
      } else {
        setError('Ошибка: ' + err.message);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const cancelRoute = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
  };

  const analyzeRoute = async (segments, vesselType) => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/analyze_route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segments, vessel_type: vesselType })
      });
      const result = await response.json();
      setAnalysis(result);
    } catch (err) {
      console.error('Ошибка анализа:', err);
    }
  };

  const clearRoute = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setRoute(null);
    setStartPoint(null);
    setEndPoint(null);
    setWaypoints([]);
    setError(null);
    setAnalysis(null);
    setFocusPoint(null);
  };

  const showSituationOnMap = (lat, lon, description) => {
    setFocusPoint({ lat, lon, description });
  };

  if (!currentUser) {
    return <AuthComponent onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <div style={{
        position: 'absolute',
        top: 0, left: 0, right: 0,
        height: '40px',
        backgroundColor: '#1e3a8a',
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        zIndex: 1000,
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <div style={{ fontWeight: 'bold', fontSize: '14px' }}>
          🚢 Система маршрутизации морских судов
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', fontSize: '13px' }}>
          <span>
            👤 {currentUser.username}
            <span style={{
              marginLeft: '8px',
              padding: '2px 8px',
              backgroundColor: currentUser.role === 'specialist' ? '#10b981' : '#6b7280',
              borderRadius: '4px',
              fontSize: '11px'
            }}>
              {currentUser.role === 'specialist' ? 'Специалист' : 'Пользователь'}
            </span>
          </span>
          <button
            onClick={handleLogout}
            style={{
              padding: '4px 12px',
              backgroundColor: '#dc2626',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            Выйти
          </button>
        </div>
      </div>

      <MapComponent
        startPoint={startPoint}
        endPoint={endPoint}
        waypoints={waypoints}
        setStartPoint={setStartPoint}
        setEndPoint={setEndPoint}
        setWaypoints={setWaypoints}
        route={route}
        focusPoint={focusPoint}
        onClearFocus={() => setFocusPoint(null)}
        heatmapSource={heatmapSource}
        showRiskZones={showRiskZones}
        showCorridors={showCorridors}
        showTraffic={showTraffic}
        dateFilter={dateFilter}
        hourFilter={hourFilter}
      />
      <Sidebar
        onRouteRequest={fetchRoute}
        onCancelRoute={cancelRoute}
        loading={loading}
        error={error}
        route={route}
        analysis={analysis}
        onClear={clearRoute}
        onShowSituation={showSituationOnMap}
        onHeatmapSourceChange={setHeatmapSource}
        showRiskZones={showRiskZones}
        setShowRiskZones={setShowRiskZones}
        showCorridors={showCorridors}
        setShowCorridors={setShowCorridors}
        showTraffic={showTraffic}
        setShowTraffic={setShowTraffic}
        dateFilter={dateFilter}
        setDateFilter={setDateFilter}
        hourFilter={hourFilter}
        setHourFilter={setHourFilter}
        currentUser={currentUser}
      />
    </div>
  );
}

export default App;





