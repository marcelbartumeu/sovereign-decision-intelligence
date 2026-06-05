import { useEffect, useRef, useState, useMemo } from 'react';
import L from 'leaflet';
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend);

const BANDS = [
  { label: '0',       min: 0,   max: 0,        color: '#374151' },
  { label: '1–5',     min: 1,   max: 5,        color: '#1e3a8a' },
  { label: '6–15',    min: 6,   max: 15,       color: '#1d4ed8' },
  { label: '16–40',   min: 16,  max: 40,       color: '#4f46e5' },
  { label: '41–80',   min: 41,  max: 80,       color: '#7c3aed' },
  { label: '81–150',  min: 81,  max: 150,      color: '#c026d3' },
  { label: '151–250', min: 151, max: 250,      color: '#f97316' },
  { label: '251+',    min: 251, max: Infinity, color: '#fbbf24' },
];

function popColor(pop, maxPop) {
  if (!pop || pop <= 0) return '#1f2937';
  const t = Math.log1p(pop) / Math.log1p(maxPop);
  const stops = [
    { t: 0.00, r: 30,  g: 58,  b: 138 },
    { t: 0.25, r: 29,  g: 78,  b: 216 },
    { t: 0.50, r: 79,  g: 70,  b: 229 },
    { t: 0.68, r: 124, g: 58,  b: 237 },
    { t: 0.84, r: 192, g: 38,  b: 211 },
    { t: 0.93, r: 249, g: 115, b: 22  },
    { t: 1.00, r: 251, g: 191, b: 36  },
  ];
  let i = 0;
  for (; i < stops.length - 2; i++) { if (t <= stops[i + 1].t) break; }
  const lo = stops[i], hi = stops[i + 1];
  const s  = Math.max(0, Math.min(1, (t - lo.t) / ((hi.t - lo.t) || 1)));
  return `rgb(${Math.round(lo.r + (hi.r - lo.r) * s)},${Math.round(lo.g + (hi.g - lo.g) * s)},${Math.round(lo.b + (hi.b - lo.b) * s)})`;
}

export default function PopulationPanel() {
  const mapRef         = useRef(null);
  const mapInstanceRef = useRef(null);
  const hexLayerRef    = useRef(null);
  const [geoData, setGeoData] = useState(null);
  const [error, setError]     = useState(null);

  // Compute band stats from loaded data
  const bandStats = useMemo(() => {
    if (!geoData) return BANDS.map(b => ({ ...b, count: 0, totalPop: 0 }));
    const result = BANDS.map(b => ({ ...b, count: 0, totalPop: 0 }));
    geoData.features.forEach(f => {
      const pop  = f.properties.population || 0;
      const band = result.find(b => pop >= b.min && pop <= b.max);
      if (band) { band.count++; band.totalPop += pop; }
    });
    return result;
  }, [geoData]);

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
    fetch(`/model/accessibility_population.geojson?v=${_v}`, { signal })
      .then(r => r.json())
      .then(data => {
        const maxPop = Math.max(...data.features.map(f => f.properties.population || 0));

        const hexLayer = L.geoJSON(data, {
          style: f => {
            const pop = f.properties.population || 0;
            return {
              fillColor:   popColor(pop, maxPop),
              fillOpacity: pop > 0 ? 0.85 : 0.18,
              color:       'rgba(0,0,0,0)',
              weight:      0,
            };
          },
          onEachFeature: (f, layer) => {
            const pop = f.properties.population || 0;
            layer.on('mouseover', function () { this.setStyle({ weight: 1.5, color: '#ffffff', fillOpacity: 1 }); });
            layer.on('mouseout',  function () { hexLayer.resetStyle(this); });
            layer.bindPopup(
              `Population: <b>${pop.toLocaleString()}</b>` +
              (f.properties.h3_cell ? `<br><span style="font-size:0.72rem;opacity:0.5">${f.properties.h3_cell}</span>` : '')
            );
          },
        }).addTo(map);

        hexLayerRef.current = hexLayer;
        map.fitBounds([[42.394176, 1.393847], [42.697242, 1.803713]], { padding: [0, 0] });
        setGeoData(data);
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
      hexLayerRef.current    = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const histData = {
    labels: bandStats.map(b => b.label),
    datasets: [{
      label: 'Hexagons',
      data:  bandStats.map(b => b.count),
      backgroundColor: bandStats.map(b => b.color),
      borderRadius: 3,
      borderSkipped: false,
    }],
  };
  const bandData = {
    labels: bandStats.map(b => b.label),
    datasets: [{
      label: 'Residents',
      data:  bandStats.map(b => b.totalPop),
      backgroundColor: bandStats.map(b => b.color),
      borderRadius: 3,
      borderSkipped: false,
    }],
  };
  const chartOpts = (tickFmt) => ({
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#9ca3af', font: { size: 10 } } },
      y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: tickFmt, color: '#9ca3af', font: { size: 10 } } },
    },
  });

  return (
    <div className="acc-panel">

      {/* Stat cards */}
      <div className="acc-stat-row">
        {[
          { color: '#f97316', icon: '👥', value: '87,097',  label: 'Total population',  sub: '2024 baseline' },
          { color: '#ef4444', icon: '🏙️', value: '399',     label: 'Peak hex density',  sub: 'residents per cell' },
          { color: '#a855f7', icon: '📐', value: '10,299',  label: 'H3 hexagons',        sub: '4,547 populated' },
          { color: '#3b82f6', icon: '📊', value: '2.7',     label: 'Median density',     sub: 'residents per cell' },
        ].map(({ color, icon, value, label, sub }) => (
          <div key={label} className="acc-stat-card" style={{ borderTopColor: color }}>
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
            <span>Population density by H3 cell</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--muted-foreground)' }}>Log scale</span>
              <div className="pop-gradient-bar">
                <span>Low</span>
                <div className="pop-gradient" />
                <span>High</span>
              </div>
            </div>
          </div>

          {error
            ? <div style={{ height: 620, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0d0d0d', color: '#9ca3af', fontSize: 12, textAlign: 'center', padding: '2rem' }}>
                {error}
              </div>
            : <div ref={mapRef} style={{ height: 620, width: '100%', background: '#0d0d0d' }} />
          }
        </div>

        {/* Charts column */}
        <div className="acc-charts-col">
          <div className="acc-chart-card">
            <div className="acc-card-header"><span>Density distribution</span></div>
            <div style={{ padding: '0.75rem 1rem 1rem', maxHeight: 200 }}>
              <Bar data={histData} options={chartOpts(v => v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v)} />
            </div>
          </div>
          <div className="acc-chart-card">
            <div className="acc-card-header"><span>Population by density band</span></div>
            <div style={{ padding: '0.75rem 1rem 1rem', maxHeight: 200 }}>
              <Bar data={bandData} options={chartOpts(v => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v)} />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
