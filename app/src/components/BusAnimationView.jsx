import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import { BUS_FREQUENCIES } from '../../../model/bus_frequencies.js';

// ── Geo helpers ──────────────────────────────────────────────────────────────
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

// ── Bus icon factory ──────────────────────────────────────────────────────────
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

// ── Time helpers ──────────────────────────────────────────────────────────────
const simToHHMM = (absMin) => {
  const todMin = absMin % (24 * 60);
  const h = Math.floor(todMin / 60);
  const m = Math.floor(todMin % 60);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

const parseMinutes = (hhmm) => {
  const [h, m] = (hhmm || '06:00').split(':').map(Number);
  return h * 60 + m;
};

const DAY_MINS = 24 * 60; // 1440

// ── Speed options ─────────────────────────────────────────────────────────────
const SPEEDS = [
  { label: '10×',  value: 10  },
  { label: '30×',  value: 30  },
  { label: '60×',  value: 60  },
  { label: '120×', value: 120 },
  { label: '300×', value: 300 },
];

// ── Lines to show in toggle bar (exclude night buses + discontinued) ───────────
const TOGGLE_LINES = BUS_FREQUENCIES.filter(
  l => l.days !== 'discontinued' && !l.ref.startsWith('BN')
);

const INITIAL_ACTIVE = Object.fromEntries(TOGGLE_LINES.map(l => [l.ref, true]));

// ── Build seed spawn state for a given day type ───────────────────────────────
function seedSpawns(routeRefs, dt, startAbsMin) {
  // startAbsMin: absolute simulation minutes at time of seeding (e.g. 6*60 = 360)
  const dayOffset = Math.floor(startAbsMin / DAY_MINS) * DAY_MINS;
  const spawns = {};
  for (const ref of routeRefs) {
    const freq = BUS_FREQUENCIES.find(l => l.ref === ref);
    if (!freq) continue;
    const sched    = freq[dt] || freq.weekday;
    const firstTod = parseMinutes(sched.first_bus);
    const headway  = sched.headway_min || sched.peak_headway_min || 30;
    spawns[ref] = {
      fwd: dayOffset + firstTod,
      bwd: dayOffset + firstTod + headway / 2,
    };
  }
  return spawns;
}

export default function BusAnimationView() {
  const mapRef         = useRef(null);
  const mapInstanceRef = useRef(null);
  const routeLayersRef = useRef({});
  const stateRef       = useRef(null);
  const rafRef         = useRef(null);
  const routeDataRef   = useRef({});

  const [playing,     setPlaying]     = useState(false);
  const [speed,       setSpeed]       = useState(60);
  const [dayType,     setDayType]     = useState('weekday');
  const [simTime,     setSimTime]     = useState(6 * 60);
  const [activeLines, setActiveLines] = useState(INITIAL_ACTIVE);
  const [busCounts,   setBusCounts]   = useState({});
  const [error,       setError]       = useState(null);

  const playingRef     = useRef(false);
  const speedRef       = useRef(60);
  const dayTypeRef     = useRef('weekday');
  const activeLinesRef = useRef({ ...INITIAL_ACTIVE });

  // ── Map init ─────────────────────────────────────────────────────────────────
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

    fetch(`/model/bus_routes.geojson?v=${Date.now()}`, { signal })
      .then(r => r.json())
      .then(data => {
        const built = {};

        data.features.forEach(f => {
          const ref      = f.properties.ref;
          const colour   = f.properties.colour || '#ffffff';
          const freqData = BUS_FREQUENCIES.find(l => l.ref === ref);
          if (!freqData || freqData.days === 'discontinued') return;

          // GeoJSON coords: [lng, lat] → swap to [lat, lng] for Leaflet
          const coords  = f.geometry.coordinates.map(([lng, lat]) => [lat, lng]);
          const cumDist = buildCumDist(coords);
          const totalKm = cumDist[cumDist.length - 1];

          built[ref] = { coords, cumDist, totalKm, colour };

          const polyline = L.polyline(coords, {
            color: colour, weight: 3, opacity: 0.7,
            lineCap: 'round', lineJoin: 'round',
          }).addTo(map);
          polyline.bindPopup(
            `<b>${ref}</b> — ${f.properties.name}<br><span style="opacity:0.7">${f.properties.operator || ''}</span>`
          );
          polyline.on('mouseover', function () { this.setStyle({ weight: 5, opacity: 1 }); this.bringToFront(); });
          polyline.on('mouseout',  function () { this.setStyle({ weight: 3, opacity: 0.7 }); });
          routeLayersRef.current[ref] = polyline;
        });

        routeDataRef.current = built;

        map.fitBounds([[42.394176, 1.393847], [42.697242, 1.803713]], { padding: [0, 0] });

        const startMin = 6 * 60;
        stateRef.current = {
          simMinutes:   startMin,  // accumulates indefinitely — no modulo wrap
          lastRafTs:    null,
          busIdCounter: 0,
          buses:        [],
          nextSpawn:    seedSpawns(Object.keys(built), dayTypeRef.current, startMin),
        };
      })
      .catch(err => { if (err.name !== 'AbortError') setError(true); });

    return () => {
      controller.abort();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      map.remove();
      mapInstanceRef.current  = null;
      routeLayersRef.current  = {};
      routeDataRef.current    = {};
      stateRef.current        = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Animation loop ────────────────────────────────────────────────────────────
  const tick = useCallback((rafTs) => {
    if (!playingRef.current) return;
    const state = stateRef.current;
    if (!state) { rafRef.current = requestAnimationFrame(tick); return; }

    const elapsed  = state.lastRafTs == null ? 0 : (rafTs - state.lastRafTs) / 1000;
    state.lastRafTs = rafTs;

    const simDelta = elapsed * speedRef.current / 60; // real sec → sim minutes
    state.simMinutes += simDelta;                      // no wrapping
    const simNow   = state.simMinutes;
    const todMin   = simNow % DAY_MINS;               // time-of-day for display

    const map     = mapInstanceRef.current;
    if (!map) { rafRef.current = requestAnimationFrame(tick); return; }

    const dt      = dayTypeRef.current;
    const activeL = activeLinesRef.current;
    const routes  = routeDataRef.current;

    // ── Spawn buses ──────────────────────────────────────────────────────────
    for (const ref of Object.keys(routes)) {
      if (!activeL[ref]) continue;
      const freq = BUS_FREQUENCIES.find(l => l.ref === ref);
      if (!freq) continue;
      const sched   = freq[dt] || freq.weekday;
      const headway = sched.headway_min || sched.peak_headway_min || 30;
      const lastTod = parseMinutes(sched.last_bus);
      const route   = routes[ref];
      const spawnNS = state.nextSpawn[ref] || { fwd: simNow, bwd: simNow + headway / 2 };

      for (const dir of ['fwd', 'bwd']) {
        // dayOffset for the day that this spawn belongs to
        while (spawnNS[dir] <= simNow) {
          const thisDayOffset = Math.floor(spawnNS[dir] / DAY_MINS) * DAY_MINS;
          const absLastMin    = thisDayOffset + lastTod;

          if (spawnNS[dir] > absLastMin + headway) {
            // Past last bus of this day — jump to first bus of next day
            const firstTod    = parseMinutes(sched.first_bus);
            const nextDayBase = (Math.floor(spawnNS[dir] / DAY_MINS) + 1) * DAY_MINS;
            spawnNS[dir] = nextDayBase + firstTod + (dir === 'bwd' ? headway / 2 : 0);
            break;
          }

          // Spawn a bus
          const direction = dir === 'fwd' ? 1 : -1;
          const startKm   = dir === 'fwd' ? 0 : route.totalKm;
          const marker = L.marker(
            interpolate(route.coords, route.cumDist, startKm),
            { icon: busIcon(ref, route.colour), zIndexOffset: 1000 }
          ).addTo(map);
          marker.bindTooltip(ref, { permanent: false, direction: 'top', offset: [0, -10] });
          state.buses.push({
            id:         ++state.busIdCounter,
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

    // ── Move buses ─────────────────────────────────────────────────────────
    const avgKmPerMin = 0.5; // ~30 km/h ÷ 60
    const kmStep = avgKmPerMin * simDelta;

    const counts   = {};
    const toRemove = [];

    for (const bus of state.buses) {
      bus.kmTraveled += bus.direction * kmStep;

      if (bus.kmTraveled < 0 || bus.kmTraveled > bus.totalKm) {
        toRemove.push(bus);
        continue;
      }

      if (activeL[bus.ref]) {
        const pos = interpolate(bus.coords, bus.cumDist, bus.kmTraveled);
        bus.marker.setLatLng(pos);
      }
      counts[bus.ref] = (counts[bus.ref] || 0) + 1;
    }

    for (const bus of toRemove) {
      bus.marker.remove();
      const idx = state.buses.indexOf(bus);
      if (idx !== -1) state.buses.splice(idx, 1);
    }

    // Update React state at ~15 fps
    if (Math.round(simNow * 10) % 2 === 0) {
      setSimTime(Math.floor(todMin));
      setBusCounts({ ...counts });
    }

    rafRef.current = requestAnimationFrame(tick);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Controls ──────────────────────────────────────────────────────────────────
  const togglePlay = useCallback(() => {
    const next = !playingRef.current;
    playingRef.current = next;
    setPlaying(next);
    if (next) {
      if (stateRef.current) stateRef.current.lastRafTs = null;
      rafRef.current = requestAnimationFrame(tick);
    } else {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    }
  }, [tick]);

  const changeSpeed = useCallback((v) => {
    speedRef.current = v;
    setSpeed(v);
  }, []);

  const changeDayType = useCallback((dt) => {
    dayTypeRef.current = dt;
    setDayType(dt);
    const state = stateRef.current;
    if (!state) return;
    for (const bus of state.buses) bus.marker.remove();
    state.buses = [];
    state.nextSpawn = seedSpawns(Object.keys(routeDataRef.current), dt, state.simMinutes);
  }, []);

  const resetTime = useCallback(() => {
    const state = stateRef.current;
    if (!state) return;
    for (const bus of state.buses) bus.marker.remove();
    state.buses      = [];
    state.simMinutes = 6 * 60;
    state.lastRafTs  = null;
    state.nextSpawn  = seedSpawns(Object.keys(routeDataRef.current), dayTypeRef.current, 6 * 60);
    setSimTime(6 * 60);
    setBusCounts({});
  }, []);

  const toggleLine = useCallback((ref) => {
    const next = { ...activeLinesRef.current, [ref]: !activeLinesRef.current[ref] };
    activeLinesRef.current = next;
    setActiveLines({ ...next });
    const map   = mapInstanceRef.current;
    const layer = routeLayersRef.current[ref];
    if (map && layer) {
      if (next[ref]) map.addLayer(layer);
      else map.removeLayer(layer);
    }
    const state = stateRef.current;
    if (!state) return;
    for (const bus of state.buses) {
      if (bus.ref !== ref) continue;
      if (next[ref]) { if (map && !map.hasLayer(bus.marker)) bus.marker.addTo(map); }
      else           { bus.marker.remove(); }
    }
  }, []);

  const totalBuses = Object.values(busCounts).reduce((s, n) => s + n, 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* ── Controls bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap',
        padding: '0.65rem 1rem', borderBottom: '1px solid var(--bdr)',
        background: 'var(--surf)', fontSize: '0.72rem',
      }}>
        <button onClick={togglePlay} style={{
          background: playing ? '#dc2626' : '#16a34a',
          color: '#fff', border: 'none', cursor: 'pointer',
          padding: '5px 14px', borderRadius: 4,
          fontFamily: 'var(--font)', fontSize: '0.72rem', fontWeight: 700,
          letterSpacing: '0.06em',
        }}>
          {playing ? '⏸ PAUSE' : '▶ PLAY'}
        </button>

        <button onClick={resetTime} style={{
          background: 'var(--surf2)', color: 'var(--text)',
          border: '1px solid var(--bdr)', cursor: 'pointer',
          padding: '5px 12px', borderRadius: 4,
          fontFamily: 'var(--font)', fontSize: '0.72rem',
        }}>
          ↺ RESET
        </button>

        {/* Sim clock */}
        <div style={{
          background: 'var(--bg)', border: '1px solid var(--bdr)',
          padding: '4px 14px', borderRadius: 4,
          fontWeight: 700, fontSize: '0.92rem', letterSpacing: '0.12em',
          color: 'var(--active)', minWidth: 72, textAlign: 'center',
        }}>
          {simToHHMM(simTime)}
        </div>

        {/* Speed */}
        <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
          <span style={{ color: 'var(--muted)', marginRight: 2 }}>SPEED</span>
          {SPEEDS.map(s => (
            <button key={s.value} onClick={() => changeSpeed(s.value)} style={{
              background: speed === s.value ? 'var(--active)' : 'var(--surf2)',
              color: speed === s.value ? '#000' : 'var(--text)',
              border: '1px solid var(--bdr)', cursor: 'pointer',
              padding: '3px 8px', borderRadius: 3,
              fontFamily: 'var(--font)', fontSize: '0.68rem', fontWeight: 700,
            }}>
              {s.label}
            </button>
          ))}
        </div>

        {/* Day type */}
        <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
          <span style={{ color: 'var(--muted)', marginRight: 2 }}>DAY</span>
          {['weekday', 'weekend'].map(dt => (
            <button key={dt} onClick={() => changeDayType(dt)} style={{
              background: dayType === dt ? 'var(--active)' : 'var(--surf2)',
              color: dayType === dt ? '#000' : 'var(--text)',
              border: '1px solid var(--bdr)', cursor: 'pointer',
              padding: '3px 10px', borderRadius: 3,
              fontFamily: 'var(--font)', fontSize: '0.68rem', fontWeight: 700,
              textTransform: 'uppercase',
            }}>
              {dt}
            </button>
          ))}
        </div>

        {/* Active bus count */}
        <div style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: '0.7rem' }}>
          <span style={{ color: 'var(--active)', fontWeight: 700 }}>{totalBuses}</span> buses active
        </div>
      </div>

      {/* ── Line toggles ── */}
      <div style={{
        display: 'flex', gap: '0.35rem', flexWrap: 'wrap',
        padding: '0.5rem 1rem', borderBottom: '1px solid var(--bdr)',
        background: 'var(--surf)',
      }}>
        {TOGGLE_LINES.map(l => {
          const on    = activeLines[l.ref];
          const count = busCounts[l.ref] || 0;
          return (
            <button key={l.ref} onClick={() => toggleLine(l.ref)} title={l.name}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.35rem',
                background: on ? l.colour + '22' : 'var(--surf2)',
                color:  on ? l.colour : 'var(--muted)',
                border: `1px solid ${on ? l.colour : 'var(--bdr)'}`,
                borderRadius: 4, cursor: 'pointer',
                padding: '3px 10px', minWidth: 52,
                fontFamily: 'var(--font)', fontSize: '0.68rem', fontWeight: 700,
                transition: 'all 0.15s',
              }}
            >
              <span style={{
                display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                background: on ? l.colour : 'var(--muted)', flexShrink: 0,
              }} />
              {l.ref}
              {count > 0 && (
                <span style={{
                  background: l.colour, color: '#fff',
                  borderRadius: 10, padding: '0 5px',
                  fontSize: '0.6rem', fontWeight: 700,
                  lineHeight: '14px', minWidth: 16, textAlign: 'center',
                }}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Map ── */}
      {error
        ? <div style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: '#0d0d0d', color: '#9ca3af', fontSize: 12,
            textAlign: 'center', padding: '2rem',
          }}>
            Map data requires the Vite dev server
          </div>
        : <div ref={mapRef} style={{ flex: 1, minHeight: 520, background: '#0d0d0d' }} />
      }
    </div>
  );
}
