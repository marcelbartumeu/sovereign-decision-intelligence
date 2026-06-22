declare module '@deck.gl/react';
declare module '@deck.gl/layers';
declare module '@deck.gl/core';
declare module '@deck.gl/geo-layers';

import { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, BitmapLayer } from '@deck.gl/layers';
import { TileLayer, TripsLayer } from '@deck.gl/geo-layers';
import { WebMercatorViewport } from '@deck.gl/core';
import type { MapViewState } from '@deck.gl/core';
import styled from 'styled-components';
import { useSharedState } from '../services/SharedStateContext';
import { SharedControlPanel } from '../components/SharedControlPanel';
import type { TripAgent } from '../services/SharedStateContext';

const MapContainer = styled.div`
  width: 100vw;
  height: 100vh;
  position: relative;
  background: #0d0d0d;
  overflow: hidden;
`;

// Physical projection bounds — four corners of the 120×120 cm 3D table
const PROJECTION_BOUNDS: [[number, number], [number, number]] = [
  [1.393847, 42.394176],
  [1.803713, 42.697242],
];

const FALLBACK_VIEW_STATE: MapViewState = {
  longitude: 1.598780,
  latitude:  42.545709,
  zoom: 10.9,
  pitch: 0,
  bearing: 0,
};

const KEYSTONE_DOTS = [
  { position: [1.393847, 42.694543] as [number, number] },
  { position: [1.801074, 42.697242] as [number, number] },
  { position: [1.39849,  42.394176] as [number, number] },
  { position: [1.803713, 42.396861] as [number, number] },
];

const MASK_CORNERS: [number, number][] = [
  [1.393847, 42.694543],
  [1.801074, 42.697242],
  [1.803713, 42.396861],
  [1.39849,  42.394176],
];

// Emotion → RGB. The four emotions that occur in the agent data (ANGER,
// ENJOYMENT, FEAR, SADNESS) use the EXACT scenario hues — Overgrowth crimson,
// Degrowth green, Density gold, Continuity blue — so the map matches the
// scenario palette. CONTEMPT/DISGUST/SURPRISE don't occur in the data; they keep
// distinct tints only so the legend stays unambiguous. Keep the TRAIL legend in sync.
const EMOTION_RGB: Record<string, [number, number, number]> = {
  ENJOYMENT: [7, 111, 55],    // #076f37 Degrowth green
  ANGER:     [189, 6, 56],    // #bd0638 Overgrowth crimson
  FEAR:      [234, 179, 8],   // #eab308 Density gold
  SADNESS:   [41, 77, 175],   // #294daf Continuity blue
  CONTEMPT:  [124, 58, 237],  // #7c3aed violet (not in data)
  DISGUST:   [194, 65, 12],   // #c2410c burnt orange (not in data)
  SURPRISE:  [8, 145, 178],   // #0891b2 teal (not in data)
};
const emotionColor = (emotion: string): [number, number, number] =>
  EMOTION_RGB[emotion] ?? [148, 163, 184]; // #94a3b8 slate fallback

// Fallback base tiles when the parent hasn't supplied a Mapbox base yet (e.g.
// the viz opened standalone, or no Mapbox token). The parent app pushes its
// shared Mapbox raster URL via postMessage — see mapboxBase.rasterTilesUrl.
const ESRI_SATELLITE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const ESRI_LABELS    = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}';

// An agent's trips do NOT chain (dest_i ≠ origin_{i+1}) and can overlap in time,
// so its path is a concatenation of independent trip segments delimited by `bounds`
// (each bounds[k] is the start index of trip k). Interpolating across the whole
// path would draw straight "teleport" lines between trips, so instead we locate the
// trip segment ACTIVE at time t and interpolate only within it; between trips the
// agent holds at its last destination.
function interpSegment(
  path: [number, number][], ts: number[], s: number, e: number, t: number,
): [number, number] {
  if (t <= ts[s]) return path[s];
  if (t >= ts[e - 1]) return path[e - 1];
  let lo = s, hi = e - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (ts[mid] <= t) lo = mid; else hi = mid;
  }
  const a = path[lo], b = path[hi];
  const span = ts[hi] - ts[lo];
  const f = span > 0 ? (t - ts[lo]) / span : 0;
  return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])];
}

function agentPosition(a: any, t: number): [number, number] | null {
  const path = a.path as [number, number][];
  const ts   = a.ts as number[];
  const n = path?.length ?? 0;
  if (!n || !ts || ts.length !== n) return n ? path[0] : null;
  const bnds: number[] = (a.bounds && a.bounds.length) ? a.bounds : [0];
  let best = -1, bestDep = -Infinity;       // active trip with the latest departure
  let park = -1, parkEnd = -Infinity;       // most-recent trip that has finished
  for (let k = 0; k < bnds.length; k++) {
    const s = bnds[k];
    const e = k + 1 < bnds.length ? bnds[k + 1] : n;
    if (e - s < 1) continue;
    const dep = ts[s], arr = ts[e - 1];
    if (t >= dep && t <= arr && dep > bestDep) { bestDep = dep; best = k; }
    if (arr <= t && arr > parkEnd) { parkEnd = arr; park = k; }
  }
  if (best >= 0) {
    const s = bnds[best];
    const e = best + 1 < bnds.length ? bnds[best + 1] : n;
    return interpSegment(path, ts, s, e, t);
  }
  if (park >= 0) {                           // parked: hold at last destination
    const e = park + 1 < bnds.length ? bnds[park + 1] : n;
    return path[e - 1];
  }
  return path[0];
}


function MapView() {
  const { state, setFollowedAgent } = useSharedState();
  const [viewState, setViewState]   = useState<MapViewState>(FALLBACK_VIEW_STATE);
  const [maskPoints, setMaskPoints] = useState<string | null>(null);
  const [baseTilesUrl, setBaseTilesUrl] = useState<string | null>(null);
  const [baseStyleKey, setBaseStyleKey] = useState<string | null>(null);
  const deckContainerRef = useRef<HTMLDivElement>(null);
  const DeckGLAny: any = DeckGL;

  // Base map = single source of truth from the parent app (mapboxBase.js). Ask
  // for it on mount and listen for pushes (style switches). Until it arrives we
  // render the ArcGIS fallback, so the map is never blank.
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.data?.type === 'MAP_BASE_CONFIG' && e.data.data?.satelliteUrl) {
        setBaseTilesUrl(e.data.data.satelliteUrl as string);
        setBaseStyleKey((e.data.data.styleKey as string) ?? null);
      }
    };
    window.addEventListener('message', onMsg);
    window.parent?.postMessage({ type: 'MAP_BASE_REQUEST' }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);

  // Fit view to projection bounds on mount and resize
  useEffect(() => {
    const el = deckContainerRef.current;
    if (!el) return;
    const fit = () => {
      const { width, height } = el.getBoundingClientRect();
      if (!width || !height) return;
      try {
        const vp      = new WebMercatorViewport({ width, height });
        const fitted  = vp.fitBounds(PROJECTION_BOUNDS, { padding: 0 });
        setViewState({ longitude: fitted.longitude, latitude: fitted.latitude, zoom: fitted.zoom, pitch: 0, bearing: 0 });
      } catch {
        setViewState(FALLBACK_VIEW_STATE);
      }
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Recompute SVG mask whenever viewState changes
  useEffect(() => {
    const el = deckContainerRef.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    if (!width || !height) return;
    try {
      const vp  = new WebMercatorViewport({ width, height, ...viewState });
      const pts = MASK_CORNERS.map(([lon, lat]) => {
        const [x, y] = vp.project([lon, lat]);
        return `${x},${y}`;
      });
      setMaskPoints(pts.join(' '));
    } catch {}
  }, [viewState]);


  // Apply nationality + emotion filters
  const visibleAgents = useMemo(() => {
    let agents = state.agents;
    if (state.natFilter)     agents = agents.filter(a => a.nat === state.natFilter);
    if (state.emotionFilter) agents = agents.filter(a => a.emotion === state.emotionFilter);
    return agents;
  }, [state.agents, state.natFilter, state.emotionFilter]);

  // One sub-trail per TRIP, split at `bounds`, so trails only trace the actual
  // on-road trips and never the straight teleport between two unchained trips.
  // Static — depends only on the loaded agents, so it runs once, not per frame.
  const agentTrails = useMemo(() => {
    const out: { path: [number, number][]; ts: number[]; color: [number, number, number]; nat: string; emotion: string }[] = [];
    for (const a of state.agents as any[]) {
      const path = a.path, ts = a.ts;
      if (!path || !ts || path.length < 2 || ts.length !== path.length) continue;
      const bnds: number[] = (a.bounds && a.bounds.length) ? a.bounds : [0];
      for (let k = 0; k < bnds.length; k++) {
        const s = bnds[k];
        const e = k + 1 < bnds.length ? bnds[k + 1] : path.length;
        if (e - s >= 2) out.push({ path: path.slice(s, e), ts: ts.slice(s, e), color: emotionColor(a.emotion), nat: a.nat, emotion: a.emotion });
      }
    }
    return out;
  }, [state.agents]);

  const visibleTrails = useMemo(() => {
    let t = agentTrails;
    if (state.natFilter)     t = t.filter(x => x.nat === state.natFilter);
    if (state.emotionFilter) t = t.filter(x => x.emotion === state.emotionFilter);
    return t;
  }, [agentTrails, state.natFilter, state.emotionFilter]);

  // Current position of followed agent (for ScatterplotLayer highlight)
  const followedDot = useMemo(() => {
    if (!state.followedAgentId) return [];
    const agent = state.agents.find(a => a.id === state.followedAgentId);
    if (!agent) return [];
    const t = state.currentTimeMin;
    const position = agentPosition(agent, t);
    if (!position) return [];
    return [{ position, agent }];
  }, [state.followedAgentId, state.agents, state.currentTimeMin]);

  const layers = useMemo(() => {

    const keystoneLayer = new ScatterplotLayer({
      id: 'keystone-corners',
      data: KEYSTONE_DOTS,
      getPosition: (d: any) => d.position,
      getFillColor: [255, 51, 51, 230] as [number, number, number, number],
      getLineColor: [255, 255, 255, 255] as [number, number, number, number],
      getLineWidth: 2,
      getRadius: 8,
      radiusUnits: 'pixels',
      stroked: true,
    } as any);

    const satelliteTiles = new TileLayer({
      id: 'satellite-tiles',
      data: baseTilesUrl ?? ESRI_SATELLITE,
      minZoom: 0, maxZoom: 19, tileSize: 256,
      renderSubLayers: (props: any) => {
        const { bbox: { west, south, east, north } } = props.tile;
        return new BitmapLayer(props, { data: undefined, image: props.data, bounds: [west, south, east, north] });
      },
    });

    const labelTiles = new TileLayer({
      id: 'label-tiles',
      data: ESRI_LABELS,
      minZoom: 0, maxZoom: 19, tileSize: 256,
      renderSubLayers: (props: any) => {
        const { bbox: { west, south, east, north } } = props.tile;
        return new BitmapLayer(props, { data: undefined, image: props.data, bounds: [west, south, east, north] });
      },
    });

    // The satellite imagery (satellite-v9 raster, or the ArcGIS fallback) carries
    // no labels, so overlay the clean ArcGIS place labels there. dark/light bases
    // already include their own labels, so they get no overlay.
    const showLabels = !baseTilesUrl || baseStyleKey === 'satellite';
    const baseLayers = showLabels ? [satelliteTiles, labelTiles] : [satelliteTiles];

    if (!visibleAgents.length) return [...baseLayers, keystoneLayer];

    // Interpolate each agent along its FULL routed path (home→work→home→…) using
    // its timestamps, so agents traverse their day rather than freezing at home.
    const t = state.currentTimeMin;
    const dotData = visibleAgents
      .map(a => {
        const position = agentPosition(a, t);
        if (!position) return null;
        return { position, color: emotionColor(a.emotion), id: a.id, nat: a.nat, inc: a.inc, emotion: a.emotion };
      })
      .filter(Boolean) as { position: [number, number]; color: [number, number, number]; id: string; nat: string; inc: string; emotion: string }[];

    const dotsLayer = new ScatterplotLayer({
      id:             'agent-heads',
      data:           dotData,
      getPosition:    (d: any) => d.position,
      getFillColor:   (d: any) => [...d.color, 235] as [number, number, number, number],
      // Soft, low-opacity dark halo (ties to the dark base) — just enough to lift
      // the dot off the imagery, without the heavy black ring of before.
      getLineColor:   [3, 6, 18, 95] as [number, number, number, number],
      getLineWidth:   0.8,
      lineWidthUnits: 'pixels',
      lineWidthMinPixels: 0.6,
      getRadius:      3,
      radiusUnits:    'pixels',
      radiusMinPixels:2,
      radiusMaxPixels:5,
      stroked:        true,
      pickable:       true,
    } as any);

    // Followed agent highlight (small dot)
    const followedLayer = followedDot.length > 0 ? [
      new ScatterplotLayer({
        id: 'followed-outer',
        data: followedDot,
        getPosition: (d: any) => d.position,
        getFillColor: [0, 0, 0, 0] as [number, number, number, number],
        getLineColor: [255, 255, 255, 255] as [number, number, number, number],
        lineWidthUnits: 'pixels',
        getLineWidth: 2,
        getRadius: 20,
        radiusUnits: 'pixels',
        stroked: true, filled: false,
      } as any),
      new ScatterplotLayer({
        id: 'followed-dot',
        data: followedDot,
        getPosition: (d: any) => d.position,
        getFillColor: [255, 255, 255, 255] as [number, number, number, number],
        getRadius: 6,
        radiusUnits: 'pixels',
        stroked: false,
      } as any),
    ] : [];

    // Fading trails that trace each agent's FULL routed road path, so movement
    // visibly follows the road network (this is the "TRAIL" the legend refers to).
    // Path geometry is static on the GPU; only currentTime changes per frame, and
    // fadeTrail means parked agents (between trips) leave no trail.
    const trailsLayer = new TripsLayer({
      id:             'agent-trails',
      data:           visibleTrails,
      getPath:        (d: any) => d.path,
      getTimestamps:  (d: any) => d.ts,
      getColor:       (d: any) => d.color,
      currentTime:    t,
      trailLength:    30,
      fadeTrail:      true,
      capRounded:     true,
      jointRounded:   true,
      widthUnits:     'pixels',
      getWidth:       1.6,
      widthMinPixels: 1.4,
      opacity:        0.75,
    } as any);

    return [...baseLayers, trailsLayer, dotsLayer, ...followedLayer, keystoneLayer];
  }, [visibleAgents, visibleTrails, state.currentTimeMin, followedDot, baseTilesUrl, baseStyleKey]);

  const handleClick = ({ object }: { object: any }) => {
    if (!object) { setFollowedAgent(null); return; }
    const id = (object as TripAgent).id;
    setFollowedAgent(state.followedAgentId === id ? null : id);
  };

  return (
    <MapContainer>
      <div ref={deckContainerRef} style={{ position: 'absolute', inset: 0 }}>
        <DeckGLAny
          viewState={viewState}
          controller={false}
          layers={layers}
          style={{ width: '100%', height: '100%' }}
          onClick={handleClick}
          getTooltip={({ object }: { object: any }) => {
            if (!object) return null;
            const a = object as TripAgent;
            const h = Math.floor(state.currentTimeMin / 60).toString().padStart(2, '0');
            const m = Math.floor(state.currentTimeMin % 60).toString().padStart(2, '0');
            return {
              html: `
                <div><strong>${a.id}</strong></div>
                <div>Nationality: ${a.nat}</div>
                <div>Income: ${a.inc}</div>
                <div>Emotion: ${a.emotion}</div>
                <div>Time: ${h}:${m}</div>
              `,
              style: {
                background: 'rgba(10,10,15,0.9)', color: '#e5e7eb',
                fontSize: '11px', padding: '6px 10px',
                fontFamily: "'IBM Plex Mono', monospace",
                borderRadius: '4px', border: '1px solid #1f2937',
              },
            };
          }}
        />
      </div>

      {/* Black mask outside the 4 keystone corners */}
      {maskPoints && (
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 5 }}>
          <defs>
            <mask id="deckMask">
              <rect width="100%" height="100%" fill="white" />
              <polygon points={maskPoints} fill="black" />
            </mask>
          </defs>
          <rect width="100%" height="100%" fill="black" mask="url(#deckMask)" />
        </svg>
      )}

      <SharedControlPanel />

      {/* Emotion legend */}
      <div style={{
        position: 'absolute', bottom: 16, right: 16, zIndex: 10,
        background: 'rgba(10,10,15,0.85)', border: '1px solid #1f2937',
        borderRadius: 6, padding: '8px 12px',
        fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#9ca3af',
        pointerEvents: 'none',
      }}>
        <div style={{ fontSize: 9, letterSpacing: '0.12em', color: '#6b7280', marginBottom: 6 }}>TRAIL — EMOTION</div>
        {[
          { color: '#076f37', label: 'ENJOYMENT' },
          { color: '#bd0638', label: 'ANGER' },
          { color: '#eab308', label: 'FEAR' },
          { color: '#294daf', label: 'SADNESS' },
          { color: '#7c3aed', label: 'CONTEMPT' },
          { color: '#c2410c', label: 'DISGUST' },
          { color: '#0891b2', label: 'SURPRISE' },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <div style={{ width: 16, height: 3, borderRadius: 2, background: color, flexShrink: 0 }} />
            <span style={{ fontSize: 9, letterSpacing: '0.06em' }}>{label}</span>
          </div>
        ))}
      </div>
    </MapContainer>
  );
}

export default MapView;
