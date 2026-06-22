import mapboxgl from 'mapbox-gl';

// Shared Mapbox foundation for all locked Andorra maps (Base, Growth, Tourism, Population).
// Replaces the previous Leaflet stack. Every map is non-interactive (no pan/zoom — the
// keystone projection is fixed), fitted to the four projection corners, with a black
// keystone mask, dashed national boundary, and the four red corner markers.

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

export { mapboxgl };

// Selectable base styles for the in-map style switcher.
export const MAP_STYLES = {
  dark:      'mapbox://styles/mapbox/dark-v11',
  satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
  light:     'mapbox://styles/mapbox/light-v11',
};
export const DEFAULT_MAP_STYLE = 'satellite';

// deck.gl-compatible Mapbox raster tiles for a given style. The agent map is a
// separate deck.gl app (the /andorra iframe) that can't import this module's
// Mapbox GL instance, so it consumes the base as raster tiles instead — this is
// how that map shares THIS module as the single source of truth for provider +
// token. Returns null if no token is configured, so callers can fall back.
// {z}/{x}/{y} are filled in by deck.gl's TileLayer.
// Raster style overrides for the agent map. deck.gl consumes the base as raster
// tiles, so it can't hide road layers the way the vector maps do (hideRoads).
// satellite-streets bakes in yellow motorways, so the raster satellite uses the
// roadless imagery style instead; the agent map adds its own clean label overlay.
const RASTER_STYLES = {
  ...MAP_STYLES,
  satellite: 'mapbox://styles/mapbox/satellite-v9',
};

export function rasterTilesUrl(styleKey = DEFAULT_MAP_STYLE) {
  if (!mapboxgl.accessToken) return null;
  const path = (RASTER_STYLES[styleKey] || RASTER_STYLES[DEFAULT_MAP_STYLE])
    .replace('mapbox://styles/', ''); // e.g. 'mapbox/satellite-v9'
  return `https://api.mapbox.com/styles/v1/${path}/tiles/256/{z}/{x}/{y}@2x?access_token=${mapboxgl.accessToken}`;
}

// [west, south] , [east, north]  (lng,lat) — matches the Leaflet PROJECTION_BOUNDS.
export const PROJECTION_BOUNDS = [
  [1.393847, 42.394176],
  [1.803713, 42.697242],
];

// Keystone projection corners, ordered NW → NE → SE → SW (lng,lat).
export const PROJECTION_CORNERS = [
  [1.393847, 42.694543], // NW
  [1.801074, 42.697242], // NE
  [1.803713, 42.396861], // SE
  [1.39849,  42.394176], // SW
];

const FRAME = {
  boundary: 'andorra-boundary',
  mask:     'keystone-mask',
  corners:  'keystone-corners',
};

// ── Map creation ──────────────────────────────────────────────────────────────

export function createLockedMap(container, styleKey = DEFAULT_MAP_STYLE) {
  const map = new mapboxgl.Map({
    container,
    style: MAP_STYLES[styleKey] || MAP_STYLES[DEFAULT_MAP_STYLE],
    bounds: PROJECTION_BOUNDS,
    fitBoundsOptions: { padding: 0, animate: false },
    attributionControl: false,
    logoPosition: 'bottom-left',
    fadeDuration: 0,
    // Lock the view — the keystone projection must stay put. Click/hover events still
    // fire (so popups work); only the navigation handlers are disabled.
    dragPan: false,
    scrollZoom: false,
    boxZoom: false,
    dragRotate: false,
    keyboard: false,
    doubleClickZoom: false,
    touchZoomRotate: false,
    touchPitch: false,
  });
  map.on('load', () => fitProjection(map));
  return map;
}

export function fitProjection(map) {
  try { map.fitBounds(PROJECTION_BOUNDS, { padding: 0, animate: false }); } catch (_) {}
}

// ── National boundary (loaded once, cached across maps + style reloads) ─────────

let _boundaryPromise = null;
export function loadBoundary() {
  if (!_boundaryPromise) {
    _boundaryPromise = fetch('/andorra_boundary.geojson')
      .then(r => r.json())
      .catch(() => null);
  }
  return _boundaryPromise;
}

// ── Frame: boundary + black keystone mask + corner markers ──────────────────────
// Idempotent. Always re-run after a style switch (Mapbox drops custom layers on setStyle).

export function addFrame(map, boundaryData) {
  // 1. National boundary (sits beneath the mask so anything outside the keystone is clipped).
  if (boundaryData && !map.getSource(FRAME.boundary)) {
    map.addSource(FRAME.boundary, { type: 'geojson', data: boundaryData });
    map.addLayer({
      id: FRAME.boundary,
      type: 'line',
      source: FRAME.boundary,
      paint: {
        'line-color': '#3fe0e6',
        'line-width': 1.6,
        'line-opacity': 0.6,
        'line-dasharray': [2, 3],
      },
    });
  }

  // 2. Black keystone mask: a huge polygon with the keystone quadrilateral punched out.
  if (!map.getSource(FRAME.mask)) {
    const outer = [
      [-20, 30], [25, 30], [25, 55], [-20, 55], [-20, 30],
    ];
    const hole = [...PROJECTION_CORNERS, PROJECTION_CORNERS[0]];
    map.addSource(FRAME.mask, {
      type: 'geojson',
      data: { type: 'Feature', geometry: { type: 'Polygon', coordinates: [outer, hole] } },
    });
    map.addLayer({
      id: FRAME.mask,
      type: 'fill',
      source: FRAME.mask,
      paint: { 'fill-color': '#000000', 'fill-opacity': 1 },
    });
  }

  // 3. Corner markers — always on top.
  if (!map.getSource(FRAME.corners)) {
    map.addSource(FRAME.corners, {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: PROJECTION_CORNERS.map(c => ({
          type: 'Feature', geometry: { type: 'Point', coordinates: c }, properties: {},
        })),
      },
    });
    map.addLayer({
      id: FRAME.corners,
      type: 'circle',
      source: FRAME.corners,
      paint: {
        'circle-radius': 5,
        'circle-color': '#d9b15a',
        'circle-stroke-color': '#3fe0e6',
        'circle-stroke-width': 1.6,
      },
    });
  } else {
    // Keep corners above any newly added data layers.
    try { map.moveLayer(FRAME.corners); } catch (_) {}
  }
}

// The beforeId data layers should be inserted before, so they stay beneath the frame.
export function frameBeforeId(map) {
  if (map.getLayer(FRAME.boundary)) return FRAME.boundary;
  if (map.getLayer(FRAME.mask)) return FRAME.mask;
  return undefined;
}

// Add a data layer beneath the frame (so the mask clips it and corners stay on top).
export function addDataLayer(map, layerDef) {
  if (map.getLayer(layerDef.id)) return;
  const before = frameBeforeId(map);
  if (before) map.addLayer(layerDef, before);
  else map.addLayer(layerDef);
}

// ── Hover popup helper (replaces Leaflet bindTooltip / bindPopup) ────────────────

export function attachHoverPopup(map, layerId, htmlFn, { sticky = true } = {}) {
  // Listeners live on the Map instance and survive setStyle, while data layers are
  // re-added on every style switch — so guard against attaching duplicates.
  map.__hoverPopups = map.__hoverPopups || new Set();
  if (map.__hoverPopups.has(layerId)) return;
  map.__hoverPopups.add(layerId);

  const popup = new mapboxgl.Popup({
    closeButton: false,
    closeOnClick: false,
    className: 'mb-hover-popup',
    offset: 8,
    maxWidth: '280px',
  });

  map.on('mousemove', layerId, (e) => {
    const f = e.features && e.features[0];
    if (!f) return;
    map.getCanvas().style.cursor = 'pointer';
    const html = htmlFn(f);
    if (html == null) { popup.remove(); return; }
    popup.setLngLat(sticky ? e.lngLat : f.geometry?.coordinates ?? e.lngLat).setHTML(html).addTo(map);
  });

  map.on('mouseleave', layerId, () => {
    map.getCanvas().style.cursor = '';
    popup.remove();
  });

  return popup;
}

// Hide the road network from a style while keeping place/settlement labels.
// Used on the satellite-streets style so its yellow highways don't clutter the imagery.
export function hideRoads(map) {
  const layers = map.getStyle()?.layers || [];
  for (const l of layers) {
    if (l['source-layer'] === 'road') {
      try { map.setLayoutProperty(l.id, 'visibility', 'none'); } catch (_) {}
    }
  }
}

// Register a callback that runs on every style load (initial + after each setStyle).
export function onEveryStyleLoad(map, fn) {
  map.on('style.load', fn);
  if (map.isStyleLoaded()) fn();
}

// Run fn as soon as the style is fully loaded (now, or on the next styledata that
// reports a loaded style). Robust against the isStyleLoaded() race when async data
// resolves before/after the initial style load.
export function whenStyleReady(map, fn) {
  if (!map) return;
  if (map.isStyleLoaded()) { fn(); return; }
  const h = () => { if (map.isStyleLoaded()) { map.off('styledata', h); fn(); } };
  map.on('styledata', h);
}
