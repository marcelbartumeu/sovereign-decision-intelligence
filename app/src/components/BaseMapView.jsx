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
        background: 'rgba(4,6,10,0.6)', border: '1px solid rgba(63,224,230,0.18)',
        borderRadius: 3, padding: '3px 9px',
        fontFamily: 'var(--mono)', fontSize: '0.64rem', textTransform: 'uppercase',
        color: 'var(--cyan)', letterSpacing: '.16em', pointerEvents: 'none',
      }}>
        BASE · ANDORRA
      </div>
    </div>
  );
}
