import { useEffect, useRef } from 'react';
import {
  createLockedMap, addFrame, loadBoundary, onEveryStyleLoad, hideRoads, MAP_STYLES,
} from '../utils/mapboxBase';

// Lifecycle for a locked Andorra Mapbox map:
//  • creates the map once,
//  • loads + draws the frame (boundary / mask / corners),
//  • re-applies the frame and the caller's overlays after every style switch,
//  • swaps the base style when `styleKey` changes.
//
// `addOverlays(map)` must be idempotent (guard with map.getLayer/getSource); it is called
// on every style load. After async data arrives, the caller should call addOverlays(map)
// once more (guarded by map.isStyleLoaded()).
export function useLockedMapbox(containerRef, styleKey, addOverlays) {
  const mapRef          = useRef(null);
  const boundaryRef     = useRef(null);
  const addOverlaysRef  = useRef(addOverlays);
  const prevStyleRef    = useRef(styleKey);
  const styleKeyRef     = useRef(styleKey);
  addOverlaysRef.current = addOverlays;
  styleKeyRef.current    = styleKey;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = createLockedMap(containerRef.current, styleKey);
    mapRef.current = map;

    loadBoundary().then(b => {
      boundaryRef.current = b;
      if (map.isStyleLoaded()) addFrame(map, b);
    });

    onEveryStyleLoad(map, () => {
      if (styleKeyRef.current === 'satellite') hideRoads(map);
      addFrame(map, boundaryRef.current);
      addOverlaysRef.current?.(map);
    });

    return () => { try { map.remove(); } catch (_) {} mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (prevStyleRef.current === styleKey) return;
    prevStyleRef.current = styleKey;
    const url = MAP_STYLES[styleKey];
    if (url) map.setStyle(url);
  }, [styleKey]);

  return { mapRef, boundaryRef };
}
