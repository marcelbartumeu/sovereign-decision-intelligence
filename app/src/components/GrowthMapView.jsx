import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import { addAndorraBoundary } from '../utils/andorraBoundary';
import { OVERLAY_SCENARIOS } from '../utils/chartUtils';
import MapMask from './MapMask';

const PROJECTION_BOUNDS = [[42.394176, 1.393847], [42.697242, 1.803713]];
const PROJECTION_CORNERS = [
  [42.694543, 1.393847],
  [42.697242, 1.801074],
  [42.394176, 1.39849],
  [42.396861, 1.803713],
];

// Overlay scenario index → geojson filename
const SCENARIO_FILE = {
  1: 'overgrowth',
  2: 'degrowth',
  3: 'continuity',
  4: 'density',
};

// Scenario-specific growth curves (deliberately exaggerated so differences are visible on map):
//   Overgrowth (1): cubic — nearly flat 2024–2038, then explosive surge
//   Degrowth   (2): cube-root — ~65% of decline done by 2032, then plateau
//   Continuity (3): smoothstep S-curve — slow start, steady middle, flattens at end
//   Density    (4): smootherstep — very flat until 2038, sharp infill phase 2038-2049
function growthCurve(t, scIdx) {
  switch (scIdx) {
    case 1: return t * t * t;
    case 2: return Math.cbrt(t);
    case 3: return t * t * (3 - 2 * t);
    case 4: return t * t * t * (t * (t * 6 - 15) + 10);
    default: return t;
  }
}

function interp(pop2024, pop2049, year, scIdx) {
  const t = Math.max(0, Math.min(1, (year - 2024) / 25));
  return pop2024 + (pop2049 - pop2024) * growthCurve(t, scIdx);
}

// Base RGB values matching OVERLAY_SCENARIOS colors exactly
const SCENARIO_RGB = {
  1: [189, 6,   56],   // #bd0638 Overgrowth
  2: [7,   111, 55],   // #076f37 Degrowth
  3: [41,  77,  175],  // #294daf Continuity
  4: [234, 179, 8],    // #eab308 Density
};

function scenarioFill(scIdx, pop2024, pop2049, year) {
  const popY  = interp(pop2024, pop2049, year, scIdx);
  const delta = popY - pop2024;

  if (popY <= 0 && pop2024 <= 0) return null;

  const pct = pop2024 > 0 ? Math.abs(delta / pop2024) * 100 : (popY > 0 ? 100 : 0);
  const s   = Math.min(pct / 120, 1);
  const [r, g, b] = SCENARIO_RGB[scIdx] || [150, 150, 150];

  // Degrowth: positive delta = scenario color, negative = depopulation red
  if (scIdx === 2) {
    if (delta >= 0) return `rgba(${r},${g},${b},${0.35 + s * 0.45})`;
    return `rgba(189,6,56,${0.30 + s * 0.50})`; // depopulation uses Overgrowth red
  }

  if (delta <= 0) return 'rgba(100,100,120,0.22)';
  return `rgba(${r},${g},${b},${0.30 + s * 0.60})`;
}

export default function GrowthMapView({ overlayEnabled = {}, selectedYear = 2049, visible = true }) {
  const mapRef        = useRef(null);
  const instanceRef   = useRef(null);
  const constraintRef = useRef(null);
  const dataCache     = useRef({});  // scIdx → GeoJSON
  const layersRef     = useRef({});  // scIdx → L.geoJSON layer
  const yearRef       = useRef(selectedYear);
  const overlayRef    = useRef(overlayEnabled);
  const refreshTimer  = useRef(null);

  const [showConstraints, setShowConstraints] = useState(true);

  // ── Init map once ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || instanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [42.545709, 1.598780], zoom: 11,
      zoomSnap: 0,
      zoomControl: false, attributionControl: false,
      scrollWheelZoom: false, doubleClickZoom: false,
      touchZoom: false, boxZoom: false,
      dragging: false, keyboard: false,
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
      { maxZoom: 18, opacity: 0.7 }
    ).addTo(map);

    addAndorraBoundary(map);
    PROJECTION_CORNERS.forEach(([lat, lon]) => {
      L.circleMarker([lat, lon], { radius: 5, fillColor: '#ff3333', color: '#ffffff', weight: 2, fillOpacity: 1 }).addTo(map);
    });

    return () => { map.remove(); instanceRef.current = null; };
  }, []);

  // ── Constraints layer ──────────────────────────────────────────────────────
  useEffect(() => {
    const map = instanceRef.current;
    if (!map) return;
    fetch('/growth_constraints.geojson')
      .then(r => r.json())
      .then(data => {
        const layer = L.geoJSON(data, {
          style: f => ({
            fillColor:   f.properties.protected ? '#166534' : '#7c2d12',
            fillOpacity: 0.45,
            color:       'transparent',
            weight:      0,
          }),
          onEachFeature: (f, lyr) => {
            const p = f.properties;
            lyr.bindTooltip(
              `<div style="font-family:monospace;font-size:11px;line-height:1.6">
                <b style="color:#f87171">${p.reason || 'constrained'}</b><br/>
                ${p.altitude ? `${p.altitude} m` : ''}${p.slope > 0 ? ` · slope ${p.slope}°` : ''}
              </div>`,
              { sticky: true, opacity: 0.95 }
            );
          },
        });
        layer.addTo(map);
        constraintRef.current = layer;
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instanceRef.current]);

  useEffect(() => {
    const map = instanceRef.current;
    const layer = constraintRef.current;
    if (!map || !layer) return;
    if (showConstraints) layer.addTo(map); else map.removeLayer(layer);
  }, [showConstraints]);

  // ── Build a GeoJSON layer for one scenario at a given year ─────────────────
  const buildLayer = useCallback((scIdx, data, year) => {
    const sc = OVERLAY_SCENARIOS.find(s => s.index === scIdx);
    return L.geoJSON(data, {
      renderer: L.canvas({ padding: 0.5, tolerance: 0 }),
      style: feat => {
        const { pop_2024 = 0, pop_2049 = 0, buildable } = feat.properties;
        if (buildable === false) return { fillOpacity: 0, stroke: false };
        const fill = scenarioFill(scIdx, pop_2024, pop_2049, year);
        if (!fill) return { fillOpacity: 0, stroke: false };
        return { fillColor: fill, fillOpacity: 1, color: 'rgba(0,0,0,0.04)', weight: 0.3 };
      },
      onEachFeature: (feat, lyr) => {
        const p     = feat.properties;
        const p24   = p.pop_2024 || 0;
        const p49   = p.pop_2049 || 0;
        const popY  = interp(p24, p49, year, scIdx);
        const delta = popY - p24;
        if (popY > 0.5 || p24 > 0.5) {
          lyr.bindTooltip(
            `<div style="font-family:monospace;font-size:11px;line-height:1.7">
              <b style="color:${sc?.color}">${sc?.label}</b> · <span style="color:#9ca3af">${p.accessibility || ''}</span><br/>
              ${p.altitude ? `${p.altitude} m` : ''}${p.slope > 0 ? ` · slope ${p.slope}°` : ''}<br/>
              2024: ${p24.toFixed(0)}<br/>
              ${year}: <b>${popY.toFixed(0)}</b><br/>
              Δ ${delta >= 0 ? '+' : ''}${delta.toFixed(0)}
            </div>`,
            { sticky: true, opacity: 0.97 }
          );
        }
      },
    });
  }, []);

  // ── Refresh all scenario layers when overlay or year changes ───────────────
  const refreshLayers = useCallback((overlay, year) => {
    const map = instanceRef.current;
    if (!map || !map.getContainer()) return;

    Object.entries(SCENARIO_FILE).forEach(([idxStr, fname]) => {
      const idx      = Number(idxStr);
      const enabled  = !!overlay[idx];
      const existing = layersRef.current[idx];

      if (!enabled) {
        try { if (existing) map.removeLayer(existing); } catch (_) {}
        layersRef.current[idx] = null;
        return;
      }

      if (dataCache.current[idx]) {
        try { if (existing) map.removeLayer(existing); } catch (_) {}
        try {
          const newLayer = buildLayer(idx, dataCache.current[idx], year);
          newLayer.addTo(map);
          layersRef.current[idx] = newLayer;
        } catch (_) {}
      } else {
        fetch(`/growth_${fname}.geojson`)
          .then(r => r.json())
          .then(data => {
            dataCache.current[idx] = data;
            const m = instanceRef.current;
            if (!m || !m.getContainer()) return;
            if (!overlayRef.current[idx]) return;
            try { if (layersRef.current[idx]) m.removeLayer(layersRef.current[idx]); } catch (_) {}
            try {
              const newLayer = buildLayer(idx, data, yearRef.current);
              newLayer.addTo(m);
              layersRef.current[idx] = newLayer;
            } catch (_) {}
          })
          .catch(() => {});
      }
    });
  }, [buildLayer]);

  useEffect(() => {
    yearRef.current    = selectedYear;
    overlayRef.current = overlayEnabled;
    // Debounce rapid changes (e.g. fast Arduino encoder sweeps)
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => {
      refreshLayers(overlayRef.current, yearRef.current);
    }, 80);
    return () => clearTimeout(refreshTimer.current);
  }, [overlayEnabled, selectedYear, refreshLayers]);

  // When the tab becomes visible again, force Leaflet to re-render and re-sync layers
  useEffect(() => {
    if (!visible) return;
    const map = instanceRef.current;
    if (!map) return;
    map.invalidateSize();
    refreshLayers(overlayRef.current, yearRef.current);
  }, [visible, refreshLayers]); // eslint-disable-line react-hooks/exhaustive-deps

  const enabledScenarios = OVERLAY_SCENARIOS.filter(s => s.index > 0 && overlayEnabled[s.index]);

  return (
    <div style={{ position: 'relative', height: '100%' }}>

      {/* Toolbar — overlay, semi-transparent */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 48, zIndex: 1000,
        display: 'flex', gap: '0.4rem', flexWrap: 'nowrap', overflow: 'hidden',
        padding: '0 1rem', alignItems: 'center',
        background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <button
          className={`acc-layer-btn${showConstraints ? ' active' : ''}`}
          onClick={() => setShowConstraints(v => !v)}
        >
          Constraints
        </button>
        {enabledScenarios.length === 0 && (
          <span style={{ fontSize: '0.72rem', color: 'var(--muted)', marginLeft: '0.5rem', opacity: 0.6 }}>
            No scenarios active — use the overlay toggles above
          </span>
        )}
        {enabledScenarios.map(s => (
          <span key={s.index} style={{
            fontSize: '0.72rem', color: s.color, marginLeft: '0.25rem',
            padding: '2px 8px', borderRadius: 4,
            border: `1px solid ${s.color}44`,
            background: `${s.color}12`,
          }}>
            {s.label}
          </span>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--muted)', letterSpacing: '.06em' }}>
          2024 → {selectedYear}
        </span>
      </div>

      {/* Map — full coverage */}
      <div ref={mapRef} style={{ position: 'absolute', inset: 0, background: '#0d0d0d' }} />
      <MapMask mapInstance={instanceRef} />

      {/* Legend — overlay at bottom */}
      <div className="acc-map-legend" style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 36, zIndex: 1000, flexWrap: 'nowrap', overflow: 'hidden', background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)' }}>
        {enabledScenarios.map(s => (
          <span key={s.index} className="acc-legend-item">
            <span className="acc-dot" style={{ background: s.color, borderRadius: 2 }} />
            {s.label}
          </span>
        ))}
        <span className="acc-legend-item">
          <span className="acc-dot" style={{ background: '#166534', borderRadius: 2 }} />
          Protected
        </span>
        <span className="acc-legend-item">
          <span className="acc-dot" style={{ background: '#7c2d12', borderRadius: 2 }} />
          Slope / altitude constrained
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--muted)', letterSpacing: '.06em' }}>
          POPULATION GROWTH · HOVER FOR DETAILS
        </span>
      </div>
    </div>
  );
}
