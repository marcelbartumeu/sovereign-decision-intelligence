import { useEffect, useRef, useState, useCallback } from 'react';
import { useLockedMapbox } from '../hooks/useLockedMapbox';
import { addDataLayer, attachHoverPopup, whenStyleReady, DEFAULT_MAP_STYLE } from '../utils/mapboxBase';
import 'mapbox-gl/dist/mapbox-gl.css';

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

const SRC = 'population-hex';

export default function PopulationMapView({ mapStyle = DEFAULT_MAP_STYLE, onBandStats }) {
  const containerRef = useRef(null);
  const dataRef      = useRef(null);
  const [error, setError] = useState(null);

  const addOverlays = useCallback((map) => {
    if (!dataRef.current || map.getSource(SRC)) return;
    map.addSource(SRC, { type: 'geojson', data: dataRef.current });
    addDataLayer(map, {
      id: SRC,
      type: 'fill',
      source: SRC,
      paint: {
        'fill-color': ['get', '_color'],
        'fill-opacity': ['get', '_alpha'],
        'fill-outline-color': ['get', '_color'], // border matches fill → no seams
      },
    });
    attachHoverPopup(map, SRC, (f) => {
      const p = f.properties || {};
      const pop = p.population || 0;
      return `Population: <b>${Number(pop).toLocaleString()}</b>` +
        (p.h3_cell ? `<br><span style="font-size:0.72rem;opacity:0.45">${p.h3_cell}</span>` : '');
    });
  }, []);

  const { mapRef } = useLockedMapbox(containerRef, mapStyle, addOverlays);

  useEffect(() => {
    const controller = new AbortController();
    const _v = Date.now();
    fetch(`/model/accessibility_population.geojson?v=${_v}`, { signal: controller.signal })
      .then(r => r.json())
      .then(data => {
        const maxPop = Math.max(...data.features.map(f => f.properties.population || 0));
        data.features.forEach(f => {
          const pop = f.properties.population || 0;
          f.properties._color = popColor(pop, maxPop);
          f.properties._alpha = pop > 0 ? 0.90 : 0.12;
        });
        dataRef.current = data;
        whenStyleReady(mapRef.current, () => addOverlays(mapRef.current));

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
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

      {error
        ? <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000', color: '#9ca3af', fontSize: 12, textAlign: 'center', padding: '2rem' }}>
            Map data requires the Vite dev server
          </div>
        : <div ref={containerRef} style={{ position: 'absolute', inset: 0, background: '#000' }} />
      }
    </div>
  );
}
