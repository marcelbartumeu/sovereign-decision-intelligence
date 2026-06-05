import { useState, useRef, useCallback, useEffect } from 'react';
import PopulationMapView from './PopulationMapView';
import BaseMapView from './BaseMapView';
import GrowthMapView from './GrowthMapView';
import TourismMapView from './TourismMapView';

const LAYERS = [
  { id: 'base',          label: 'Base' },
  { id: 'agents',        label: 'AGENTS' },
  { id: 'growth',        label: 'Growth' },
  { id: 'tourism',       label: 'Tourism' },
  { id: 'accessibility', label: 'Accessibility' },
  { id: 'population',    label: 'Population' },
];

const IFRAME_LAYERS = {
  agents:        '/andorra/map?embed',
  accessibility: '/transit-builder/',
};

const LEAFLET_IDS = ['base', 'growth', 'tourism', 'population'];

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
  const setActiveLayer = onLayerChange ?? setVisualLayer;

  // Sync when Arduino forces a layer change from outside
  useEffect(() => {
    if (activeLayerProp && activeLayerProp !== visualLayer) {
      setVisualLayer(activeLayerProp);
      // Also mark as seen so the component mounts in the same render batch
      setEverSeen(prev => ({ ...prev, [activeLayerProp]: true }));
    }
  }, [activeLayerProp]); // eslint-disable-line react-hooks/exhaustive-deps

  // Always dispatch a resize event when the active layer changes so Leaflet
  // invalidates its size regardless of whether the switch came from a UI button
  // click or an Arduino-triggered prop update.
  useEffect(() => {
    const t = setTimeout(() => window.dispatchEvent(new Event('resize')), 80);
    return () => clearTimeout(t);
  }, [visualLayer]);

  const [everSeen, setEverSeen] = useState(
    Object.keys(IFRAME_LAYERS).reduce((acc, id) => ({ ...acc, [id]: true }), { base: true })
  );

  const agentsIframeRef = useRef(null);

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

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>

      {/* Layer switcher */}
      <div style={{
        position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 6, flexWrap: 'wrap', zIndex: 20, pointerEvents: 'all',
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(6px)',
        padding: '6px 10px', borderRadius: 10,
        border: '1px solid rgba(255,255,255,0.10)',
      }}>
        {LAYERS.map(({ id, label }) => (
          <button key={id} type="button"
            className={`tab-button ${visualLayer === id ? 'active' : ''}`}
            style={{ fontSize:'10px', padding:'7px 14px' }}
            onClick={() => switchLayer(id)}>
            {label}
          </button>
        ))}
      </div>

      <div style={{ position: 'relative', height: '100%' }}>

        {/* Leaflet maps — mounted on first visit, kept alive (never remounted) */}
        {LEAFLET_IDS.map(id => (
          <div key={id} style={{
            position:      'absolute',
            inset:         0,
            opacity:       visualLayer === id ? 1 : 0,
            pointerEvents: visualLayer === id ? 'auto' : 'none',
            transition:    'opacity 380ms ease',
            zIndex:        visualLayer === id ? 1 : 0,
          }}>
            {everSeen[id] && (
              id === 'base'          ? <BaseMapView /> :
              id === 'growth'        ? <GrowthMapView overlayEnabled={overlayEnabled} selectedYear={selectedYear} visible={visualLayer === 'growth'} /> :
              id === 'tourism'       ? <TourismMapView /> :
                                       <PopulationMapView />
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
