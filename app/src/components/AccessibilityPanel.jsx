import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import {
  Chart as ChartJS,
  ArcElement, BarElement,
  CategoryScale, LinearScale,
  Tooltip, Legend,
} from 'chart.js';
import { Doughnut, Bar } from 'react-chartjs-2';

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const ACC_COLORS = {
  walk:      '#4ade80',
  bike:      '#fbbf24',
  'bus/car': '#f87171',
  default:   '#374151',
};
const accColor = v => ACC_COLORS[v] || ACC_COLORS.default;

const LAYER_BTNS = [
  ['hexagons', 'Hexagons'],
  ['streets',  'Streets'],
  ['schools',  'Schools'],
  ['parks',    'Parks'],
  ['busRoutes','Bus Lines'],
  ['busStops', 'Bus Stops'],
];

const MODE_LABELS = ['Walk', 'Bike', 'Bus / Car'];
const MODE_POP    = [56265, 10101, 13392];
const MODE_COLORS = ['#22c55e', '#f59e0b', '#ef4444'];

const INIT_VIS = { hexagons: true, streets: true, schools: true, parks: true, busRoutes: true, busStops: true };

export default function AccessibilityPanel() {
  const mapRef         = useRef(null);
  const mapInstanceRef = useRef(null);
  const layersRef      = useRef({});
  const visRef         = useRef({ ...INIT_VIS });
  const [vis, setVis]  = useState(INIT_VIS);
  const [error, setError] = useState(null);

  const toggle = key => {
    const next = { ...visRef.current, [key]: !visRef.current[key] };
    visRef.current = next;
    setVis({ ...next });
    const map   = mapInstanceRef.current;
    const layer = layersRef.current[key];
    if (map && layer) {
      next[key] ? map.addLayer(layer) : map.removeLayer(layer);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const PROJECTION_BOUNDS = [[42.394176, 1.393847], [42.697242, 1.803713]];
    const map = L.map(mapRef.current, {
      center: [42.545709, 1.598780], zoom: 11,
      zoomSnap: 0,
      zoomControl: false, attributionControl: false,
      scrollWheelZoom: false, doubleClickZoom: false,
      touchZoom: false, boxZoom: false,
      dragging: false, keyboard: false,
    });
    map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] });
    map.on('resize', () => { map.invalidateSize(); map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] }); });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd', maxZoom: 19,
    }).addTo(map);

    mapInstanceRef.current = map;

    const _v = Date.now();
    Promise.all([
      fetch(`/model/accessibility_population.geojson?v=${_v}`, { signal }).then(r => r.json()),
      fetch(`/model/accessibility_streets.geojson?v=${_v}`, { signal }).then(r => r.json()),
      fetch(`/model/accessibility_schools.geojson?v=${_v}`, { signal }).then(r => r.json()),
      fetch(`/model/accessibility_parks.geojson?v=${_v}`, { signal }).then(r => r.json()),
      fetch(`/model/bus_routes.geojson?v=${_v}`, { signal }).then(r => r.json()),
      fetch(`/model/bus_stops.geojson?v=${_v}`, { signal }).then(r => r.json()),
    ])
    .then(([popData, streetsData, schoolsData, parksData, busRoutesData, busStopsData]) => {
      const maxPop = Math.max(...popData.features.map(f => f.properties.population || 0));

      const hexLayer = L.geoJSON(popData, {
        style: f => {
          const pop = f.properties.population || 0;
          return {
            fillColor:   accColor(f.properties.accessibility),
            fillOpacity: 0.15 + Math.sqrt(pop / maxPop) * 0.72,
            color:       'rgba(0,0,0,0)',
            weight:      0,
          };
        },
        onEachFeature: (f, layer) => {
          const p = f.properties;
          layer.on('mouseover', function () { this.setStyle({ weight: 1.5, color: '#ffffff', fillOpacity: 1 }); });
          layer.on('mouseout',  function () { hexLayer.resetStyle(this); });
          layer.bindPopup(
            `<b style="text-transform:capitalize">${p.accessibility || 'unknown'}</b><br>` +
            `Population: <b>${(p.population || 0).toLocaleString()}</b>`
          );
        },
      });
      layersRef.current.hexagons = hexLayer;
      if (visRef.current.hexagons) hexLayer.addTo(map);

      const streetLayer = L.geoJSON(streetsData, {
        style: f => ({ color: accColor(f.properties.accessibility), weight: 1.2, opacity: 0.6, lineCap: 'round', lineJoin: 'round' }),
      });
      layersRef.current.streets = streetLayer;
      if (visRef.current.streets) streetLayer.addTo(map);

      const schoolLayer = L.geoJSON(schoolsData, {
        pointToLayer: (f, latlng) => L.circleMarker(latlng, {
          radius: 6, fillColor: '#60a5fa', color: '#1d4ed8', weight: 1.5, fillOpacity: 0.9,
        }),
        onEachFeature: (f, layer) => layer.bindPopup(`<b>${f.properties.name || 'School'}</b>`),
      });
      layersRef.current.schools = schoolLayer;
      if (visRef.current.schools) schoolLayer.addTo(map);

      const parksLayer = L.geoJSON(parksData, {
        style: f => ({ fillColor: f.properties.color || '#166534', fillOpacity: 0.5, color: '#14532d', weight: 1 }),
        onEachFeature: (f, layer) => {
          const q = f.properties.poi_quality;
          layer.bindPopup(`Park<br>Quality: <b>${q ? (q * 100).toFixed(0) + '%' : 'N/A'}</b>`);
        },
      });
      layersRef.current.parks = parksLayer;
      if (visRef.current.parks) parksLayer.addTo(map);

      const busRoutesLayer = L.geoJSON(busRoutesData, {
        style: f => ({ color: f.properties.colour || '#ffffff', weight: 3.5, opacity: 0.85, lineCap: 'round', lineJoin: 'round' }),
        onEachFeature: (f, layer) => {
          const p = f.properties;
          layer.bindPopup(`<b>${p.ref}</b> — ${p.name}<br><span style="opacity:0.7">${p.operator}</span>`);
          layer.on('mouseover', function () { this.setStyle({ weight: 6, opacity: 1 }); this.bringToFront(); });
          layer.on('mouseout',  function () { busRoutesLayer.resetStyle(this); });
        },
      });
      layersRef.current.busRoutes = busRoutesLayer;
      if (visRef.current.busRoutes) busRoutesLayer.addTo(map);

      const busStopsLayer = L.geoJSON(busStopsData, {
        pointToLayer: (f, latlng) => L.circleMarker(latlng, {
          radius: 4, fillColor: '#facc15', color: '#1e293b', weight: 1.5, fillOpacity: 0.95,
        }),
        onEachFeature: (f, layer) => {
          const p = f.properties;
          const lines = p.lines ? `<br>Lines: <b>${p.lines}</b>` : '';
          layer.bindPopup(`<b>${p.name}</b>${lines}`);
        },
      });
      layersRef.current.busStops = busStopsLayer;
      if (visRef.current.busStops) busStopsLayer.addTo(map);

      map.fitBounds([[42.394176, 1.393847], [42.697242, 1.803713]], { padding: [0, 0] });
    })
    .catch(err => {
      if (err.name !== 'AbortError') {
        setError('Map data requires the Vite dev server (npm run dev).');
      }
    });

    return () => {
      controller.abort();
      map.remove();
      mapInstanceRef.current = null;
      layersRef.current = {};
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const donutData = {
    labels: MODE_LABELS,
    datasets: [{ data: MODE_POP, backgroundColor: MODE_COLORS, borderColor: '#1a1a1a', borderWidth: 2, hoverOffset: 6 }],
  };
  const donutOptions = {
    cutout: '68%',
    plugins: {
      legend: { position: 'bottom', labels: { boxWidth: 10, padding: 12, color: '#9ca3af', font: { size: 11, family: 'IBM Plex Mono' } } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} (${(ctx.parsed / 87097 * 100).toFixed(1)}%)` } },
    },
  };
  const barData = {
    labels: MODE_LABELS,
    datasets: [{ label: 'Residents', data: MODE_POP, backgroundColor: MODE_COLORS, borderRadius: 4, borderSkipped: false }],
  };
  const barOptions = {
    indexAxis: 'y',
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { callback: v => (v / 1000).toFixed(0) + 'k', color: '#9ca3af', font: { size: 10 } } },
      y: { grid: { display: false }, ticks: { color: '#9ca3af', font: { size: 10 } } },
    },
  };

  return (
    <div className="acc-panel">

      {/* Stat cards */}
      <div className="acc-stat-row">
        {[
          { cls: 'acc-walk',  icon: '🚶', value: '64.6%',  label: 'Walkable',       sub: '56,265 residents' },
          { cls: 'acc-bike',  icon: '🚲', value: '11.6%',  label: 'Bike access',    sub: '10,101 residents' },
          { cls: 'acc-car',   icon: '🚌', value: '15.4%',  label: 'Bus / Car only', sub: '13,392 residents' },
          { cls: 'acc-total', icon: '👥', value: '87,097', label: 'Total population',sub: '2024 baseline'   },
        ].map(({ cls, icon, value, label, sub }) => (
          <div key={cls} className={`acc-stat-card ${cls}`}>
            <div className="acc-stat-icon">{icon}</div>
            <div className="acc-stat-value">{value}</div>
            <div className="acc-stat-label">{label}</div>
            <div className="acc-stat-sub">{sub}</div>
          </div>
        ))}
      </div>

      {/* Map + charts */}
      <div className="acc-main-row">

        {/* Map card */}
        <div className="acc-map-card">
          <div className="acc-card-header">
            <span>Accessibility by H3 cell</span>
            <div className="acc-layer-toggles">
              {LAYER_BTNS.map(([key, label]) => (
                <button key={key} className={`acc-layer-btn${vis[key] ? ' active' : ''}`} onClick={() => toggle(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {error
            ? <div style={{ height: 620, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0d0d0d', color: '#9ca3af', fontSize: 12, textAlign: 'center', padding: '2rem' }}>
                {error}
              </div>
            : <div ref={mapRef} style={{ height: 620, width: '100%', background: '#0d0d0d' }} />
          }

          <div className="acc-map-legend">
            <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#4ade80' }} /> Walk</span>
            <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#fbbf24' }} /> Bike</span>
            <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#f87171' }} /> Bus/Car</span>
            <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#166534' }} /> Parks</span>
            <span className="acc-legend-item">
              <span style={{ display: 'inline-block', width: 14, height: 4, background: '#E63946', borderRadius: 2, flexShrink: 0 }} /> Bus Lines
            </span>
            <span className="acc-legend-item">
              <span className="acc-dot" style={{ background: '#facc15', border: '2px solid #1e293b' }} /> Bus Stops
            </span>
          </div>
        </div>

        {/* Charts column */}
        <div className="acc-charts-col">
          <div className="acc-chart-card">
            <div className="acc-card-header"><span>Mode distribution</span></div>
            <div className="acc-donut-wrap">
              <Doughnut data={donutData} options={donutOptions} />
              <div className="acc-donut-center">
                <div className="acc-donut-total">87k</div>
                <div className="acc-donut-label">residents</div>
              </div>
            </div>
          </div>
          <div className="acc-chart-card">
            <div className="acc-card-header"><span>Residents by mode</span></div>
            <div style={{ padding: '0.75rem 1rem 1rem' }}>
              <Bar data={barData} options={barOptions} />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
