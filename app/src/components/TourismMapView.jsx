import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { addAndorraBoundary } from '../utils/andorraBoundary';
import MapMask from './MapMask';

const PROJECTION_BOUNDS = [[42.394176, 1.393847], [42.697242, 1.803713]];

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

const STAGE_COLORS = ['#f59e0b', '#10b981', '#3b82f6', '#ec4899', '#a855f7'];

const SKI_COLORS = {
  'Grandvalira':            { fill: '#93c5fd', stroke: '#60a5fa' },
  'Vallnord – Pal Arinsal': { fill: '#6ee7b7', stroke: '#34d399' },
  'Ordino Arcalís':         { fill: '#fde68a', stroke: '#fbbf24' },
  'Naturland':              { fill: '#fdba74', stroke: '#fb923c' },
};

function mkPeakIcon(altitude) {
  const label = altitude ? `${altitude}m` : '▲';
  return L.divIcon({
    html: `<div style="display:flex;flex-direction:column;align-items:center;pointer-events:none;">
      <div style="width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:12px solid rgba(255,255,255,0.92);filter:drop-shadow(0 1px 3px rgba(0,0,0,0.7));"></div>
      <div style="margin-top:2px;background:rgba(15,23,42,0.82);color:#e2e8f0;font-size:8.5px;font-weight:600;font-family:IBM Plex Mono,monospace;padding:1px 4px;border-radius:3px;white-space:nowrap;border:1px solid rgba(255,255,255,0.18);backdrop-filter:blur(2px);">${label}</div>
    </div>`,
    className: '', iconSize: [46, 32], iconAnchor: [23, 12],
  });
}

function mkRefugeIcon() {
  return L.divIcon({
    html: `<div style="width:10px;height:10px;border-radius:50%;background:rgba(180,83,9,0.90);box-shadow:0 1px 4px rgba(0,0,0,0.6);border:1.5px solid rgba(255,200,100,0.6);pointer-events:none;"></div>`,
    className: '', iconSize: [10, 10], iconAnchor: [5, 5],
  });
}

function mkAttractionIcon() {
  return L.divIcon({
    html: `<div style="width:10px;height:10px;border-radius:50%;background:rgba(109,40,217,0.88);box-shadow:0 1px 4px rgba(0,0,0,0.6);border:1.5px solid rgba(196,181,253,0.55);pointer-events:none;"></div>`,
    className: '', iconSize: [10, 10], iconAnchor: [5, 5],
  });
}

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

function buildLayer(key, data, skiRendererRef) {
  if (key === 'ski') {
    const renderer = L.canvas({ padding: 0.5 });
    skiRendererRef.current = renderer;
    return L.geoJSON(stripHoles(data), {
      renderer,
      style: feat => {
        const cfg = SKI_COLORS[feat.properties.name] || { fill: '#93c5fd', stroke: '#60a5fa' };
        return { fillColor: cfg.fill, fillOpacity: 1, fillRule: 'nonzero', color: 'transparent', weight: 0, smoothFactor: 1 };
      },
      onEachFeature: (f, lyr) => {
        const p   = f.properties;
        const cfg = SKI_COLORS[p.name] || { fill: '#93c5fd', stroke: '#60a5fa' };
        lyr.on('mouseover', function () { this.setStyle({ color: cfg.stroke, weight: 2 }); });
        lyr.on('mouseout',  function () { this.setStyle({ color: 'transparent', weight: 0 }); });
        lyr.bindTooltip(
          `<div style="font-family:monospace;font-size:11px;line-height:1.7"><b style="color:${cfg.fill}">${p.name}</b><br/>${p.pistes_km} km of pistes<br/>${p.min_alt}–${p.max_alt} m<br/><span style="color:#9ca3af">${p.sectors}</span></div>`,
          { sticky: true, opacity: 0.97 }
        );
      },
    });
  }

  if (key === 'peaks') {
    return L.geoJSON(data, {
      pointToLayer: (f, ll) => L.marker(ll, { icon: mkPeakIcon(f.properties.altitude) }),
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindTooltip(
          `<div style="font-family:monospace;font-size:11px;line-height:1.7"><b style="color:#d1d5db">${p.name || '—'}</b><br/>${p.altitude ? `${p.altitude} m` : ''}${p.refugi ? `<br/><span style="color:#fcd34d">${p.refugi}</span>` : ''}</div>`,
          { sticky: true, opacity: 0.97 }
        );
      },
    });
  }

  if (key === 'refuges') {
    return L.geoJSON(data, {
      pointToLayer: (f, ll) => L.marker(ll, { icon: mkRefugeIcon() }),
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindTooltip(
          `<div style="font-family:monospace;font-size:11px;line-height:1.7"><b style="color:#fcd34d">${p.name}</b><br/>${p.tipus || ''} ${p.altitude ? `· ${p.altitude} m` : ''}<br/>${p.calendari ? `<span style="color:#9ca3af">${p.calendari}</span>` : ''}</div>`,
          { sticky: true, opacity: 0.97 }
        );
      },
    });
  }

  if (key === 'attractions') {
    return L.geoJSON(data, {
      pointToLayer: (f, ll) => L.marker(ll, { icon: mkAttractionIcon() }),
      onEachFeature: (f, lyr) => {
        const p = f.properties;
        lyr.bindTooltip(
          `<div style="font-family:monospace;font-size:11px;line-height:1.7"><b style="color:#c4b5fd">${p.name}</b><br/><span style="color:#9ca3af">${p.parish || ''}</span></div>`,
          { sticky: true, opacity: 0.97 }
        );
      },
    });
  }

  if (key === 'btt') {
    return L.geoJSON(data, {
      style: { color: '#f97316', weight: 2, opacity: 0.75 },
      onEachFeature: (f, lyr) => {
        lyr.bindTooltip(
          `<div style="font-family:monospace;font-size:11px"><b style="color:#fb923c">${f.properties.name || 'BTT trail'}</b></div>`,
          { sticky: true, opacity: 0.97 }
        );
      },
    });
  }

  if (key === 'cycling') {
    return L.geoJSON(data, {
      style: { color: '#06b6d4', weight: 2, opacity: 0.75 },
      onEachFeature: (f, lyr) => {
        lyr.bindTooltip(
          `<div style="font-family:monospace;font-size:11px"><b style="color:#22d3ee">${f.properties.name || 'Cycling route'}</b></div>`,
          { sticky: true, opacity: 0.97 }
        );
      },
    });
  }

  if (key === 'corona') {
    return L.geoJSON(data, {
      style: feat => ({ color: STAGE_COLORS[(feat.properties.stage || 1) - 1] || '#f59e0b', weight: 3, opacity: 0.85 }),
      onEachFeature: (f, lyr) => {
        lyr.bindTooltip(
          `<div style="font-family:monospace;font-size:11px"><b style="color:#fcd34d">${f.properties.name || `Etapa ${f.properties.stage}`}</b><br/><span style="color:#9ca3af">Corona de Llacs · Stage ${f.properties.stage}</span></div>`,
          { sticky: true, opacity: 0.97 }
        );
      },
    });
  }

  return L.geoJSON(data);
}

export default function TourismMapView() {
  const mapRef         = useRef(null);
  const instanceRef    = useRef(null);
  const skiRendererRef = useRef(null);
  const layersRef      = useRef({});

  const [vis, setVis] = useState(INIT_VIS);

  useEffect(() => {
    if (!mapRef.current || instanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [42.545709, 1.598780], zoom: 11,
      zoomSnap: 0, zoomControl: false, attributionControl: false,
      scrollWheelZoom: false, doubleClickZoom: false,
      touchZoom: false, boxZoom: false, keyboard: false, dragging: false,
    });
    instanceRef.current = map;
    map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] });
    map.on('resize', () => { map.invalidateSize(); map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] }); });

    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18 }
    ).addTo(map);
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18, opacity: 0.6 }
    ).addTo(map);

    addAndorraBoundary(map);
    [
      [42.694543, 1.393847], [42.697242, 1.801074],
      [42.394176, 1.39849],  [42.396861, 1.803713],
    ].forEach(([lat, lon]) => {
      L.circleMarker([lat, lon], { radius: 5, fillColor: '#ff3333', color: '#ffffff', weight: 2, fillOpacity: 1 }).addTo(map);
    });

    const files = [
      { key: 'ski',         url: '/tourism_ski_areas.geojson' },
      { key: 'peaks',       url: '/tourism_peaks.geojson' },
      { key: 'refuges',     url: '/tourism_refuges.geojson' },
      { key: 'attractions', url: '/tourism_attractions.geojson' },
      { key: 'btt',         url: '/tourism_btt.geojson' },
      { key: 'cycling',     url: '/tourism_cycling.geojson' },
      { key: 'corona',      url: '/tourism_corona_llacs.geojson' },
    ];

    files.forEach(({ key, url }) => {
      fetch(url)
        .then(r => r.json())
        .then(data => {
          const layer = buildLayer(key, data, skiRendererRef);
          layersRef.current[key] = layer;
          if (INIT_VIS[key]) layer.addTo(map);
          if (key === 'ski') {
            requestAnimationFrame(() => {
              const canvas = skiRendererRef.current?._container;
              if (canvas) canvas.style.opacity = '0.72';
            });
          }
        })
        .catch(err => console.warn(`tourism ${key}:`, err));
    });

    return () => { map.remove(); instanceRef.current = null; };
  }, []);

  useEffect(() => {
    const map = instanceRef.current;
    if (!map) return;
    Object.entries(vis).forEach(([key, show]) => {
      const layer = layersRef.current[key];
      if (!layer) return;
      if (show) layer.addTo(map);
      else      map.removeLayer(layer);
    });
  }, [vis]);

  const toggle = key => setVis(v => ({ ...v, [key]: !v[key] }));

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

      {/* Map */}
      <div ref={mapRef} style={{ position: 'absolute', inset: 0, background: '#0d0d0d' }} />
      <MapMask mapInstance={instanceRef} />

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
