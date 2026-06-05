import { useEffect, useRef, useCallback } from 'react'
import mapboxgl from 'mapbox-gl'

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN

const ANDORRA_CENTER = [1.598, 42.547]
const ANDORRA_ZOOM   = 11
const MAPBOX_STYLE   = 'mapbox://styles/mapbox/dark-v11'

// ── Layer paint definitions ───────────────────────────────────────────────────

const STREETS_PAINT = {
  'line-color': [
    'match', ['coalesce', ['get', 'accessibility'], ''],
    'walk',    '#4ade80',
    'bike',    '#fbbf24',
    'bus/car', '#f87171',
    '#374151',
  ],
  'line-width': 1.2,
  'line-opacity': 0.65,
}

const SCHOOLS_PAINT = {
  'circle-radius': 6,
  'circle-color': '#60a5fa',
  'circle-stroke-color': '#1d4ed8',
  'circle-stroke-width': 1.5,
  'circle-opacity': 0.9,
}

const BUS_STOPS_PAINT = {
  'circle-radius': 4,
  'circle-color': '#facc15',
  'circle-stroke-color': '#1e293b',
  'circle-stroke-width': 1.5,
  'circle-opacity': 0.95,
}

const ACCESS_FILL_PAINT = {
  'fill-color': [
    'match', ['coalesce', ['get', 'accessibility'], ''],
    'walk',    '#4ade80',
    'bike',    '#fbbf24',
    'bus/car', '#f87171',
    'rgba(0,0,0,0)',
  ],
  'fill-opacity': [
    'interpolate', ['linear'], ['coalesce', ['get', 'population'], 0],
    0, 0.0, 5, 0.22, 100, 0.45, 400, 0.58,
  ],
}

const COST_FILL_PAINT = {
  'fill-color': [
    'interpolate', ['linear'],
    ['*',
      ['coalesce', ['get', 'population'], 0],
      ['match', ['coalesce', ['get', 'accessibility'], ''],
        'bus/car', 3, 'bike', 1.5, 'walk', 0.2, 0.3,
      ],
    ],
    0,   'rgba(0,0,0,0)',
    2,   '#fef9c3',
    15,  '#fde047',
    50,  '#f97316',
    200, '#dc2626',
    600, '#7f1d1d',
  ],
  'fill-opacity': 0.65,
}

const TRANSIT_LINE_PAINT = {
  'line-width':   ['interpolate', ['linear'], ['zoom'], 10, 2, 14, 4.5, 18, 9],
  'line-color':   ['get', 'color'],
  'line-opacity': 0.95,
}

const TRANSIT_STOP_CIRCLE_PAINT = {
  'circle-radius':       ['interpolate', ['linear'], ['zoom'], 10, 4, 14, 6.5, 18, 10],
  'circle-color':        '#ffffff',
  'circle-stroke-width': 2.5,
  'circle-stroke-color': ['get', 'color'],
  'circle-pitch-alignment': 'map',
}

const TRANSIT_STOP_HALO_PAINT = {
  'circle-radius':  ['interpolate', ['linear'], ['zoom'], 10, 8, 14, 12, 18, 18],
  'circle-color':   ['get', 'color'],
  'circle-opacity': 0.18,
  'circle-pitch-alignment': 'map',
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useMap(containerRef) {
  const mapRef         = useRef(null)
  const layerReadyRef  = useRef(false)
  const pendingRef     = useRef({})          // data that arrived before map was ready

  // Transit editor refs
  const editingRef      = useRef(false)
  const activeLineIdRef = useRef(null)
  const onAddStopRef    = useRef(null)
  const onMoveStopRef   = useRef(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: MAPBOX_STYLE,
      center: ANDORRA_CENTER,
      zoom: ANDORRA_ZOOM,
      pitch: 0,
      bearing: 0,
      antialias: true,
    })

    map.addControl(new mapboxgl.NavigationControl({ visualizePitch: false }), 'bottom-right')

    map.on('load', () => {

      // ── Accessibility hex layers ──────────────────────────────────────────
      map.addSource('access-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({ id: 'access-layer', type: 'fill', source: 'access-source',
        layout: { visibility: 'none' }, paint: ACCESS_FILL_PAINT })
      map.addLayer({ id: 'cost-layer',   type: 'fill', source: 'access-source',
        layout: { visibility: 'none' }, paint: COST_FILL_PAINT })

      // ── Streets accessibility ─────────────────────────────────────────────
      map.addSource('streets-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({ id: 'streets-layer', type: 'line', source: 'streets-source',
        layout: { visibility: 'visible', 'line-join': 'round', 'line-cap': 'round' },
        paint: STREETS_PAINT,
      })

      // ── Schools ───────────────────────────────────────────────────────────
      map.addSource('schools-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({ id: 'schools-layer', type: 'circle', source: 'schools-source',
        layout: { visibility: 'visible' }, paint: SCHOOLS_PAINT })

      // ── Bus stops (static) ────────────────────────────────────────────────
      map.addSource('bus-stops-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({ id: 'bus-stops-layer', type: 'circle', source: 'bus-stops-source',
        layout: { visibility: 'visible' }, paint: BUS_STOPS_PAINT })

      // ── Live bus animation ────────────────────────────────────────────────
      map.addSource('bus-live-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      // Circle background (route colour)
      map.addLayer({
        id: 'bus-live-bg', type: 'circle', source: 'bus-live-source',
        layout: { visibility: 'visible' },
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 5, 13, 8, 16, 12],
          'circle-color':  ['get', 'color'],
          'circle-opacity': 0.92,
          'circle-pitch-alignment': 'map',
        },
      })
      // Text label (route ref)
      map.addLayer({
        id: 'bus-live-labels', type: 'symbol', source: 'bus-live-source',
        layout: {
          visibility: 'visible',
          'text-field': ['slice', ['get', 'ref'], 0, 4],
          'text-size': ['interpolate', ['linear'], ['zoom'], 9, 7, 13, 9, 16, 11],
          'text-font': ['DIN Offc Pro Bold', 'Arial Unicode MS Bold'],
          'text-allow-overlap': true,
          'text-ignore-placement': true,
          'text-anchor': 'center',
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': 'rgba(0,0,0,0.3)',
          'text-halo-width': 0.5,
        },
      })

      // ── Transit editor layers (on top of everything) ──────────────────────
      map.addSource('transit-edit-lines',  { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addSource('transit-edit-stops',  { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })

      map.addLayer({ id: 'transit-edit-lines-layer', type: 'line', source: 'transit-edit-lines',
        layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: TRANSIT_LINE_PAINT })
      map.addLayer({ id: 'transit-edit-stops-halo',  type: 'circle', source: 'transit-edit-stops',
        paint: TRANSIT_STOP_HALO_PAINT })
      map.addLayer({ id: 'transit-edit-stops-layer', type: 'circle', source: 'transit-edit-stops',
        paint: TRANSIT_STOP_CIRCLE_PAINT })

      // ── Map interaction: click to add stop ────────────────────────────────
      map.on('click', (e) => {
        if (!editingRef.current || !activeLineIdRef.current) return
        const hits = map.queryRenderedFeatures(e.point, { layers: ['transit-edit-stops-layer'] })
        if (hits.length > 0) return
        onAddStopRef.current?.(activeLineIdRef.current, [e.lngLat.lng, e.lngLat.lat])
      })

      map.on('mouseenter', 'transit-edit-stops-layer', () => {
        if (editingRef.current) map.getCanvas().style.cursor = 'grab'
      })
      map.on('mouseleave', 'transit-edit-stops-layer', () => {
        if (editingRef.current) map.getCanvas().style.cursor = 'crosshair'
      })

      // Drag stops
      let draggingStop = null
      const onMove = (ev) => {
        if (!draggingStop) return
        onMoveStopRef.current?.(draggingStop.lineId, draggingStop.stopId, [ev.lngLat.lng, ev.lngLat.lat])
        map.getCanvas().style.cursor = 'grabbing'
      }
      const onUp = () => {
        if (!draggingStop) return
        draggingStop = null
        map.getCanvas().style.cursor = editingRef.current ? 'crosshair' : ''
        map.off('mousemove', onMove)
        map.dragPan.enable()
      }
      map.on('mousedown', 'transit-edit-stops-layer', (ev) => {
        if (!editingRef.current) return
        const f = ev.features?.[0]
        if (!f) return
        ev.preventDefault()
        draggingStop = { lineId: f.properties.lineId, stopId: f.properties.stopId }
        map.dragPan.disable()
        map.getCanvas().style.cursor = 'grabbing'
        map.on('mousemove', onMove)
        map.once('mouseup', onUp)
      })

      // ── Flush any data that arrived before map was ready ──────────────────
      layerReadyRef.current = true
      const p = pendingRef.current
      if (p.access)    map.getSource('access-source')?.setData(p.access)
      if (p.streets)   map.getSource('streets-source')?.setData(p.streets)
      if (p.schools)   map.getSource('schools-source')?.setData(p.schools)
      if (p.busStops)  map.getSource('bus-stops-source')?.setData(p.busStops)
      pendingRef.current = {}
    })

    mapRef.current = map
    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        layerReadyRef.current = false
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Generic setter helpers ────────────────────────────────────────────────

  const setSource = useCallback((sourceId, pendingKey, geojson) => {
    if (!mapRef.current || !layerReadyRef.current) {
      pendingRef.current[pendingKey] = geojson
      return
    }
    mapRef.current.getSource(sourceId)?.setData(geojson)
  }, [])

  const setLayerVisible = useCallback((layerId, visible) => {
    const map = mapRef.current
    if (!map || !layerReadyRef.current) return
    map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none')
  }, [])

  // ── Public setters ────────────────────────────────────────────────────────

  const setAccessibilityData = useCallback((g) => setSource('access-source',     'access',   g), [setSource])
  const setStreetsData        = useCallback((g) => setSource('streets-source',    'streets',  g), [setSource])
  const setSchoolsData        = useCallback((g) => setSource('schools-source',    'schools',  g), [setSource])
  const setBusStopsData       = useCallback((g) => setSource('bus-stops-source',  'busStops', g), [setSource])

  const setBusPositions = useCallback((geojson) => {
    mapRef.current?.getSource('bus-live-source')?.setData(geojson)
  }, [])

  const setTransitEditData = useCallback((lines) => {
    const map = mapRef.current
    if (!map || !layerReadyRef.current) return

    const lineFeatures = lines.filter(l => l.stops.length >= 2).map(l => ({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: l.stops.map(s => s.coords) },
      properties: { lineId: l.id, color: l.color, name: l.name },
    }))
    const stopFeatures = lines.flatMap(l =>
      l.stops.map(s => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: s.coords },
        properties: { lineId: l.id, stopId: s.id, color: l.color },
      }))
    )
    map.getSource('transit-edit-lines')?.setData({ type: 'FeatureCollection', features: lineFeatures })
    map.getSource('transit-edit-stops')?.setData({ type: 'FeatureCollection', features: stopFeatures })
  }, [])

  const setTransitEditing = useCallback((editing) => {
    editingRef.current = editing
    const map = mapRef.current
    if (map) map.getCanvas().style.cursor = editing ? 'crosshair' : ''
  }, [])

  const setActiveTransitLine = useCallback((id) => { activeLineIdRef.current = id }, [])

  const setTransitHandlers = useCallback(({ onAddStop, onMoveStop }) => {
    onAddStopRef.current  = onAddStop
    onMoveStopRef.current = onMoveStop
  }, [])

  return {
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
  }
}
