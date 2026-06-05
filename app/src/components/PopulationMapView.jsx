import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { addAndorraBoundary } from '../utils/andorraBoundary';
import MapMask from './MapMask';

// 10-stop color ramp — more stops = smoother perceived gradient between adjacent hexagons
function popColor(pop, maxPop) {
  if (!pop || pop <= 0) return '#111827';
  const t = Math.log1p(pop) / Math.log1p(maxPop);
  const stops = [
    { t: 0.00, r: 15,  g: 23,  b: 42  },  // #0f172a  void dark
    { t: 0.12, r: 23,  g: 37,  b: 84  },  // #172554  deep navy
    { t: 0.26, r: 30,  g: 58,  b: 138 },  // #1e3a8a  navy blue
    { t: 0.40, r: 29,  g: 78,  b: 216 },  // #1d4ed8  royal blue
    { t: 0.52, r: 67,  g: 56,  b: 202 },  // #4338ca  indigo
    { t: 0.62, r: 109, g: 40,  b: 217 },  // #6d28d9  violet
    { t: 0.72, r: 147, g: 51,  b: 234 },  // #9333ea  purple
    { t: 0.82, r: 192, g: 38,  b: 211 },  // #c026d3  fuchsia
    { t: 0.91, r: 234, g: 88,  b: 12  },  // #ea580c  orange-red
    { t: 0.96, r: 249, g: 115, b: 22  },  // #f97316  orange
    { t: 1.00, r: 251, g: 191, b: 36  },  // #fbbf24  amber
  ];
  let i = 0;
  for (; i < stops.length - 2; i++) { if (t <= stops[i + 1].t) break; }
  const lo = stops[i], hi = stops[i + 1];
  const s  = Math.max(0, Math.min(1, (t - lo.t) / ((hi.t - lo.t) || 1)));
  const r  = Math.round(lo.r + (hi.r - lo.r) * s);
  const g  = Math.round(lo.g + (hi.g - lo.g) * s);
  const b  = Math.round(lo.b + (hi.b - lo.b) * s);
  return `rgb(${r},${g},${b})`;
}

export default function PopulationMapView({ onBandStats }) {
  const mapRef         = useRef(null);
  const mapInstanceRef = useRef(null);
  const hexLayerRef    = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const map = L.map(mapRef.current, {
      zoomSnap: 0,
      zoomControl: false, attributionControl: false,
      scrollWheelZoom: false, doubleClickZoom: false,
      touchZoom: false, boxZoom: false,
      dragging: false, keyboard: false,
    }).setView([42.545709, 1.598780], 11);
    const PROJECTION_BOUNDS = [[42.394176, 1.393847], [42.697242, 1.803713]];
    map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] });
    map.on('resize', () => { map.invalidateSize(); map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] }); });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd', maxZoom: 19,
    }).addTo(map);
    mapInstanceRef.current = map;
    addAndorraBoundary(map);
    [
      [42.694543, 1.393847], [42.697242, 1.801074],
      [42.394176, 1.39849],  [42.396861, 1.803713],
    ].forEach(([lat, lon]) => {
      L.circleMarker([lat, lon], { radius: 5, fillColor: '#ff3333', color: '#ffffff', weight: 2, fillOpacity: 1 }).addTo(map);
    });

    // Canvas renderer: GPU-composited, anti-aliased edges → smoother appearance
    const canvas = L.canvas({ padding: 0.5, tolerance: 0 });

    const _v = Date.now();
    fetch(`/model/accessibility_population.geojson?v=${_v}`, { signal })
      .then(r => r.json())
      .then(data => {
        const maxPop = Math.max(...data.features.map(f => f.properties.population || 0));

        const hexLayer = L.geoJSON(data, {
          renderer: canvas,
          style: f => {
            const pop   = f.properties.population || 0;
            const col   = popColor(pop, maxPop);
            const alpha = pop > 0 ? 0.90 : 0.12;
            return {
              fillColor:   col,
              fillOpacity: alpha,
              // Border matches fill — eliminates seams between adjacent hexagons
              color:       col,
              weight:      0.6,
              opacity:     alpha,
              smoothFactor: 0,   // no path simplification = crisp hex edges
            };
          },
          onEachFeature: (f, layer) => {
            const pop = f.properties.population || 0;
            layer.on('mouseover', function () {
              this.setStyle({ weight: 2, color: '#ffffff', fillOpacity: 1, opacity: 1 });
              this.bringToFront();
            });
            layer.on('mouseout', function () { hexLayer.resetStyle(this); });
            layer.bindPopup(
              `Population: <b>${pop.toLocaleString()}</b>` +
              (f.properties.h3_cell ? `<br><span style="font-size:0.72rem;opacity:0.45">${f.properties.h3_cell}</span>` : '')
            );
          },
        }).addTo(map);

        hexLayerRef.current = hexLayer;
        map.fitBounds([[42.394176, 1.393847], [42.697242, 1.803713]], { padding: [0, 0] });

        // Compute band stats and pass up to parent (for KPI charts)
        if (onBandStats) {
          const BANDS = [
            { label: '0',       min: 0,   max: 0,        color: '#374151' },
            { label: '1–5',     min: 1,   max: 5,        color: '#1e3a8a' },
            { label: '6–15',    min: 6,   max: 15,       color: '#1d4ed8' },
            { label: '16–40',   min: 16,  max: 40,       color: '#4f46e5' },
            { label: '41–80',   min: 41,  max: 80,       color: '#7c3aed' },
            { label: '81–150',  min: 81,  max: 150,      color: '#c026d3' },
            { label: '151–250', min: 151, max: 250,      color: '#f97316' },
            { label: '251+',    min: 251, max: Infinity, color: '#fbbf24' },
          ].map(b => ({ ...b, count: 0, totalPop: 0 }));

          data.features.forEach(f => {
            const pop  = f.properties.population || 0;
            const band = BANDS.find(b => pop >= b.min && pop <= b.max);
            if (band) { band.count++; band.totalPop += pop; }
          });
          onBandStats(BANDS);
        }
      })
      .catch(err => { if (err.name !== 'AbortError') setError(true); });

    return () => { controller.abort(); map.remove(); mapInstanceRef.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      {/* Header — overlay */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 48, zIndex: 1000,
        display: 'flex', alignItems: 'center', gap: '0.75rem',
        padding: '0 1rem', overflow: 'hidden',
        background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        fontSize: '0.75rem', color: 'var(--muted-foreground)',
      }}>
        <span style={{ fontSize: '0.7rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>Log scale density</span>
        <div className="pop-gradient-bar">
          <span>Low</span>
          <div className="pop-gradient" style={{ width: 120 }} />
          <span>High</span>
        </div>
      </div>

      {/* Map — full coverage */}
      {error
        ? <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0d0d0d', color: '#9ca3af', fontSize: 12, textAlign: 'center', padding: '2rem' }}>
            Map data requires the Vite dev server
          </div>
        : <div ref={mapRef} style={{ position: 'absolute', inset: 0, background: '#0d0d0d' }} />
      }
      <MapMask mapInstance={mapInstanceRef} />
    </div>
  );
}
