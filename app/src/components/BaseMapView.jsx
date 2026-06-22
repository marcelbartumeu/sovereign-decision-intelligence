import { useRef, useCallback } from 'react';
import { useLockedMapbox } from '../hooks/useLockedMapbox';
import { DEFAULT_MAP_STYLE } from '../utils/mapboxBase';
import 'mapbox-gl/dist/mapbox-gl.css';

// Base map: just the selected Mapbox style (satellite / dark / light) with the keystone
// frame. All overlays come from the shared frame, so there is nothing extra to add.
export default function BaseMapView({ mapStyle = DEFAULT_MAP_STYLE }) {
  const containerRef = useRef(null);
  const addOverlays  = useCallback(() => {}, []);
  useLockedMapbox(containerRef, mapStyle, addOverlays);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={containerRef} style={{ position: 'absolute', inset: 0, background: '#000' }} />
      <div style={{
        position: 'absolute', bottom: 8, left: 10, zIndex: 600,
        background: 'rgba(0,0,0,0.6)', borderRadius: 4, padding: '3px 8px',
        fontSize: '0.68rem', color: 'rgba(200,200,200,0.8)', letterSpacing: '.08em', pointerEvents: 'none',
      }}>
        BASE · ANDORRA
      </div>
    </div>
  );
}
