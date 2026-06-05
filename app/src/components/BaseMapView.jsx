import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { addAndorraBoundary } from '../utils/andorraBoundary';
import MapMask from './MapMask';

const PROJECTION_BOUNDS = [[42.394176, 1.393847], [42.697242, 1.803713]];
const PROJECTION_CORNERS = [
  [42.694543, 1.393847],  // NW
  [42.697242, 1.801074],  // NE
  [42.394176, 1.39849],   // SW
  [42.396861, 1.803713],  // SE
];

export default function BaseMapView() {
  const mapRef = useRef(null);
  const instanceRef = useRef(null);

  useEffect(() => {
    if (!mapRef.current || instanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [42.545709, 1.598780],
      zoom: 11,
      zoomSnap: 0,
      zoomControl: false,
      attributionControl: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      touchZoom: false,
      boxZoom: false,
      dragging: false,
      keyboard: false,
    });

    instanceRef.current = map;
    map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] });
    map.on('resize', () => { map.invalidateSize(); map.fitBounds(PROJECTION_BOUNDS, { padding: [0, 0] }); });

    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18 }
    ).addTo(map);

    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 18, opacity: 0.7 }
    ).addTo(map);

    addAndorraBoundary(map);
    PROJECTION_CORNERS.forEach(([lat, lon]) => {
      L.circleMarker([lat, lon], { radius: 5, fillColor: '#ff3333', color: '#ffffff', weight: 2, fillOpacity: 1 }).addTo(map);
    });

    return () => {
      map.remove();
      instanceRef.current = null;
    };
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapRef} style={{ position: 'absolute', inset: 0 }} />
      <MapMask mapInstance={instanceRef} />
      <div style={{
        position: 'absolute', bottom: 8, left: 10, zIndex: 600,
        background: 'rgba(0,0,0,0.6)', borderRadius: 4, padding: '3px 8px',
        fontSize: '0.68rem', color: 'rgba(200,200,200,0.8)', letterSpacing: '.08em', pointerEvents: 'none',
      }}>
        BASE — SATELLITE IMAGERY · ANDORRA
      </div>
    </div>
  );
}
