import { useState, useRef, useCallback, useEffect } from 'react';
import PopulationMapView from './PopulationMapView';
import BaseMapView from './BaseMapView';
import GrowthMapView from './GrowthMapView';
import TourismMapView from './TourismMapView';
import { DEFAULT_MAP_STYLE, rasterTilesUrl } from '../utils/mapboxBase';

const LAYERS = [
  { id: 'base',          label: 'Base' },
  { id: 'agents',        label: 'Agents' },
  { id: 'growth',        label: 'Growth' },
  { id: 'tourism',       label: 'Tourism' },
  { id: 'accessibility', label: 'Accessibility' },
  { id: 'population',    label: 'Population' },
];

const IFRAME_LAYERS = {
  agents:        '/andorra/map?embed',
  accessibility: '/transit-builder/',
};

// Layers backed by the shared Mapbox stack (respond to the style selector).
const MAPBOX_IDS = ['base', 'growth', 'tourism', 'population'];

const MAP_STYLE_OPTIONS = [
  { id: 'satellite', label: 'Satellite' },
  { id: 'dark',      label: 'Dark' },
  { id: 'light',     label: 'Light' },
];

export default function MapVisualization({
  overlayEnabled  = {},
  selectedYear    = 2049,
  activeLayer: activeLayerProp,
  onLayerChange,
  hoveredAgent    = -1,
  selectedAgent   = -1,
}) {
  // visualLayer updates immediately on click so the "already on this layer?" guard is always current.
  // The prop (activeLayerProp) may lag by 400ms due to the Arduino debounce in App.jsx.
  const [visualLayer, setVisualLayer] = useState('base');
  const [mapStyle, setMapStyle]       = useState(DEFAULT_MAP_STYLE);
  const setActiveLayer = onLayerChange ?? setVisualLayer;

  // Sync when Arduino forces a layer change from outside
  useEffect(() => {
    if (activeLayerProp && activeLayerProp !== visualLayer) {
      setVisualLayer(activeLayerProp);
      setEverSeen(prev => ({ ...prev, [activeLayerProp]: true }));
    }
  }, [activeLayerProp]); // eslint-disable-line react-hooks/exhaustive-deps

  const [everSeen, setEverSeen] = useState(
    Object.keys(IFRAME_LAYERS).reduce((acc, id) => ({ ...acc, [id]: true }), { base: true })
  );

  const agentsIframeRef = useRef(null);

  // Single source of truth for the map base: mapboxBase.js owns the provider +
  // token; we push the derived raster-tile URL to the deck.gl agent map (a
  // separate app in the iframe) so changing the style/provider here updates it
  // too. The iframe pulls (MAP_BASE_REQUEST on mount); we also push on style change.
  const postBaseConfig = useCallback(() => {
    const satelliteUrl = rasterTilesUrl(mapStyle);
    if (!satelliteUrl) return; // no token → iframe keeps its ArcGIS fallback
    agentsIframeRef.current?.contentWindow?.postMessage(
      { type: 'MAP_BASE_CONFIG', data: { satelliteUrl, styleKey: mapStyle } }, '*',
    );
  }, [mapStyle]);

  useEffect(() => { postBaseConfig(); }, [postBaseConfig]);

  useEffect(() => {
    const onMsg = (e) => { if (e.data?.type === 'MAP_BASE_REQUEST') postBaseConfig(); };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [postBaseConfig]);

  useEffect(() => {
    if (selectedAgent < 0) return;
    agentsIframeRef.current?.contentWindow?.postMessage({ type: 'AGENT_SELECT', pos: selectedAgent }, '*');
  }, [selectedAgent]);

  useEffect(() => {
    if (hoveredAgent < 0) return;
    agentsIframeRef.current?.contentWindow?.postMessage({ type: 'AGENT_HOVER', pos: hoveredAgent }, '*');
  }, [hoveredAgent]);

  useEffect(() => {
    if (visualLayer && !everSeen[visualLayer]) {
      setEverSeen(prev => ({ ...prev, [visualLayer]: true }));
    }
  }, [visualLayer]); // eslint-disable-line react-hooks/exhaustive-deps

  const switchLayer = useCallback((id) => {
    if (id === visualLayer) return;
    setVisualLayer(id);
    setActiveLayer(id);
    setEverSeen(prev => ({ ...prev, [id]: true }));
  }, [visualLayer, setActiveLayer]);

  // The agent map now shares the same Mapbox base, so it responds to the selector too.
  const styleSelectorVisible = MAPBOX_IDS.includes(visualLayer) || visualLayer === 'agents';

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>

      {/* Map style selector (Dark / Satellite / Light) — only for Mapbox-backed layers */}
      {styleSelectorVisible && (
        <div className="map-style-pill" style={{
          position: 'absolute', top: 18, right: 18, zIndex: 25,
          display: 'flex', gap: 4, alignItems: 'center', pointerEvents: 'all',
        }}>
          {MAP_STYLE_OPTIONS.map(({ id, label }) => (
            <button key={id} type="button"
              className={`map-style-btn ${mapStyle === id ? 'active' : ''}`}
              onClick={() => setMapStyle(id)}>
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Layer switcher */}
      <div className="map-layer-pill" style={{
        position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 6, flexWrap: 'wrap', zIndex: 20, pointerEvents: 'all',
      }}>
        {LAYERS.map(({ id, label }) => (
          <button key={id} type="button"
            className={`tab-button ${visualLayer === id ? 'active' : ''}`}
            style={{ fontSize: '10px', padding: '7px 14px' }}
            onClick={() => switchLayer(id)}>
            {label}
          </button>
        ))}
      </div>

      <div style={{ position: 'relative', height: '100%' }}>

        {/* Mapbox maps — mounted on first visit, kept alive (never remounted) */}
        {MAPBOX_IDS.map(id => (
          <div key={id} style={{
            position:      'absolute',
            inset:         0,
            opacity:       visualLayer === id ? 1 : 0,
            pointerEvents: visualLayer === id ? 'auto' : 'none',
            transition:    'opacity 380ms ease',
            zIndex:        visualLayer === id ? 1 : 0,
          }}>
            {everSeen[id] && (
              id === 'base'    ? <BaseMapView mapStyle={mapStyle} /> :
              id === 'growth'  ? <GrowthMapView overlayEnabled={overlayEnabled} selectedYear={selectedYear} visible={visualLayer === 'growth'} mapStyle={mapStyle} /> :
              id === 'tourism' ? <TourismMapView mapStyle={mapStyle} /> :
                                 <PopulationMapView mapStyle={mapStyle} />
            )}
          </div>
        ))}

        {/* Iframe layers */}
        {Object.entries(IFRAME_LAYERS).map(([id, src]) => (
          <div key={id} style={{
            position:      'absolute',
            inset:         0,
            opacity:       visualLayer === id ? 1 : 0,
            pointerEvents: visualLayer === id ? 'auto' : 'none',
            transition:    'opacity 380ms ease',
            zIndex:        visualLayer === id ? 1 : 0,
          }}>
            {everSeen[id] && (
              <iframe
                ref={id === 'agents' ? agentsIframeRef : undefined}
                src={src}
                title={id}
                onLoad={id === 'agents' ? postBaseConfig : undefined}
                style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
                allow="clipboard-write"
              />
            )}
          </div>
        ))}

      </div>
    </div>
  );
}
