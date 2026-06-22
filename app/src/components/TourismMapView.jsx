import { useEffect, useRef, useState, useCallback } from 'react';
import { useLockedMapbox } from '../hooks/useLockedMapbox';
import { addDataLayer, attachHoverPopup, whenStyleReady, DEFAULT_MAP_STYLE } from '../utils/mapboxBase';
import 'mapbox-gl/dist/mapbox-gl.css';

const LAYER_BTNS = [
  { key: 'ski',         label: 'Ski Resorts' },
  { key: 'peaks',       label: 'Peaks' },
  { key: 'refuges',     label: 'Refuges' },
  { key: 'attractions', label: 'Attractions' },
  { key: 'btt',         label: 'MTB Trails' },
  { key: 'cycling',     label: 'Cycling' },
  { key: 'corona',      label: 'Corona de Llacs' },
];

const INIT_VIS = {
  ski: true, peaks: true, refuges: true, attractions: true,
  btt: false, cycling: false, corona: false,
};

const FILES = [
  { key: 'ski',         url: '/tourism_ski_areas.geojson' },
  { key: 'peaks',       url: '/tourism_peaks.geojson' },
  { key: 'refuges',     url: '/tourism_refuges.geojson' },
  { key: 'attractions', url: '/tourism_attractions.geojson' },
  { key: 'btt',         url: '/tourism_btt.geojson' },
  { key: 'cycling',     url: '/tourism_cycling.geojson' },
  { key: 'corona',      url: '/tourism_corona_llacs.geojson' },
];

const STAGE_COLORS = ['#f59e0b', '#10b981', '#3b82f6', '#ec4899', '#a855f7'];

const SKI_COLORS = {
  'Grandvalira':            { fill: '#93c5fd', stroke: '#60a5fa' },
  'Vallnord – Pal Arinsal': { fill: '#6ee7b7', stroke: '#34d399' },
  'Ordino Arcalís':         { fill: '#fde68a', stroke: '#fbbf24' },
  'Naturland':              { fill: '#fdba74', stroke: '#fb923c' },
};
const SKI_DEFAULT = { fill: '#93c5fd', stroke: '#60a5fa' };

// Mapbox layer ids per logical key (for visibility toggling).
const LAYER_IDS = {
  ski:         ['tr-ski-fill', 'tr-ski-line'],
  peaks:       ['tr-peaks-dot', 'tr-peaks-label'],
  refuges:     ['tr-refuges'],
  attractions: ['tr-attractions'],
  btt:         ['tr-btt'],
  cycling:     ['tr-cycling'],
  corona:      ['tr-corona'],
};

function stripHoles(geojson) {
  return {
    ...geojson,
    features: geojson.features.map(f => {
      if (!f.geometry) return f;
      const g = f.geometry;
      if (g.type === 'Polygon') return { ...f, geometry: { ...g, coordinates: [g.coordinates[0]] } };
      if (g.type === 'MultiPolygon') return { ...f, geometry: { ...g, coordinates: g.coordinates.map(p => [p[0]]) } };
      return f;
    }),
  };
}

const tip = (html) => `<div style="font-family:monospace;font-size:11px;line-height:1.7">${html}</div>`;

export default function TourismMapView({ mapStyle = DEFAULT_MAP_STYLE }) {
  const containerRef = useRef(null);
  const dataRef      = useRef({});            // key → geojson
  const visRef       = useRef({ ...INIT_VIS });
  const [vis, setVis] = useState(INIT_VIS);

  const vy = (key) => (visRef.current[key] ? 'visible' : 'none');

  const addKey = useCallback((map, key) => {
    const data = dataRef.current[key];
    if (!data) return;
    const srcId = `tr-src-${key}`;
    if (map.getSource(srcId)) return;

    if (key === 'ski') {
      const prepared = stripHoles(data);
      prepared.features.forEach(f => {
        const cfg = SKI_COLORS[f.properties?.name] || SKI_DEFAULT;
        f.properties._fill = cfg.fill;
        f.properties._stroke = cfg.stroke;
      });
      map.addSource(srcId, { type: 'geojson', data: prepared });
      addDataLayer(map, { id: 'tr-ski-fill', type: 'fill', source: srcId, layout: { visibility: vy('ski') },
        paint: { 'fill-color': ['get', '_fill'], 'fill-opacity': 0.72 } });
      addDataLayer(map, { id: 'tr-ski-line', type: 'line', source: srcId, layout: { visibility: vy('ski') },
        paint: { 'line-color': ['get', '_stroke'], 'line-width': 1, 'line-opacity': 0.6 } });
      attachHoverPopup(map, 'tr-ski-fill', (f) => {
        const p = f.properties || {};
        return tip(`<b style="color:${p._fill}">${p.name}</b><br/>${p.pistes_km} km of pistes<br/>${p.min_alt}–${p.max_alt} m<br/><span style="color:#9ca3af">${p.sectors || ''}</span>`);
      });
      return;
    }

    if (key === 'peaks') {
      const prepared = { ...data, features: data.features.map(f => ({
        ...f, properties: { ...f.properties, _label: `▲\n${f.properties?.altitude ? `${f.properties.altitude}m` : ''}` },
      })) };
      map.addSource(srcId, { type: 'geojson', data: prepared });
      addDataLayer(map, { id: 'tr-peaks-dot', type: 'circle', source: srcId, layout: { visibility: vy('peaks') },
        paint: { 'circle-radius': 2.5, 'circle-color': '#ffffff', 'circle-opacity': 0.9 } });
      addDataLayer(map, { id: 'tr-peaks-label', type: 'symbol', source: srcId,
        layout: {
          visibility: vy('peaks'),
          'text-field': ['get', '_label'], 'text-size': 9.5, 'text-anchor': 'bottom',
          'text-offset': [0, -0.2], 'text-allow-overlap': false, 'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Regular'],
        },
        paint: { 'text-color': '#e2e8f0', 'text-halo-color': 'rgba(0,0,0,0.85)', 'text-halo-width': 1.2 } });
      attachHoverPopup(map, 'tr-peaks-dot', (f) => {
        const p = f.properties || {};
        return tip(`<b style="color:#d1d5db">${p.name || '—'}</b><br/>${p.altitude ? `${p.altitude} m` : ''}${p.refugi ? `<br/><span style="color:#fcd34d">${p.refugi}</span>` : ''}`);
      });
      return;
    }

    if (key === 'refuges' || key === 'attractions') {
      const color  = key === 'refuges' ? 'rgba(180,83,9,0.9)' : 'rgba(109,40,217,0.88)';
      const stroke = key === 'refuges' ? 'rgba(255,200,100,0.6)' : 'rgba(196,181,253,0.55)';
      const lid = LAYER_IDS[key][0];
      map.addSource(srcId, { type: 'geojson', data });
      addDataLayer(map, { id: lid, type: 'circle', source: srcId, layout: { visibility: vy(key) },
        paint: { 'circle-radius': 5, 'circle-color': color, 'circle-stroke-color': stroke, 'circle-stroke-width': 1.5 } });
      attachHoverPopup(map, lid, (f) => {
        const p = f.properties || {};
        if (key === 'refuges') return tip(`<b style="color:#fcd34d">${p.name}</b><br/>${p.tipus || ''} ${p.altitude ? `· ${p.altitude} m` : ''}<br/>${p.calendari ? `<span style="color:#9ca3af">${p.calendari}</span>` : ''}`);
        return tip(`<b style="color:#c4b5fd">${p.name}</b><br/><span style="color:#9ca3af">${p.parish || ''}</span>`);
      });
      return;
    }

    if (key === 'btt' || key === 'cycling') {
      const color = key === 'btt' ? '#f97316' : '#06b6d4';
      const lid = LAYER_IDS[key][0];
      map.addSource(srcId, { type: 'geojson', data });
      addDataLayer(map, { id: lid, type: 'line', source: srcId, layout: { visibility: vy(key), 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': color, 'line-width': 2, 'line-opacity': 0.75 } });
      attachHoverPopup(map, lid, (f) => tip(`<b style="color:${key === 'btt' ? '#fb923c' : '#22d3ee'}">${f.properties?.name || (key === 'btt' ? 'BTT trail' : 'Cycling route')}</b>`));
      return;
    }

    if (key === 'corona') {
      const prepared = { ...data, features: data.features.map(f => ({
        ...f, properties: { ...f.properties, _color: STAGE_COLORS[((f.properties?.stage || 1) - 1)] || '#f59e0b' },
      })) };
      map.addSource(srcId, { type: 'geojson', data: prepared });
      addDataLayer(map, { id: 'tr-corona', type: 'line', source: srcId, layout: { visibility: vy('corona'), 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': ['get', '_color'], 'line-width': 3, 'line-opacity': 0.85 } });
      attachHoverPopup(map, 'tr-corona', (f) => {
        const p = f.properties || {};
        return tip(`<b style="color:#fcd34d">${p.name || `Etapa ${p.stage}`}</b><br/><span style="color:#9ca3af">Corona de Llacs · Stage ${p.stage}</span>`);
      });
    }
  }, []);

  const addOverlays = useCallback((map) => {
    Object.keys(dataRef.current).forEach(key => addKey(map, key));
  }, [addKey]);

  const { mapRef } = useLockedMapbox(containerRef, mapStyle, addOverlays);

  useEffect(() => {
    const controller = new AbortController();
    FILES.forEach(({ key, url }) => {
      fetch(url, { signal: controller.signal })
        .then(r => r.json())
        .then(data => {
          dataRef.current[key] = data;
          whenStyleReady(mapRef.current, () => addKey(mapRef.current, key));
        })
        .catch(err => { if (err.name !== 'AbortError') console.warn(`tourism ${key}:`, err); });
    });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = (key) => {
    const next = { ...visRef.current, [key]: !visRef.current[key] };
    visRef.current = next;
    setVis(next);
    const map = mapRef.current;
    if (!map) return;
    (LAYER_IDS[key] || []).forEach(lid => {
      if (map.getLayer(lid)) map.setLayoutProperty(lid, 'visibility', next[key] ? 'visible' : 'none');
    });
  };

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      {/* Controls pill */}
      <div style={{
        position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
        zIndex: 1000, display: 'flex', gap: 6, flexWrap: 'wrap',
        alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(6px)',
        padding: '6px 10px', borderRadius: 10,
        border: '1px solid rgba(255,255,255,0.10)',
        maxWidth: 'calc(100% - 2rem)',
      }}>
        {LAYER_BTNS.map(({ key, label }) => (
          <button key={key} className={`acc-layer-btn${vis[key] ? ' active' : ''}`} onClick={() => toggle(key)}>
            {label}
          </button>
        ))}
      </div>

      <div ref={containerRef} style={{ position: 'absolute', inset: 0, background: '#000' }} />

      {/* Legend */}
      <div className="acc-map-legend" style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 36, zIndex: 1000, flexWrap: 'nowrap', overflow: 'hidden', background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)' }}>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#60a5fa', borderRadius: 2, width: 14, height: 4 }} />Grandvalira</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#34d399', borderRadius: 2, width: 14, height: 4 }} />Vallnord</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#fbbf24', borderRadius: 2, width: 14, height: 4 }} />Arcalís</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#ffffff', borderRadius: 0, width: 14, height: 2, opacity: 0.5 }} />Andorra</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#475569', borderRadius: '50%' }} />Peak</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#92400e', borderRadius: '50%' }} />Refuge</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#6d28d9', borderRadius: '50%' }} />Attraction</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#f97316', borderRadius: 2 }} />MTB</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#06b6d4', borderRadius: 2 }} />Cycling</span>
        {STAGE_COLORS.map((c, i) => (
          <span key={i} className="acc-legend-item"><span className="acc-dot" style={{ background: c, borderRadius: 2 }} />{`E${i + 1}`}</span>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--muted)', letterSpacing: '.06em' }}>
          TOURISM · HOVER FOR DETAILS
        </span>
      </div>
    </div>
  );
}
