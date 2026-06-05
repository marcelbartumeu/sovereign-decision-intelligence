import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import { BUS_FREQUENCIES } from '../../../model/bus_frequencies.js';
import { addAndorraBoundary } from '../utils/andorraBoundary';
import MapMask from './MapMask';

// ── Accessibility colour map ──────────────────────────────────────────────────
const ACC_COLORS = { walk: '#4ade80', bike: '#fbbf24', 'bus/car': '#f87171', default: '#374151' };
const accColor = v => ACC_COLORS[v] || ACC_COLORS.default;

// ── Geo helpers for bus animation ────────────────────────────────────────────
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function buildCumDist(coords) {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) {
    const [lat1, lon1] = coords[i - 1];
    const [lat2, lon2] = coords[i];
    cum.push(cum[i - 1] + haversineKm(lat1, lon1, lat2, lon2));
  }
  return cum;
}

function interpolate(coords, cumDist, km) {
  const total   = cumDist[cumDist.length - 1];
  const clamped = Math.max(0, Math.min(km, total));
  let lo = 0, hi = cumDist.length - 2;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (cumDist[mid + 1] < clamped) lo = mid + 1;
    else hi = mid;
  }
  const segLen = cumDist[lo + 1] - cumDist[lo];
  const t = segLen > 0 ? (clamped - cumDist[lo]) / segLen : 0;
  const [lat1, lon1] = coords[lo];
  const [lat2, lon2] = coords[lo + 1] || coords[lo];
  return [lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t];
}

function busIcon(ref, colour) {
  return L.divIcon({
    html: `<div style="
      background:${colour};color:#fff;
      padding:2px 6px;border-radius:3px;
      font-size:9px;font-weight:700;
      font-family:'IBM Plex Mono',monospace;
      letter-spacing:0.05em;white-space:nowrap;
      box-shadow:0 1px 4px rgba(0,0,0,0.6);
      border:1px solid rgba(255,255,255,0.25);
      pointer-events:none;
    ">${ref.slice(0, 4)}</div>`,
    className: '',
    iconSize:   [36, 16],
    iconAnchor: [18, 8],
  });
}

const DAY_MINS   = 24 * 60;
const parseMin   = hhmm => { const [h, m] = (hhmm || '06:00').split(':').map(Number); return h * 60 + m; };
const toHHMM     = abs  => { const t = abs % DAY_MINS; const h = Math.floor(t / 60); const m = Math.floor(t % 60); return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`; };

function seedSpawns(refs, dt, startAbs) {
  const dayOffset = Math.floor(startAbs / DAY_MINS) * DAY_MINS;
  const out = {};
  for (const ref of refs) {
    const freq = BUS_FREQUENCIES.find(l => l.ref === ref);
    if (!freq) continue;
    const sched   = freq[dt] || freq.weekday;
    const first   = parseMin(sched.first_bus);
    const headway = sched.headway_min || sched.peak_headway_min || 30;
    out[ref] = { fwd: dayOffset + first, bwd: dayOffset + first + headway / 2 };
  }
  return out;
}

const SPEEDS = [
  { label: '10×',  value: 10  },
  { label: '30×',  value: 30  },
  { label: '60×',  value: 60  },
  { label: '120×', value: 120 },
  { label: '300×', value: 300 },
];

// ── Layer config ──────────────────────────────────────────────────────────────
const LAYER_BTNS = [
  ['hexagons',  'Hexagons'],
  ['streets',   'Streets'],
  ['schools',   'Schools'],
  ['busRoutes', 'Bus Lines'],
  ['busStops',  'Bus Stops'],
  ['busAnim',   'Live Buses'],
];

const INIT_VIS = {
  hexagons: true, streets: true, schools: true,
  busRoutes: true, busStops: true,
  busAnim: true,
};

export default function AccessibilityMapView() {
  const mapRef         = useRef(null);
  const mapInstanceRef = useRef(null);
  const layersRef      = useRef({});
  const visRef         = useRef({ ...INIT_VIS });
  const [vis, setVis]  = useState(INIT_VIS);
  const [error, setError] = useState(null);

  // ── Bus animation state ───────────────────────────────────────────────────
  const rafRef       = useRef(null);
  const routeDataRef = useRef({});   // ref → { coords, cumDist, totalKm, colour }
  const busStateRef  = useRef(null);
  const speedRef     = useRef(60);
  const dayTypeRef   = useRef('weekday');
  const [simTime,  setSimTime]  = useState(6 * 60);
  const [busSpeed, setBusSpeed] = useState(60);
  const [busDay,   setBusDay]   = useState('weekday');

  // ── Animation tick ────────────────────────────────────────────────────────
  const tick = useCallback((rafTs) => {
    if (!visRef.current.busAnim) return;
    const state = busStateRef.current;
    const map   = mapInstanceRef.current;
    if (!state || !map) { rafRef.current = requestAnimationFrame(tick); return; }

    const elapsed = state.lastRafTs == null ? 0 : (rafTs - state.lastRafTs) / 1000;
    state.lastRafTs = rafTs;

    const simDelta = elapsed * speedRef.current / 60;
    state.simMinutes += simDelta;
    const simNow = state.simMinutes;

    const dt     = dayTypeRef.current;
    const routes = routeDataRef.current;

    // Spawn
    for (const ref of Object.keys(routes)) {
      const freq = BUS_FREQUENCIES.find(l => l.ref === ref);
      if (!freq) continue;
      const sched   = freq[dt] || freq.weekday;
      const headway = sched.headway_min || sched.peak_headway_min || 30;
      const lastTod = parseMin(sched.last_bus);
      const route   = routes[ref];
      const spawnNS = state.nextSpawn[ref] || { fwd: simNow, bwd: simNow + headway / 2 };

      for (const dir of ['fwd', 'bwd']) {
        while (spawnNS[dir] <= simNow) {
          const thisDayOffset = Math.floor(spawnNS[dir] / DAY_MINS) * DAY_MINS;
          if (spawnNS[dir] > thisDayOffset + lastTod + headway) {
            const nextBase = (Math.floor(spawnNS[dir] / DAY_MINS) + 1) * DAY_MINS;
            const firstTod = parseMin(sched.first_bus);
            spawnNS[dir]   = nextBase + firstTod + (dir === 'bwd' ? headway / 2 : 0);
            break;
          }
          const direction = dir === 'fwd' ? 1 : -1;
          const startKm   = dir === 'fwd' ? 0 : route.totalKm;
          const marker = L.marker(
            interpolate(route.coords, route.cumDist, startKm),
            { icon: busIcon(ref, route.colour), zIndexOffset: 1000 }
          ).addTo(map);
          state.buses.push({
            id: ++state.busIdCounter,
            ref,
            coords:     route.coords,
            cumDist:    route.cumDist,
            totalKm:    route.totalKm,
            kmTraveled: startKm,
            direction,
            marker,
          });
          spawnNS[dir] += headway;
        }
      }
      state.nextSpawn[ref] = spawnNS;
    }

    // Move
    const kmStep = 0.5 * simDelta; // ~30 km/h ÷ 60
    const toRemove = [];
    for (const bus of state.buses) {
      bus.kmTraveled += bus.direction * kmStep;
      if (bus.kmTraveled < 0 || bus.kmTraveled > bus.totalKm) {
        toRemove.push(bus);
      } else {
        bus.marker.setLatLng(interpolate(bus.coords, bus.cumDist, bus.kmTraveled));
      }
    }
    for (const bus of toRemove) {
      bus.marker.remove();
      const idx = state.buses.indexOf(bus);
      if (idx !== -1) state.buses.splice(idx, 1);
    }

    if (Math.round(simNow * 10) % 2 === 0) setSimTime(Math.floor(simNow % DAY_MINS));
    rafRef.current = requestAnimationFrame(tick);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stop animation + clear markers ───────────────────────────────────────
  const stopAnim = useCallback(() => {
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
    const state = busStateRef.current;
    if (state) { for (const bus of state.buses) bus.marker.remove(); state.buses = []; }
  }, []);

  // ── Layer toggle ─────────────────────────────────────────────────────────
  const toggle = key => {
    const next = { ...visRef.current, [key]: !visRef.current[key] };
    visRef.current = next;
    setVis({ ...next });
    const map   = mapInstanceRef.current;
    const layer = layersRef.current[key];
    if (map && layer) { next[key] ? map.addLayer(layer) : map.removeLayer(layer); }

    if (key === 'busAnim') {
      if (next.busAnim) {
        if (busStateRef.current) busStateRef.current.lastRafTs = null;
        rafRef.current = requestAnimationFrame(tick);
      } else {
        stopAnim();
      }
    }
  };

  // ── Map + data init ──────────────────────────────────────────────────────
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
    addAndorraBoundary(map);
    [
      [42.694543, 1.393847], [42.697242, 1.801074],
      [42.394176, 1.39849],  [42.396861, 1.803713],
    ].forEach(([lat, lon]) => {
      L.circleMarker([lat, lon], { radius: 5, fillColor: '#ff3333', color: '#ffffff', weight: 2, fillOpacity: 1 }).addTo(map);
    });

    const _v = Date.now();
    Promise.all([
      fetch(`/model/accessibility_population.geojson?v=${_v}`, { signal }).then(r => r.json()),
      fetch(`/model/accessibility_streets.geojson?v=${_v}`,   { signal }).then(r => r.json()),
      fetch(`/model/accessibility_schools.geojson?v=${_v}`,   { signal }).then(r => r.json()),
      fetch(`/model/bus_routes.geojson?v=${_v}`,              { signal }).then(r => r.json()),
      fetch(`/model/bus_stops.geojson?v=${_v}`,               { signal }).then(r => r.json()),
    ])
    .then(([popData, streetsData, schoolsData, busRoutesData, busStopsData]) => {
      const maxPop = Math.max(...popData.features.map(f => f.properties.population || 0));

      const hexLayer = L.geoJSON(popData, {
        style: f => {
          const pop = f.properties.population || 0;
          if (pop === 0) return { fillOpacity: 0, stroke: false };
          return { fillColor: accColor(f.properties.accessibility), fillOpacity: 0.15 + Math.sqrt(pop / maxPop) * 0.72, color: 'rgba(0,0,0,0)', weight: 0 };
        },
        onEachFeature: (f, layer) => {
          const p = f.properties;
          layer.on('mouseover', function () { this.setStyle({ weight: 1.5, color: '#fff', fillOpacity: 1 }); });
          layer.on('mouseout',  function () { hexLayer.resetStyle(this); });
          layer.bindPopup(`<b style="text-transform:capitalize">${p.accessibility || 'unknown'}</b><br>Population: <b>${(p.population || 0).toLocaleString()}</b>`);
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
        pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 6, fillColor: '#60a5fa', color: '#1d4ed8', weight: 1.5, fillOpacity: 0.9 }),
        onEachFeature: (f, layer) => layer.bindPopup(`<b>${f.properties.name || 'School'}</b>`),
      });
      layersRef.current.schools = schoolLayer;
      if (visRef.current.schools) schoolLayer.addTo(map);

      const busRoutesLayer = L.geoJSON(busRoutesData, {
        style: f => ({ color: f.properties.colour || '#fff', weight: 3.5, opacity: 0.85, lineCap: 'round', lineJoin: 'round' }),
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
        pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 4, fillColor: '#facc15', color: '#1e293b', weight: 1.5, fillOpacity: 0.95 }),
        onEachFeature: (f, layer) => {
          const p = f.properties;
          layer.bindPopup(`<b>${p.name}</b>${p.lines ? `<br>Lines: <b>${p.lines}</b>` : ''}`);
        },
      });
      layersRef.current.busStops = busStopsLayer;
      if (visRef.current.busStops) busStopsLayer.addTo(map);

      // ── Build route data for bus animation ──────────────────────────────
      const builtRoutes = {};
      busRoutesData.features.forEach(f => {
        const ref      = f.properties.ref;
        const colour   = f.properties.colour || '#ffffff';
        const freqData = BUS_FREQUENCIES.find(l => l.ref === ref);
        if (!freqData || freqData.days === 'discontinued') return;
        const coords  = f.geometry.coordinates.map(([lng, lat]) => [lat, lng]);
        const cumDist = buildCumDist(coords);
        builtRoutes[ref] = { coords, cumDist, totalKm: cumDist[cumDist.length - 1], colour };
      });
      routeDataRef.current = builtRoutes;
      const startMin = 6 * 60;
      busStateRef.current = {
        simMinutes:   startMin,
        lastRafTs:    null,
        busIdCounter: 0,
        buses:        [],
        nextSpawn:    seedSpawns(Object.keys(builtRoutes), dayTypeRef.current, startMin),
      };

      // Auto-start bus animation
      rafRef.current = requestAnimationFrame(tick);

      map.fitBounds([[42.394176, 1.393847], [42.697242, 1.803713]], { padding: [0, 0] });
    })
    .catch(err => { if (err.name !== 'AbortError') setError(true); });

    return () => {
      controller.abort();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      map.remove();
      mapInstanceRef.current = null;
      layersRef.current      = {};
      routeDataRef.current   = {};
      busStateRef.current    = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Bus animation controls ────────────────────────────────────────────────
  const changeSpeed = useCallback((v) => {
    speedRef.current = v;
    setBusSpeed(v);
  }, []);

  const changeDay = useCallback((dt) => {
    dayTypeRef.current = dt;
    setBusDay(dt);
    const state = busStateRef.current;
    if (!state) return;
    for (const bus of state.buses) bus.marker.remove();
    state.buses     = [];
    state.nextSpawn = seedSpawns(Object.keys(routeDataRef.current), dt, state.simMinutes);
  }, []);

  const resetBus = useCallback(() => {
    const state = busStateRef.current;
    if (!state) return;
    for (const bus of state.buses) bus.marker.remove();
    state.buses      = [];
    state.simMinutes = 6 * 60;
    state.lastRafTs  = null;
    state.nextSpawn  = seedSpawns(Object.keys(routeDataRef.current), dayTypeRef.current, 6 * 60);
    setSimTime(6 * 60);
  }, []);

  return (
    <div style={{ position: 'relative', height: '100%' }}>

      {/* Toolbar pill — floating overlay at top-center */}
      <div style={{
        position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
        zIndex: 1000, display: 'flex', gap: 6, flexWrap: 'wrap',
        alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(6px)',
        padding: '6px 10px', borderRadius: 10,
        border: '1px solid rgba(255,255,255,0.10)',
        maxWidth: 'calc(100% - 2rem)',
      }}>
        {LAYER_BTNS.map(([key, label]) => (
          <button
            key={key}
            className={`acc-layer-btn${vis[key] ? ' active' : ''}${key === 'busAnim' ? ' bus-anim-btn' : ''}`}
            onClick={() => toggle(key)}
            style={key === 'busAnim' && vis[key] ? {
              background: 'rgba(250,204,21,0.15)',
              borderColor: '#facc15',
              color: '#facc15',
            } : {}}
          >
            {key === 'busAnim' && vis[key] ? `▶ ${label}` : label}
          </button>
        ))}
      </div>

      {/* Bus animation controls — floating pill below the toolbar */}
      {vis.busAnim && (
        <div style={{
          position: 'absolute', top: 58, left: '50%', transform: 'translateX(-50%)',
          zIndex: 1001, maxWidth: 'calc(100% - 2rem)',
          display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap',
          justifyContent: 'center',
          padding: '6px 12px',
          background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(6px)',
          borderRadius: 10, border: '1px solid rgba(255,255,255,0.10)', fontSize: '0.7rem',
        }}>
          {/* Clock */}
          <div style={{
            background: 'var(--bg)', border: '1px solid #facc1555',
            padding: '3px 10px', borderRadius: 4,
            fontWeight: 700, fontSize: '0.85rem', letterSpacing: '0.1em',
            color: '#facc15', minWidth: 64, textAlign: 'center',
          }}>
            {toHHMM(simTime)}
          </div>

          <span style={{ color: 'var(--muted)' }}>SPEED</span>
          {SPEEDS.map(s => (
            <button key={s.value} onClick={() => changeSpeed(s.value)} style={{
              background: busSpeed === s.value ? '#facc15' : 'var(--surf2)',
              color: busSpeed === s.value ? '#000' : 'var(--text)',
              border: `1px solid ${busSpeed === s.value ? '#facc15' : 'var(--bdr)'}`,
              cursor: 'pointer', padding: '2px 8px', borderRadius: 3,
              fontFamily: 'var(--font)', fontSize: '0.67rem', fontWeight: 700,
            }}>
              {s.label}
            </button>
          ))}

          <span style={{ color: 'var(--muted)' }}>DAY</span>
          {['weekday', 'weekend'].map(dt => (
            <button key={dt} onClick={() => changeDay(dt)} style={{
              background: busDay === dt ? '#facc15' : 'var(--surf2)',
              color: busDay === dt ? '#000' : 'var(--text)',
              border: `1px solid ${busDay === dt ? '#facc15' : 'var(--bdr)'}`,
              cursor: 'pointer', padding: '2px 9px', borderRadius: 3,
              fontFamily: 'var(--font)', fontSize: '0.67rem', fontWeight: 700,
              textTransform: 'uppercase',
            }}>
              {dt}
            </button>
          ))}

          <button onClick={resetBus} style={{
            background: 'var(--surf2)', color: 'var(--text)',
            border: '1px solid var(--bdr)', cursor: 'pointer',
            padding: '2px 9px', borderRadius: 3,
            fontFamily: 'var(--font)', fontSize: '0.67rem',
          }}>
            ↺ Reset
          </button>
        </div>
      )}

      {/* Map — full coverage */}
      {error
        ? <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0d0d0d', color: '#9ca3af', fontSize: 12, textAlign: 'center', padding: '2rem' }}>
            Map data requires the Vite dev server
          </div>
        : <div ref={mapRef} style={{ position: 'absolute', inset: 0, background: '#0d0d0d' }} />
      }
      <MapMask mapInstance={mapInstanceRef} />

      {/* Legend — overlay at bottom */}
      <div className="acc-map-legend" style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 36, zIndex: 1000, flexWrap: 'nowrap', overflow: 'hidden', background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)' }}>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#4ade80' }} /> Walk</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#fbbf24' }} /> Bike</span>
        <span className="acc-legend-item"><span className="acc-dot" style={{ background: '#f87171' }} /> Bus/Car</span>
        <span className="acc-legend-item">
          <span style={{ display: 'inline-block', width: 14, height: 4, background: '#E63946', borderRadius: 2 }} /> Bus Lines
        </span>
        <span className="acc-legend-item">
          <span className="acc-dot" style={{ background: '#facc15', border: '2px solid #1e293b' }} /> Bus Stops
        </span>
      </div>
    </div>
  );
}
