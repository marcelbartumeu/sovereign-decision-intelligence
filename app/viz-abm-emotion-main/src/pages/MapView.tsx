declare module '@deck.gl/react';
declare module '@deck.gl/layers';
declare module '@deck.gl/core';
declare module '@deck.gl/geo-layers';

import { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, BitmapLayer, GeoJsonLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
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


function MapView() {
  const { state, setFollowedAgent } = useSharedState();
  const [viewState, setViewState]   = useState<MapViewState>(FALLBACK_VIEW_STATE);
  const [maskPoints, setMaskPoints] = useState<string | null>(null);
  const [roadGeoJSON, setRoadGeoJSON] = useState<any>(null);
  const deckContainerRef = useRef<HTMLDivElement>(null);
  const DeckGLAny: any = DeckGL;

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

  // Load road network for overlay
  useEffect(() => {
    fetch('/model/accessibility_streets.geojson')
      .then(r => r.json())
      .then(data => setRoadGeoJSON(data))
      .catch(() => {});
  }, []);

  // Apply nationality + emotion filters
  const visibleAgents = useMemo(() => {
    let agents = state.agents;
    if (state.natFilter)     agents = agents.filter(a => a.nat === state.natFilter);
    if (state.emotionFilter) agents = agents.filter(a => a.emotion === state.emotionFilter);
    return agents;
  }, [state.agents, state.natFilter, state.emotionFilter]);

  // Current position of followed agent (for ScatterplotLayer highlight)
  const followedDot = useMemo(() => {
    if (!state.followedAgentId) return [];
    const agent = state.agents.find(a => a.id === state.followedAgentId);
    if (!agent) return [];
    const t = state.currentTimeMin;
    let idx = agent.ts.findLastIndex((ts: number) => ts <= t);
    if (idx < 0) idx = 0;
    const posIdx = Math.min(idx, agent.path.length - 1);
    let position: [number, number] = agent.path[posIdx] ?? agent.path[0];
    const nextIdx = posIdx + 1;
    if (nextIdx < agent.path.length && nextIdx < agent.ts.length && agent.ts[posIdx] < agent.ts[nextIdx]) {
      const f = Math.max(0, Math.min(1, (t - agent.ts[posIdx]) / (agent.ts[nextIdx] - agent.ts[posIdx])));
      position = [
        agent.path[posIdx][0] + f * (agent.path[nextIdx][0] - agent.path[posIdx][0]),
        agent.path[posIdx][1] + f * (agent.path[nextIdx][1] - agent.path[posIdx][1]),
      ];
    }
    return [{ position, agent }];
  }, [state.followedAgentId, state.agents, state.currentTimeMin]);

  const layers = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _roadDep = roadGeoJSON; // ensure re-render when roads load

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
      data: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      minZoom: 0, maxZoom: 19, tileSize: 256,
      renderSubLayers: (props: any) => {
        const { bbox: { west, south, east, north } } = props.tile;
        return new BitmapLayer(props, { data: undefined, image: props.data, bounds: [west, south, east, north] });
      },
    });

    const labelTiles = new TileLayer({
      id: 'label-tiles',
      data: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      minZoom: 0, maxZoom: 19, tileSize: 256,
      renderSubLayers: (props: any) => {
        const { bbox: { west, south, east, north } } = props.tile;
        return new BitmapLayer(props, { data: undefined, image: props.data, bounds: [west, south, east, north] });
      },
    });

    const roadLayer = roadGeoJSON ? new (GeoJsonLayer as any)({
      id: 'road-network',
      data: roadGeoJSON,
      stroked: true,
      filled: false,
      lineWidthUnits: 'pixels',
      getLineWidth: 1,
      getLineColor: [80, 100, 120, 90],
      lineCapRounded: true,
      lineJointRounded: true,
      pickable: false,
    }) : null;

    if (!visibleAgents.length) return [satelliteTiles, labelTiles, ...(roadLayer ? [roadLayer] : []), keystoneLayer];

    // Current-position dots — binary search + linear interpolation between waypoints
    // so agents move smoothly along their road-following paths.
    const t = state.currentTimeMin;
    const dotData = visibleAgents
      .map(a => {
        let lo = 0, hi = a.ts.length - 1, idx = -1;
        while (lo <= hi) {
          const mid = (lo + hi) >> 1;
          if (a.ts[mid] <= t) { idx = mid; lo = mid + 1; } else hi = mid - 1;
        }
        const posIdx = idx < 0 ? 0 : Math.min(idx, a.path.length - 1);
        if (!a.path[posIdx]) return null;
        let position: [number, number] = a.path[posIdx];
        const nextIdx = posIdx + 1;
        if (nextIdx < a.path.length && nextIdx < a.ts.length && a.ts[posIdx] < a.ts[nextIdx]) {
          const f = Math.max(0, Math.min(1, (t - a.ts[posIdx]) / (a.ts[nextIdx] - a.ts[posIdx])));
          position = [
            a.path[posIdx][0] + f * (a.path[nextIdx][0] - a.path[posIdx][0]),
            a.path[posIdx][1] + f * (a.path[nextIdx][1] - a.path[posIdx][1]),
          ];
        }
        return { position, color: a.color, id: a.id, nat: a.nat, inc: a.inc, emotion: a.emotion };
      })
      .filter(Boolean) as { position: [number, number]; color: [number, number, number]; id: string; nat: string; inc: string; emotion: string }[];

    const dotsLayer = new ScatterplotLayer({
      id:             'agent-heads',
      data:           dotData,
      getPosition:    (d: any) => d.position,
      getFillColor:   (d: any) => [...d.color, 230] as [number, number, number, number],
      getLineColor:   [20, 20, 20, 180] as [number, number, number, number],
      getLineWidth:   1,
      lineWidthUnits: 'pixels',
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

    return [satelliteTiles, labelTiles, ...(roadLayer ? [roadLayer] : []), dotsLayer, ...followedLayer, keystoneLayer];
  }, [visibleAgents, state.currentTimeMin, followedDot, roadGeoJSON]);

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
          { color: '#34d399', label: 'ENJOYMENT' },
          { color: '#f87171', label: 'ANGER' },
          { color: '#fb923c', label: 'FEAR' },
          { color: '#60a5fa', label: 'SADNESS' },
          { color: '#c084fc', label: 'CONTEMPT' },
          { color: '#fbbf24', label: 'DISGUST' },
          { color: '#22d3ee', label: 'SURPRISE' },
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
