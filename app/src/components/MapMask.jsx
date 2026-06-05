import { useEffect, useRef, useState } from 'react';

let nextMaskId = 0;

const CORNERS = [
  [42.694543, 1.393847],
  [42.697242, 1.801074],
  [42.396861, 1.803713],
  [42.394176, 1.39849],
];

export default function MapMask({ mapInstance }) {
  const [points, setPoints] = useState(null);
  const maskIdRef = useRef(null);

  if (!maskIdRef.current) {
    nextMaskId += 1;
    maskIdRef.current = `andorra-map-mask-${nextMaskId}`;
  }

  useEffect(() => {
    let map = null;
    let attached = false;

    function update() {
      if (!map) return;
      try {
        const pts = CORNERS.map(([lat, lon]) => {
          const p = map.latLngToContainerPoint([lat, lon]);
          return `${p.x},${p.y}`;
        });
        setPoints(pts.join(' '));
      } catch (_) {}
    }

    function tryAttach() {
      const candidate = mapInstance?.current ?? mapInstance;
      // Reject plain ref objects (current still null) or non-Leaflet values
      if (!candidate || typeof candidate.whenReady !== 'function') return;
      map = candidate;
      attached = true;
      map.whenReady(update);
      map.on('resize move zoom', update);
    }

    // Poll until the map instance is ready (parent effect runs after child effect)
    const interval = setInterval(() => {
      if (!attached) tryAttach();
      else clearInterval(interval);
    }, 50);

    return () => {
      clearInterval(interval);
      if (map) map.off('resize move zoom', update);
    };
  }, [mapInstance]);

  if (!points) return null;

  return (
    <svg
      style={{
        position: 'absolute', inset: 0, width: '100%', height: '100%',
        pointerEvents: 'none', zIndex: 500,
      }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <mask id={maskIdRef.current}>
          <rect width="100%" height="100%" fill="white" />
          <polygon points={points} fill="black" />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="black" mask={`url(#${maskIdRef.current})`} />
    </svg>
  );
}
