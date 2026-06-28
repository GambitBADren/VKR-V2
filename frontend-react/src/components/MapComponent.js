import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const MapComponent = ({
  startPoint, endPoint, waypoints,
  setStartPoint, setEndPoint, setWaypoints,
  route, focusPoint, onClearFocus,
  heatmapSource,
  showRiskZones, showCorridors, showTraffic,
  dateFilter, hourFilter,
}) => {
  const mapRef = useRef(null);
  const markersRef = useRef({ start: null, end: null, waypoints: [], currentVessels: [] });
  const routeLayerRef = useRef(null);
  const heatLayerRef = useRef(null);
  const landLayerRef = useRef(null);
  const focusMarkerRef = useRef(null);
  const riskZonesLayerRef = useRef(null);
  const corridorsLayerRef = useRef(null);
  const trafficLayerRef = useRef(null);

  const [heatmapData, setHeatmapData] = useState({ points: [] });
  const [riskZones, setRiskZones] = useState([]);
  const [corridors, setCorridors] = useState([]);
  const [trafficData, setTrafficData] = useState([]);

  const loadHeatmap = async () => {
    let url = heatmapSource === 'retrospective'
      ? 'http://127.0.0.1:8000/api/heatmap_data'
      : 'http://127.0.0.1:8000/api/current_heatmap_data';

    const params = [];
    if (dateFilter.startDate && heatmapSource === 'retrospective') params.push(`start_date=${dateFilter.startDate}`);
    if (dateFilter.endDate && heatmapSource === 'retrospective') params.push(`end_date=${dateFilter.endDate}`);
    if (hourFilter !== null && heatmapSource === 'retrospective') {
      params.push(`start_hour=${hourFilter}`);
      params.push(`end_hour=${hourFilter}`);
    }

    if (params.length > 0) url += '?' + params.join('&');

    try {
      const res = await fetch(url);
      const data = await res.json();
      setHeatmapData(data);
    } catch (err) { console.error('Ошибка heatmap:', err); }
  };

  const loadRiskZones = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/risk_zones');
      const data = await res.json();
      setRiskZones(data.zones || []);
    } catch (err) { console.error('Ошибка risk zones:', err); }
  };

  const loadCorridors = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/maritime_corridors');
      const data = await res.json();
      setCorridors(data.corridors || []);
    } catch (err) { console.error('Ошибка corridors:', err); }
  };

  const loadTraffic = async () => {
  try {
    let url = 'http://127.0.0.1:8000/api/traffic_density';
    const params = [];
    if (hourFilter !== null) params.push(`hour=${hourFilter}`);
    if (dateFilter.startDate) params.push(`start_date=${dateFilter.startDate}`);
    if (dateFilter.endDate) params.push(`end_date=${dateFilter.endDate}`);
    if (params.length > 0) url += '?' + params.join('&');

    const res = await fetch(url);
    const data = await res.json();

    const transformed = (data.traffic || []).map(item => ({
      center: { lat: item.lat, lon: item.lon },
      vessel_count: item.intensity,
      hour_of_day: item.hour || null
    }));

    setTrafficData(transformed);
  } catch (err) { console.error('Ошибка traffic:', err); }
};

  useEffect(() => {
    if (!mapRef.current) {
      mapRef.current = L.map('map', { attributionControl: false }).setView([55.0, 150.0], 5);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '' }).addTo(mapRef.current);

      fetch('http://127.0.0.1:8000/api/russia_border.geojson')
        .then(r => r.json())
        .then(data => {
          landLayerRef.current = L.geoJSON(data, {
            style: { color: '#1a1a1a', weight: 1.5, fillColor: '#c8e6c9', fillOpacity: 0.6 },
            filter: (feature) => {
              const name = feature.properties?.name || '';
              return name.toLowerCase().includes('russia') ||
                     feature.properties?.['ISO3166-1-Alpha-2'] === 'RU';
            }
          }).addTo(mapRef.current);
        });
    }

    loadHeatmap();
    loadRiskZones();
    loadCorridors();
    loadTraffic();
  }, []);

  useEffect(() => {
    loadHeatmap();
  }, [dateFilter, hourFilter, heatmapSource]);

  useEffect(() => {
    loadTraffic();
  }, [dateFilter, hourFilter]);

  useEffect(() => {
    if (!mapRef.current) return;

    if (heatLayerRef.current) mapRef.current.removeLayer(heatLayerRef.current);
    if (heatmapData.points && heatmapData.points.length) {
      const maxI = Math.max(...heatmapData.points.map(p => p[2]));
      const points = heatmapData.points.map(p => [p[0], p[1], maxI > 0 ? p[2] / maxI : 0]);
      heatLayerRef.current = L.heatLayer(points, {
        radius: 25,
        blur: 20,
        maxZoom: 12,
        minOpacity: 0.4,
        gradient: { 0.0: 'blue', 0.25: 'cyan', 0.5: 'lime', 0.75: 'yellow', 1.0: 'red' }
      }).addTo(mapRef.current);
    }

    if (riskZonesLayerRef.current) mapRef.current.removeLayer(riskZonesLayerRef.current);
    if (showRiskZones && riskZones.length > 0) {
      const group = L.layerGroup();
      riskZones.forEach(zone => {
        const displayRadius = Math.min(zone.radius_km, 100) * 1000;
        L.circle([zone.center.lat, zone.center.lon], {
          radius: displayRadius,
          color: 'red',
          fillColor: '#f03',
          fillOpacity: 0.2,
          weight: 2,
          dashArray: '5, 5'
        }).bindPopup(
          `<b>Зона риска #${zone.id}</b><br/>
           Риск: ${zone.avg_risk_score?.toFixed(2)}<br/>
           Точек: ${zone.points_count}<br/>
           Радиус: ${zone.radius_km?.toFixed(1)} км`
        ).addTo(group);
      });
      riskZonesLayerRef.current = group.addTo(mapRef.current);
    }

    if (corridorsLayerRef.current) mapRef.current.removeLayer(corridorsLayerRef.current);
    if (showCorridors && corridors.length > 0) {
      const group = L.layerGroup();
      corridors.forEach(c => {
        L.circle([c.center.lat, c.center.lon], {
          radius: (c.width_km / 2) * 1000,
          color: 'blue',
          fillColor: '#00f',
          fillOpacity: 0.15,
          weight: 2,
          dashArray: '5, 5'
        }).bindPopup(
          `<b>Морской коридор #${c.id}</b><br/>
           Трафик: ${c.traffic_count} судов<br/>
           Ср. скорость: ${c.avg_speed?.toFixed(1)} уз.`
        ).addTo(group);
      });
      corridorsLayerRef.current = group.addTo(mapRef.current);
    }

    if (trafficLayerRef.current) mapRef.current.removeLayer(trafficLayerRef.current);
    if (showTraffic && trafficData.length > 0) {
      const group = L.layerGroup();
      const maxVessels = Math.max(...trafficData.map(t => t.vessel_count), 1);
      trafficData.forEach(t => {
        const intensity = t.vessel_count / maxVessels;
        L.circleMarker([t.center.lat, t.center.lon], {
          radius: 5 + intensity * 10,
          color: 'orange',
          fillColor: '#f80',
          fillOpacity: 0.6,
          weight: 1
        }).bindPopup(
          `<b>Трафик (${t.hour_of_day !== null ? t.hour_of_day + ':00' : '?'})</b><br/>
           Судов: ${t.vessel_count}`
        ).addTo(group);
      });
      trafficLayerRef.current = group.addTo(mapRef.current);
    }
  }, [heatmapData, riskZones, corridors, trafficData, showRiskZones, showCorridors, showTraffic]);

  useEffect(() => {
    if (!mapRef.current) return;
    if (routeLayerRef.current) mapRef.current.removeLayer(routeLayerRef.current);
    if (route && route.segments && route.segments.length) {
      const group = L.layerGroup();
      route.segments.forEach(seg => {
        const line = L.polyline([[seg.start.lat, seg.start.lon], [seg.end.lat, seg.end.lon]], {
          color: '#1e3a8a',
          weight: 5
        });
        const weatherInfo = seg.weather && seg.weather.wind_speed
          ? `<br/>Ветер: ${seg.weather.wind_speed.toFixed(1)} м/с<br/> Волна: ${seg.weather.wave_height.toFixed(1)} м`
          : '';
        line.bindTooltip(
          `Скорость: ${seg.recommended_speed_knots?.toFixed(1)} уз.<br/>
           Риск: ${seg.risk_level?.toFixed(2)}<br/>
           Расст.: ${seg.distance_km?.toFixed(1)} км${weatherInfo}`,
          { permanent: false, direction: 'center', offset: [0, -10] }
        );
        group.addLayer(line);
      });
      routeLayerRef.current = group.addTo(mapRef.current);
      mapRef.current.fitBounds(L.latLngBounds(route.segments.flatMap(s => [[s.start.lat, s.start.lon], [s.end.lat, s.end.lon]])));
    }
  }, [route]);

  useEffect(() => {
    if (!mapRef.current) return;
    const handleMapClick = (e) => {
      if (!startPoint) setStartPoint(e.latlng);
      else if (!endPoint) setEndPoint(e.latlng);
      else setWaypoints(prev => [...prev, e.latlng]);
    };
    mapRef.current.on('click', handleMapClick);
    return () => mapRef.current?.off('click', handleMapClick);
  }, [startPoint, endPoint, setStartPoint, setEndPoint, setWaypoints]);

  useEffect(() => {
    if (!mapRef.current) return;
    if (markersRef.current.start) mapRef.current.removeLayer(markersRef.current.start);
    if (startPoint) {
      markersRef.current.start = L.marker(startPoint, { draggable: true })
        .addTo(mapRef.current)
        .bindPopup('Старт')
        .openPopup();
      markersRef.current.start.on('dragend', (e) => setStartPoint(e.target.getLatLng()));
    }
    if (markersRef.current.end) mapRef.current.removeLayer(markersRef.current.end);
    if (endPoint) {
      markersRef.current.end = L.marker(endPoint, { draggable: true })
        .addTo(mapRef.current)
        .bindPopup('Финиш');
      markersRef.current.end.on('dragend', (e) => setEndPoint(e.target.getLatLng()));
    }
    markersRef.current.waypoints.forEach(m => mapRef.current.removeLayer(m));
    markersRef.current.waypoints = [];
    waypoints.forEach((wp, idx) => {
      const m = L.marker(wp, { draggable: true })
        .addTo(mapRef.current)
        .bindPopup(`Точка ${idx+1}`);
      m.on('dragend', (e) => {
        const newPos = e.target.getLatLng();
        setWaypoints(prev => prev.map((p, i) => i === idx ? newPos : p));
      });
      markersRef.current.waypoints.push(m);
    });
  }, [startPoint, endPoint, waypoints, setStartPoint, setEndPoint, setWaypoints]);

  useEffect(() => {
    if (!mapRef.current) return;
    if (focusPoint) {
      if (focusMarkerRef.current) mapRef.current.removeLayer(focusMarkerRef.current);
      focusMarkerRef.current = L.marker([focusPoint.lat, focusPoint.lon], {
        icon: L.divIcon({ className: 'focus-marker', html: '📍', iconSize: [20, 20] })
      }).addTo(mapRef.current)
        .bindPopup(focusPoint.description || 'Историческая ситуация')
        .openPopup();
      mapRef.current.setView([focusPoint.lat, focusPoint.lon], 10);
    } else {
      if (focusMarkerRef.current) mapRef.current.removeLayer(focusMarkerRef.current);
      focusMarkerRef.current = null;
    }
  }, [focusPoint]);

  return <div id="map" style={{ height: '100%', width: '100%' }} />;
};

export default MapComponent;
