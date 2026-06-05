import { useRef, useState, useCallback, useEffect } from 'react'
import { useMap } from './hooks/useMap'
import { BUS_FREQUENCIES } from './data/busFrequencies'
import TransitEditor from './components/TransitEditor'

// ── Bus animation helpers (ported from AccessibilityMapView) ─────────────────

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function buildCumDist(coords) {
  const cum = [0]
  for (let i = 1; i < coords.length; i++) {
    const [lat1, lon1] = coords[i - 1]
    const [lat2, lon2] = coords[i]
    cum.push(cum[i - 1] + haversineKm(lat1, lon1, lat2, lon2))
  }
  return cum
}

function interpolate(coords, cumDist, km) {
  const total   = cumDist[cumDist.length - 1]
  const clamped = Math.max(0, Math.min(km, total))
  let lo = 0, hi = cumDist.length - 2
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (cumDist[mid + 1] < clamped) lo = mid + 1
    else hi = mid
  }
  const segLen = cumDist[lo + 1] - cumDist[lo]
  const t      = segLen > 0 ? (clamped - cumDist[lo]) / segLen : 0
  const [lat1, lon1] = coords[lo]
  const [lat2, lon2] = coords[lo + 1] || coords[lo]
  return [lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t]
}

const DAY_MINS = 24 * 60
const parseMin = hhmm => {
  const [h, m] = (hhmm || '06:00').split(':').map(Number)
  return h * 60 + m
}
const toHHMM = abs => {
  const t = abs % DAY_MINS
  const h = Math.floor(t / 60)
  const m = Math.floor(t % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

function seedSpawns(refs, dt, startAbs) {
  const dayOffset = Math.floor(startAbs / DAY_MINS) * DAY_MINS
  const out = {}
  for (const ref of refs) {
    const freq = BUS_FREQUENCIES.find(l => l.ref === ref)
    if (!freq) continue
    const sched   = freq[dt] || freq.weekday
    const first   = parseMin(sched.first_bus)
    const headway = sched.headway_min || sched.peak_headway_min || 30
    out[ref] = { fwd: dayOffset + first, bwd: dayOffset + first + headway / 2 }
  }
  return out
}

// ── Route downsampling for transit editor ────────────────────────────────────

function downsample(coords, target = 25) {
  if (coords.length <= target) return coords
  const step   = (coords.length - 1) / (target - 1)
  const result = []
  for (let i = 0; i < target; i++) result.push(coords[Math.round(i * step)])
  return result
}

let stopCounter = 0
const nextStopId = () => `stop-${++stopCounter}`

const SPEEDS = [
  { label: '10×',  value: 10  },
  { label: '30×',  value: 30  },
  { label: '60×',  value: 60  },
  { label: '120×', value: 120 },
  { label: '300×', value: 300 },
]

// ── Component ────────────────────────────────────────────────────────────────

export default function App() {
  const mapContainerRef = useRef(null)

  // Transit editor state
  const [transitLines, setTransitLines] = useState([])
  const [activeLineId, setActiveLineId] = useState(null)
  const [editing,      setEditing]      = useState(false)

  // Layer visibility
  const [vis, setVis] = useState({
    streets:  true,
    schools:  true,
    busStops: true,
    busAnim:  true,
    access:   false,
    cost:     false,
  })
  const visRef = useRef(vis)
  const setVisKey = useCallback((key, val) => {
    const next = { ...visRef.current, [key]: val }
    visRef.current = next
    setVis(next)
  }, [])

  // Bus animation state
  const [simTime,  setSimTime]  = useState(6 * 60)
  const [busSpeed, setBusSpeed] = useState(60)
  const [busDay,   setBusDay]   = useState('weekday')
  const speedRef   = useRef(60)
  const dayTypeRef = useRef('weekday')

  // Animation internals
  const rafRef       = useRef(null)
  const routeDataRef = useRef({})
  const busStateRef  = useRef(null)

  const [loading, setLoading] = useState(true)

  const {
    setAccessibilityData,
    setStreetsData,
    setSchoolsData,
    setBusStopsData,
    setBusPositions,
    setLayerVisible,
    setTransitEditData,
    setTransitEditing,
    setActiveTransitLine,
    setTransitHandlers,
  } = useMap(mapContainerRef)

  // ── Load all data on mount ──────────────────────────────────────────────

  useEffect(() => {
    Promise.all([
      fetch('/model/bus_routes.geojson').then(r => r.json()),
      fetch('/model/accessibility_population.geojson').then(r => r.json()),
      fetch('/model/accessibility_streets.geojson').then(r => r.json()),
      fetch('/model/accessibility_schools.geojson').then(r => r.json()),
      fetch('/model/bus_stops.geojson').then(r => r.json()),
    ]).then(([routesGeo, accessGeo, streetsGeo, schoolsGeo, stopsGeo]) => {

      // Transit editor lines (downsampled geometry)
      const lines = routesGeo.features.map((f, idx) => {
        const { ref, name, colour } = f.properties
        const freq = BUS_FREQUENCIES.find(b => b.ref === ref)
        const sampled = downsample(f.geometry.coordinates, 25)
        return {
          id:        `route-${ref}-${idx}`,
          name:      name || ref,
          color:     colour || '#ffffff',
          medium:    'bus',
          frequency: freq?.weekday?.headway_min ?? 30,
          stops:     sampled.map((coords, i) => ({ id: `${ref}-${i}`, coords })),
        }
      })
      setTransitLines(lines)
      setActiveLineId(lines[0]?.id ?? null)

      // Full-resolution route data for animation
      const builtRoutes = {}
      routesGeo.features.forEach(f => {
        const { ref, colour } = f.properties
        const freq = BUS_FREQUENCIES.find(l => l.ref === ref)
        if (!freq || freq.days === 'discontinued') return
        // coords in GeoJSON are [lng, lat] — animation needs [lat, lng]
        const coords  = f.geometry.coordinates.map(([lng, lat]) => [lat, lng])
        const cumDist = buildCumDist(coords)
        builtRoutes[ref] = { coords, cumDist, totalKm: cumDist[cumDist.length - 1], colour: colour || '#fff' }
      })
      routeDataRef.current = builtRoutes

      const startMin = 6 * 60
      busStateRef.current = {
        simMinutes:   startMin,
        lastRafTs:    null,
        busIdCounter: 0,
        buses:        [],
        nextSpawn:    seedSpawns(Object.keys(builtRoutes), dayTypeRef.current, startMin),
      }

      // Static map layers
      setAccessibilityData(accessGeo)
      setStreetsData(streetsGeo)
      setSchoolsData(schoolsGeo)
      setBusStopsData(stopsGeo)

      setLoading(false)
    }).catch(() => setLoading(false))
  }, [setAccessibilityData, setStreetsData, setSchoolsData, setBusStopsData])

  // ── Bus animation tick ──────────────────────────────────────────────────

  const tick = useCallback((rafTs) => {
    const state  = busStateRef.current
    const routes = routeDataRef.current
    if (!state) { rafRef.current = requestAnimationFrame(tick); return }

    const elapsed   = state.lastRafTs == null ? 0 : (rafTs - state.lastRafTs) / 1000
    state.lastRafTs = rafTs
    state.simMinutes += elapsed * speedRef.current / 60
    const simNow = state.simMinutes
    const dt     = dayTypeRef.current

    // Spawn
    for (const ref of Object.keys(routes)) {
      const freq = BUS_FREQUENCIES.find(l => l.ref === ref)
      if (!freq) continue
      const sched   = freq[dt] || freq.weekday
      const headway = sched.headway_min || sched.peak_headway_min || 30
      if (!headway) continue
      const lastTod = parseMin(sched.last_bus)
      const route   = routes[ref]
      const spawnNS = state.nextSpawn[ref] || { fwd: simNow, bwd: simNow + headway / 2 }

      for (const dir of ['fwd', 'bwd']) {
        while (spawnNS[dir] <= simNow) {
          const dayOffset = Math.floor(spawnNS[dir] / DAY_MINS) * DAY_MINS
          if (spawnNS[dir] > dayOffset + lastTod + headway) {
            const nextBase = (Math.floor(spawnNS[dir] / DAY_MINS) + 1) * DAY_MINS
            spawnNS[dir]   = nextBase + parseMin(sched.first_bus) + (dir === 'bwd' ? headway / 2 : 0)
            break
          }
          state.buses.push({
            id: ++state.busIdCounter,
            ref,
            colour:     route.colour,
            coords:     route.coords,
            cumDist:    route.cumDist,
            totalKm:    route.totalKm,
            kmTraveled: dir === 'fwd' ? 0 : route.totalKm,
            direction:  dir === 'fwd' ? 1 : -1,
          })
          spawnNS[dir] += headway
        }
      }
      state.nextSpawn[ref] = spawnNS
    }

    // Move + collect positions
    const kmStep   = 0.5 * (elapsed * speedRef.current / 60)
    const features = []
    const toRemove = []

    for (const bus of state.buses) {
      bus.kmTraveled += bus.direction * kmStep
      if (bus.kmTraveled < 0 || bus.kmTraveled > bus.totalKm) {
        toRemove.push(bus)
      } else {
        const [lat, lng] = interpolate(bus.coords, bus.cumDist, bus.kmTraveled)
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lng, lat] },
          properties: { ref: bus.ref, color: bus.colour },
        })
      }
    }
    for (const bus of toRemove) {
      const idx = state.buses.indexOf(bus)
      if (idx !== -1) state.buses.splice(idx, 1)
    }

    setBusPositions({ type: 'FeatureCollection', features })
    if (Math.round(simNow * 10) % 2 === 0) setSimTime(Math.floor(simNow % DAY_MINS))

    if (visRef.current.busAnim) rafRef.current = requestAnimationFrame(tick)
  }, [setBusPositions])

  // Start/stop animation when busAnim visibility changes or routes load
  useEffect(() => {
    if (loading) return
    if (vis.busAnim) {
      if (busStateRef.current) busStateRef.current.lastRafTs = null
      rafRef.current = requestAnimationFrame(tick)
    } else {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
      // Clear bus markers
      setBusPositions({ type: 'FeatureCollection', features: [] })
    }
    return () => {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
    }
  }, [vis.busAnim, loading, tick, setBusPositions])

  // ── Sync layer visibility to map ────────────────────────────────────────

  useEffect(() => { setLayerVisible('streets-layer',   vis.streets)  }, [vis.streets,  setLayerVisible])
  useEffect(() => { setLayerVisible('schools-layer',   vis.schools)  }, [vis.schools,  setLayerVisible])
  useEffect(() => { setLayerVisible('bus-stops-layer', vis.busStops) }, [vis.busStops, setLayerVisible])
  useEffect(() => { setLayerVisible('bus-live-bg',     vis.busAnim)  }, [vis.busAnim,  setLayerVisible])
  useEffect(() => { setLayerVisible('bus-live-labels', vis.busAnim)  }, [vis.busAnim,  setLayerVisible])
  useEffect(() => { setLayerVisible('access-layer',    vis.access)   }, [vis.access,   setLayerVisible])
  useEffect(() => { setLayerVisible('cost-layer',      vis.cost)     }, [vis.cost,     setLayerVisible])

  // ── Sync transit editor state to map ────────────────────────────────────

  useEffect(() => { setTransitEditData(transitLines)    }, [transitLines,  setTransitEditData])
  useEffect(() => { setActiveTransitLine(activeLineId)  }, [activeLineId,  setActiveTransitLine])
  useEffect(() => { setTransitEditing(editing)          }, [editing,       setTransitEditing])

  useEffect(() => {
    setTransitHandlers({
      onAddStop: (lineId, coords) => {
        setTransitLines(prev => prev.map(l =>
          l.id === lineId ? { ...l, stops: [...l.stops, { id: nextStopId(), coords }] } : l
        ))
      },
      onMoveStop: (lineId, stopId, coords) => {
        setTransitLines(prev => prev.map(l =>
          l.id === lineId
            ? { ...l, stops: l.stops.map(s => s.id === stopId ? { ...s, coords } : s) }
            : l
        ))
      },
    })
  }, [setTransitHandlers])

  // ── Transit editor handlers ─────────────────────────────────────────────

  const handleToggleEdit = useCallback(() => {
    setEditing(prev => {
      const next = !prev
      if (next && !activeLineId && transitLines.length > 0) setActiveLineId(transitLines[0].id)
      return next
    })
  }, [transitLines, activeLineId])

  const handleRunEdit = useCallback(() => {
    const stops = transitLines.flatMap(l =>
      l.stops.map(s => ({
        line_name: l.name, line_color: l.color,
        lat: s.coords[1], long: s.coords[0],
        mode: l.medium,   intervall: l.frequency,
      }))
    )
    const lines = transitLines.map(l => ({
      name: l.name, color: l.color, medium: l.medium,
      frequency: l.frequency, stop_count: l.stops.length,
    }))
    console.log('[Transit Builder] stops =', stops)
    window.parent.postMessage({ type: 'TRANSIT_EDIT', stops, lines }, '*')
    setEditing(false)
  }, [transitLines])

  // ── Animation controls ──────────────────────────────────────────────────

  const changeSpeed = useCallback((v) => {
    speedRef.current = v
    setBusSpeed(v)
  }, [])

  const changeDay = useCallback((dt) => {
    dayTypeRef.current = dt
    setBusDay(dt)
    const state = busStateRef.current
    if (!state) return
    for (const bus of state.buses) ; // buses will naturally expire
    state.buses     = []
    state.nextSpawn = seedSpawns(Object.keys(routeDataRef.current), dt, state.simMinutes)
    setBusPositions({ type: 'FeatureCollection', features: [] })
  }, [setBusPositions])

  const resetBus = useCallback(() => {
    const state = busStateRef.current
    if (!state) return
    state.buses      = []
    state.simMinutes = 6 * 60
    state.lastRafTs  = null
    state.nextSpawn  = seedSpawns(Object.keys(routeDataRef.current), dayTypeRef.current, 6 * 60)
    setBusPositions({ type: 'FeatureCollection', features: [] })
    setSimTime(6 * 60)
  }, [setBusPositions])

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="app">
      <div ref={mapContainerRef} className="map-container" />

      <div className="map-label">
        <span className="map-label-name">Andorra</span>
        <span className="map-label-sub">Accessibility · Transit Builder</span>
      </div>

      {/* ── Layer toggles ── */}
      <div className="layer-bar">
        {[
          { key: 'streets',  label: 'Streets'   },
          { key: 'schools',  label: 'Schools'   },
          { key: 'busStops', label: 'Stops'     },
          { key: 'busAnim',  label: 'Live Buses'},
          { key: 'access',   label: 'Access'    },
          { key: 'cost',     label: 'Cost'      },
        ].map(({ key, label }) => (
          <button
            key={key}
            className={`layer-btn${vis[key] ? ' active' : ''} btn-${key}`}
            onClick={() => setVisKey(key, !vis[key])}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Bus animation controls ── */}
      {vis.busAnim && (
        <div className="anim-bar">
          <div className="anim-clock">{toHHMM(simTime)}</div>

          <span className="anim-label">SPEED</span>
          {SPEEDS.map(s => (
            <button
              key={s.value}
              className={`anim-btn${busSpeed === s.value ? ' active' : ''}`}
              onClick={() => changeSpeed(s.value)}
            >
              {s.label}
            </button>
          ))}

          <span className="anim-label">DAY</span>
          {['weekday', 'weekend'].map(dt => (
            <button
              key={dt}
              className={`anim-btn${busDay === dt ? ' active' : ''}`}
              onClick={() => changeDay(dt)}
            >
              {dt === 'weekday' ? 'Weekday' : 'Weekend'}
            </button>
          ))}

          <button className="anim-btn" onClick={resetBus}>↺ Reset</button>
        </div>
      )}

      {/* ── Legend ── */}
      {(vis.access || vis.cost) && (
        <div className="legend-box">
          {vis.access && (
            <div className="legend-section">
              <div className="legend-title">Accessibility</div>
              <div className="legend-row"><span className="legend-dot" style={{ background: '#4ade80' }} />Walk</div>
              <div className="legend-row"><span className="legend-dot" style={{ background: '#fbbf24' }} />Bike</div>
              <div className="legend-row"><span className="legend-dot" style={{ background: '#f87171' }} />Bus / Car</div>
            </div>
          )}
          {vis.cost && (
            <div className="legend-section">
              <div className="legend-title">Transport Cost</div>
              <div className="legend-gradient" />
              <div className="legend-gradient-labels"><span>Low</span><span>High</span></div>
              <div className="legend-note">population × mode factor</div>
            </div>
          )}
        </div>
      )}

      {loading && <div className="loading-pill">Loading…</div>}

      <TransitEditor
        visible={true}
        editing={editing}
        onToggleEdit={handleToggleEdit}
        lines={transitLines}
        setLines={setTransitLines}
        activeLineId={activeLineId}
        setActiveLineId={setActiveLineId}
        onRunEdit={handleRunEdit}
      />
    </div>
  )
}
