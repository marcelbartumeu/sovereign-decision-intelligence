import { useEffect, useRef, useState, useCallback } from 'react';
import { useLockedMapbox } from '../hooks/useLockedMapbox';
import { addDataLayer, attachHoverPopup, whenStyleReady, DEFAULT_MAP_STYLE } from '../utils/mapboxBase';
import { OVERLAY_SCENARIOS } from '../utils/chartUtils';
import 'mapbox-gl/dist/mapbox-gl.css';

// Overlay scenario index → geojson filename
const SCENARIO_FILE = { 1: 'overgrowth', 2: 'degrowth', 3: 'continuity', 4: 'density' };

// Scenario-specific growth curves (deliberately exaggerated so differences are visible)
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
  if (scIdx === 2) {
    if (delta >= 0) return `rgba(${r},${g},${b},${0.35 + s * 0.45})`;
    return `rgba(189,6,56,${0.30 + s * 0.50})`;
  }
  if (delta <= 0) return 'rgba(100,100,120,0.22)';
  return `rgba(${r},${g},${b},${0.30 + s * 0.60})`;
}

function fillFor(scIdx, p, year) {
  if (p.buildable === false) return 'rgba(0,0,0,0)';
  return scenarioFill(scIdx, p.pop_2024 || 0, p.pop_2049 || 0, year) || 'rgba(0,0,0,0)';
}

function computeFC(scIdx, raw, year) {
  return {
    ...raw,
    features: raw.features.map(f => ({
      ...f,
      properties: { ...f.properties, _fill: fillFor(scIdx, f.properties || {}, year) },
    })),
  };
}

export default function GrowthMapView({ overlayEnabled = {}, selectedYear = 2049, visible = true, mapStyle = DEFAULT_MAP_STYLE }) {
  const containerRef    = useRef(null);
  const dataCache       = useRef({});   // scIdx → raw GeoJSON
  const constraintData  = useRef(null);
  const yearRef         = useRef(selectedYear);
  const overlayRef      = useRef(overlayEnabled);
  const showConstrRef   = useRef(true);
  const refreshTimer    = useRef(null);

  const [showConstraints, setShowConstraints] = useState(true);

  // ── Add / update a single scenario layer ───────────────────────────────────
  const addScenario = useCallback((map, idx) => {
    const raw = dataCache.current[idx];
    if (!raw) return;
    const srcId   = `growth-src-${idx}`;
    const layerId = `growth-${idx}`;
    const enabled = !!overlayRef.current[idx];

    if (!map.getSource(srcId)) {
      map.addSource(srcId, { type: 'geojson', data: computeFC(idx, raw, yearRef.current) });
      addDataLayer(map, {
        id: layerId, type: 'fill', source: srcId,
        layout: { visibility: enabled ? 'visible' : 'none' },
        paint: { 'fill-color': ['get', '_fill'], 'fill-opacity': 1, 'fill-outline-color': 'rgba(0,0,0,0.04)' },
      });
      const sc = OVERLAY_SCENARIOS.find(s => s.index === idx);
      attachHoverPopup(map, layerId, (f) => {
        const p    = f.properties || {};
        const p24  = p.pop_2024 || 0;
        const p49  = p.pop_2049 || 0;
        const popY = interp(p24, p49, yearRef.current, idx);
        const d    = popY - p24;
        if (popY <= 0.5 && p24 <= 0.5) return null;
        return `<div style="font-family:monospace;font-size:11px;line-height:1.7">
          <b style="color:${sc?.color}">${sc?.label}</b> · <span style="color:#9ca3af">${p.accessibility || ''}</span><br/>
          ${p.altitude ? `${p.altitude} m` : ''}${p.slope > 0 ? ` · slope ${p.slope}°` : ''}<br/>
          2024: ${p24.toFixed(0)}<br/>${yearRef.current}: <b>${popY.toFixed(0)}</b><br/>
          Δ ${d >= 0 ? '+' : ''}${d.toFixed(0)}</div>`;
      });
    } else if (enabled) {
      map.getSource(srcId).setData(computeFC(idx, raw, yearRef.current));
    }
    if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', enabled ? 'visible' : 'none');
  }, []);

  const addConstraints = useCallback((map) => {
    if (!constraintData.current || map.getSource('growth-constraints')) return;
    map.addSource('growth-constraints', { type: 'geojson', data: constraintData.current });
    addDataLayer(map, {
      id: 'growth-constraints', type: 'fill', source: 'growth-constraints',
      layout: { visibility: showConstrRef.current ? 'visible' : 'none' },
      paint: { 'fill-color': ['get', '_color'], 'fill-opacity': 0.45 },
    });
    attachHoverPopup(map, 'growth-constraints', (f) => {
      const p = f.properties || {};
      return `<div style="font-family:monospace;font-size:11px;line-height:1.6">
        <b style="color:#f87171">${p.reason || 'constrained'}</b><br/>
        ${p.altitude ? `${p.altitude} m` : ''}${p.slope > 0 ? ` · slope ${p.slope}°` : ''}</div>`;
    });
  }, []);

  const addOverlays = useCallback((map) => {
    addConstraints(map);
    Object.keys(SCENARIO_FILE).forEach(k => addScenario(map, Number(k)));
  }, [addConstraints, addScenario]);

  const { mapRef } = useLockedMapbox(containerRef, mapStyle, addOverlays);

  // ── Constraints data (fetched once) ────────────────────────────────────────
  useEffect(() => {
    fetch('/growth_constraints.geojson')
      .then(r => r.json())
      .then(data => {
        data.features.forEach(f => {
          f.properties._color = f.properties.protected ? '#166534' : '#7c2d12';
        });
        constraintData.current = data;
        whenStyleReady(mapRef.current, () => addConstraints(mapRef.current));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    showConstrRef.current = showConstraints;
    const map = mapRef.current;
    if (map && map.getLayer('growth-constraints')) {
      map.setLayoutProperty('growth-constraints', 'visibility', showConstraints ? 'visible' : 'none');
    }
  }, [showConstraints, mapRef]);

  // ── Refresh scenario layers when overlay / year changes ────────────────────
  const refreshLayers = useCallback(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    Object.entries(SCENARIO_FILE).forEach(([idxStr, fname]) => {
      const idx = Number(idxStr);
      if (overlayRef.current[idx] && !dataCache.current[idx]) {
        fetch(`/growth_${fname}.geojson`)
          .then(r => r.json())
          .then(data => {
            dataCache.current[idx] = data;
            const m = mapRef.current;
            if (m && m.isStyleLoaded() && overlayRef.current[idx]) addScenario(m, idx);
          })
          .catch(() => {});
      } else if (dataCache.current[idx]) {
        addScenario(map, idx);
      }
    });
  }, [addScenario, mapRef]);

  useEffect(() => {
    yearRef.current    = selectedYear;
    overlayRef.current = overlayEnabled;
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => whenStyleReady(mapRef.current, refreshLayers), 80);
    return () => clearTimeout(refreshTimer.current);
  }, [overlayEnabled, selectedYear, refreshLayers]);

  useEffect(() => {
    if (visible) { const map = mapRef.current; if (map) { map.resize(); refreshLayers(); } }
  }, [visible, refreshLayers, mapRef]);

  const enabledScenarios = OVERLAY_SCENARIOS.filter(s => s.index > 0 && overlayEnabled[s.index]);

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      {/* Toolbar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 48, zIndex: 1000,
        display: 'flex', gap: '0.4rem', flexWrap: 'nowrap', overflow: 'hidden',
        padding: '0 1rem', alignItems: 'center',
        background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <button className={`acc-layer-btn${showConstraints ? ' active' : ''}`} onClick={() => setShowConstraints(v => !v)}>
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
            border: `1px solid ${s.color}44`, background: `${s.color}12`,
          }}>{s.label}</span>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--muted)', letterSpacing: '.06em' }}>
          2024 → {selectedYear}
        </span>
      </div>

      <div ref={containerRef} style={{ position: 'absolute', inset: 0, background: '#000' }} />

      {/* Legend */}
      <div className="acc-map-legend" style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 36, zIndex: 1000, flexWrap: 'nowrap', overflow: 'hidden', background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)' }}>
        {enabledScenarios.map(s => (
          <span key={s.index} className="acc-legend-item">
            <span className="acc-dot" style={{ background: s.color, borderRadius: 2 }} />{s.label}
          </span>
        ))}
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#166534', borderRadius: 2 }} />Protected</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#7c2d12', borderRadius: 2 }} />Slope / altitude constrained</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--muted)', letterSpacing: '.06em' }}>
          POPULATION GROWTH · HOVER FOR DETAILS
        </span>
      </div>
    </div>
  );
}
