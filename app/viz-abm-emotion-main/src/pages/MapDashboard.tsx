declare module '@deck.gl/react';
declare module '@deck.gl/layers';
declare module '@deck.gl/core';
declare module '@deck.gl/geo-layers';

/**
 * MAP DASHBOARD — Projector B
 *
 * Designed for a 120 cm × 120 cm square projection surface.
 * No controls, no sidebar. Pure spatial visualization.
 * Receives all state (filters, followed agent, play/pause) from KPI Dashboard
 * via SharedStateContext + TabSyncService BroadcastChannel.
 *
 * Open this page in the projector browser window:
 *   http://localhost:5173/map-dashboard
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { Map as MapGL } from 'react-map-gl';
import { ScatterplotLayer, TextLayer, PathLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import type { MapViewState, PickingInfo } from '@deck.gl/core';
import { FlyToInterpolator, WebMercatorViewport } from '@deck.gl/core';
import { easeCubic } from 'd3-ease';
import styled, { keyframes } from 'styled-components';
import 'mapbox-gl/dist/mapbox-gl.css';
import { useSharedState } from '../services/SharedStateContext';
import {
  SCENARIO_COLORS, SCENARIO_LABELS, MAP_LAYER_LABELS,
  getScenarioYear, ANDORRA_PARISHES, ANDORRA_TOURISM_HOTSPOTS,
  type MapLayerId,
} from '../services/ScenarioDataService';

const MAPBOX_ACCESS_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

// ── Constants ─────────────────────────────────────────────────────────────────

const EKMAN_COLORS: Record<string, [number, number, number]> = {
  ANGER:    [239, 68,  68],
  CONTEMPT: [168, 85, 247],
  DISGUST:  [34, 197, 94],
  ENJOYMENT:[234,179,  8],
  FEAR:     [249,115, 22],
  SADNESS:  [59, 130, 246],
  SURPRISE: [236, 72, 153],
};

const EKMAN_HEX: Record<string, string> = {
  ANGER:    '#ef4444',
  CONTEMPT: '#a855f7',
  DISGUST:  '#22c55e',
  ENJOYMENT:'#eab308',
  FEAR:     '#f97316',
  SADNESS:  '#3b82f6',
  SURPRISE: '#ec4899',
};

const COLOR_TO_EKMAN: Record<string, string> = {
  red:    'ANGER',
  purple: 'CONTEMPT',
  green:  'ENJOYMENT',
  blue:   'SURPRISE',
  orange: 'FEAR',
  yellow: 'ENJOYMENT',
};

const TRANSPORT_COLORS: Record<string, [number, number, number]> = {
  foot:    [200, 200, 200],
  bicycle: [255,  87,  51],
  car:     [51,  161, 255],
  bus:     [51,  255,  87],
  train:   [255,  51, 233],
};

// Four corners of the 120×120 cm physical projection table
const PROJECTION_BOUNDS: [[number, number], [number, number]] = [
  [1.393847, 42.394176],   // SW
  [1.803713, 42.697242],   // NE
];

const KEYSTONE_DOTS = [
  { position: [1.393847, 42.694543] as [number, number] },  // NW
  { position: [1.801074, 42.697242] as [number, number] },  // NE
  { position: [1.39849,  42.394176] as [number, number] },  // SW
  { position: [1.803713, 42.396861] as [number, number] },  // SE
];

const INITIAL_VIEW: MapViewState = {
  longitude: 1.598780,
  latitude:  42.545709,
  zoom:      10.9,
  pitch:     0,
  bearing:   0,
};

// ── Styled ────────────────────────────────────────────────────────────────────

const pulse = keyframes`
  0%   { opacity: 1; }
  50%  { opacity: 0.3; }
  100% { opacity: 1; }
`;

/**
 * Full-viewport map — fills the entire projector output pixel-for-pixel.
 * The ResizeObserver + WebMercatorViewport.fitBounds ensures the geographic
 * corners align with the physical table corners at any screen resolution.
 */
const FullMap = styled.div`
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #000;
`;

// ── Overlays ──────────────────────────────────────────────────────────────────

const StepBadge = styled.div`
  position: absolute;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.75);
  border: 1px solid #374151;
  border-radius: 20px;
  padding: 5px 20px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  letter-spacing: 0.1em;
  color: #9ca3af;
  z-index: 20;
  pointer-events: none;
  white-space: nowrap;
`;

const SyncDot = styled.div<{ $active: boolean }>`
  width: 7px; height: 7px;
  border-radius: 50%;
  background: ${p => p.$active ? '#4ade80' : '#374151'};
  animation: ${p => p.$active ? pulse : 'none'} 2s ease-in-out infinite;
  display: inline-block;
  margin-right: 6px;
`;

const SyncBadge = styled.div`
  position: absolute;
  top: 18px;
  right: 18px;
  background: rgba(0,0,0,0.7);
  border: 1px solid #1f2937;
  border-radius: 6px;
  padding: 4px 10px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.1em;
  color: #6b7280;
  z-index: 20;
  pointer-events: none;
  display: flex;
  align-items: center;
`;

const Legend = styled.div`
  position: absolute;
  bottom: 18px;
  left: 18px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  z-index: 20;
  pointer-events: none;
`;

const LegendBlock = styled.div`
  background: rgba(0,0,0,0.72);
  border: 1px solid #1f2937;
  border-radius: 5px;
  padding: 5px 9px;
`;

const LRow = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: #9ca3af;
  line-height: 1.7;
`;

const LDot = styled.div<{ $r: number; $g: number; $b: number }>`
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: rgb(${p => p.$r},${p => p.$g},${p => p.$b});
`;

const FilterNotice = styled.div`
  position: absolute;
  bottom: 18px;
  right: 18px;
  background: rgba(0,0,0,0.75);
  border: 1px solid #facc1566;
  border-radius: 6px;
  padding: 5px 12px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: #facc15;
  letter-spacing: 0.08em;
  z-index: 20;
  pointer-events: none;
`;

const LayerSwitcher = styled.div`
  position: absolute;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 4px;
  z-index: 30;
  pointer-events: all;
`;

const LayerBtn = styled.button<{ $active: boolean; $color: string }>`
  padding: 5px 16px;
  border-radius: 20px;
  border: 1px solid ${p => p.$active ? p.$color : '#374151'};
  background: ${p => p.$active ? `${p.$color}30` : 'rgba(0,0,0,0.7)'};
  color: ${p => p.$active ? p.$color : '#6b7280'};
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all 0.15s;
  backdrop-filter: blur(4px);
  &:hover { border-color: ${p => p.$color}; color: ${p => p.$color}; }
`;

const ScenarioBadge = styled.div<{ $color: string }>`
  position: absolute;
  top: 18px;
  left: 18px;
  background: rgba(0,0,0,0.75);
  border: 1px solid ${p => p.$color}55;
  border-radius: 6px;
  padding: 5px 12px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: ${p => p.$color};
  letter-spacing: 0.1em;
  font-weight: 700;
  z-index: 20;
  pointer-events: none;
  line-height: 1.7;
`;

const AgentLabel = styled.div`
  position: absolute;
  top: 18px;
  left: 18px;
  background: rgba(0,0,0,0.8);
  border: 1px solid #ffd70066;
  border-radius: 6px;
  padding: 5px 12px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: #ffd700;
  letter-spacing: 0.08em;
  z-index: 20;
  pointer-events: none;
  line-height: 1.7;
`;

// ── Types ─────────────────────────────────────────────────────────────────────

interface TripData {
  agentId: string;
  agentType: string;
  emotion: string;
  transport: string;
  path: Array<[number, number]>;
  timestamps: Array<number>;
}

interface ScatterData {
  agentId: string;
  agentType: string;
  emotion: string;
  transport: string;
  position: [number, number];
}

// ── Component ─────────────────────────────────────────────────────────────────

const MAP_LAYER_ORDER: MapLayerId[] = ['agents', 'base', 'tourism', 'growth'];

export default function MapDashboard() {
  const { state, setFollowedAgent, setMapLayer } = useSharedState();

  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW);
  const [time, setTime]           = useState(0);
  const followLockRef             = useRef(false);
  const squareRef                 = useRef<HTMLDivElement>(null);

  // Fit view to physical projection bounds on mount and resize (only when not following an agent)
  useEffect(() => {
    const el = squareRef.current;
    if (!el) return;
    const fit = () => {
      if (followLockRef.current) return; // don't reset while tracking an agent
      const { width, height } = el.getBoundingClientRect();
      if (!width || !height) return;
      try {
        const vp = new WebMercatorViewport({ width, height });
        const { longitude, latitude, zoom } = vp.fitBounds(PROJECTION_BOUNDS, { padding: 0 });
        setViewState({ longitude, latitude, zoom, pitch: 0, bearing: 0 });
      } catch {}
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Return to projection bounds when agent is released
  useEffect(() => {
    if (state.followedAgent) return;
    followLockRef.current = false;
    const el = squareRef.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    if (!width || !height) return;
    try {
      const vp = new WebMercatorViewport({ width, height });
      const { longitude, latitude, zoom } = vp.fitBounds(PROJECTION_BOUNDS, { padding: 0 });
      setViewState({
        longitude, latitude, zoom, pitch: 0, bearing: 0,
        transitionDuration: 1000,
        transitionInterpolator: new FlyToInterpolator({ speed: 1.5 }),
        transitionEasing: easeCubic,
      });
    } catch {}
  }, [state.followedAgent]);

  // Sync time with shared step
  useEffect(() => {
    setTime(state.currentStep + state.currentInterpolationStep / 40);
  }, [state.currentStep, state.currentInterpolationStep]);

  // Follow camera when a specific agent is selected from KPI Dashboard
  useEffect(() => {
    if (!state.followedAgent || !state.simulationData?.agents) return;
    const agent = state.simulationData.agents.find(
      a => a.agent_id === state.followedAgent?.agentId
    );
    if (!agent?.path?.length) return;

    const maxI = agent.path.length - 1;
    const i = Math.min(Math.floor(time), maxI);
    const j = Math.min(i + 1, maxI);
    const f = state.currentInterpolationStep / 40;
    const lon = agent.path[i][0] + (agent.path[j][0] - agent.path[i][0]) * f;
    const lat = agent.path[i][1] + (agent.path[j][1] - agent.path[i][1]) * f;

    if (followLockRef.current) {
      setViewState(prev => ({
        ...prev, longitude: lon, latitude: lat,
        transitionDuration: 80,
        transitionInterpolator: new FlyToInterpolator({ speed: 2 }),
        transitionEasing: easeCubic,
      }));
    } else {
      // First time following — fly in
      followLockRef.current = true;
      setViewState(prev => ({
        ...prev, longitude: lon, latitude: lat, zoom: 18,
        transitionDuration: 1200,
        transitionInterpolator: new FlyToInterpolator({ speed: 1.5 }),
        transitionEasing: easeCubic,
      }));
    }
  }, [time, state.currentInterpolationStep, state.followedAgent, state.simulationData]);

  // Reset follow lock when agent changes
  useEffect(() => {
    followLockRef.current = false;
  }, [state.followedAgent?.agentId]);

  // ── Layer computation ─────────────────────────────────────────────────────

  const agentLayers = useMemo(() => {
    if (!state.simulationData?.agents) return [];

    const isFiltered = (agentType: string, emotion: string): boolean => {
      if (state.selectedAgentType && agentType !== state.selectedAgentType) return true;
      if (state.selectedEmotionFilter) {
        const ekman = COLOR_TO_EKMAN[emotion] ?? 'ENJOYMENT';
        if (ekman !== state.selectedEmotionFilter) return true;
      }
      return false;
    };

    const tripData: TripData[] = state.simulationData.agents.map(agent => ({
      agentId: agent.agent_id,
      agentType: agent.type,
      emotion: agent.emotion[Math.min(Math.floor(time), agent.emotion.length - 1)] ?? 'green',
      transport: agent.transport_method[Math.min(Math.floor(time), agent.transport_method.length - 1)] ?? 'foot',
      path: agent.path,
      timestamps: agent.path.map((_, i) => i * 40),
    }));

    const scatterData: ScatterData[] = state.simulationData.agents.flatMap(agent => {
      const maxI = agent.path.length - 1;
      if (maxI < 0) return [];
      const i = Math.min(Math.floor(time), maxI);
      const j = Math.min(i + 1, maxI);
      const f = state.currentInterpolationStep / 40;
      return [{
        agentId: agent.agent_id,
        agentType: agent.type,
        emotion: agent.emotion[Math.min(i, agent.emotion.length - 1)] ?? 'green',
        transport: agent.transport_method[Math.min(i, agent.transport_method.length - 1)] ?? 'foot',
        position: [
          agent.path[i][0] + (agent.path[j][0] - agent.path[i][0]) * f,
          agent.path[i][1] + (agent.path[j][1] - agent.path[i][1]) * f,
        ] as [number, number],
      }];
    });

    const out = [];

    out.push(new TripsLayer({
      id: 'trips',
      data: tripData,
      currentTime: state.currentStep * 40 + state.currentInterpolationStep,
      getPath: (d: TripData) => d.path,
      getTimestamps: (d: TripData) => d.timestamps,
      getColor: (d: TripData) => {
        if (isFiltered(d.agentType, d.emotion)) return [60, 60, 60, 30];
        return TRANSPORT_COLORS[d.transport] || [180, 180, 180];
      },
      opacity: 0.85,
      widthMinPixels: 2,
      rounded: true, fadeTrail: true, trailLength: 40, shadowEnabled: false,
    }));

    out.push(new ScatterplotLayer({
      id: 'agents',
      data: scatterData,
      pickable: true,
      getPosition: (d: ScatterData) => d.position,
      getFillColor: (d: ScatterData) => {
        if (isFiltered(d.agentType, d.emotion)) return [60, 60, 60, 40];
        const ekman = COLOR_TO_EKMAN[d.emotion] ?? 'ENJOYMENT';
        return EKMAN_COLORS[ekman] || [180, 180, 180];
      },
      getRadius: (d: ScatterData) => isFiltered(d.agentType, d.emotion) ? 3 : 9,
      radiusMinPixels: 3,
      radiusMaxPixels: 14,
      getLineColor: [255, 255, 255, 50],
      getLineWidth: 1,
      updateTriggers: {
        getFillColor: [state.selectedAgentType, state.selectedEmotionFilter, time],
        getRadius:    [state.selectedAgentType, state.selectedEmotionFilter],
      },
    } as any));

    if (state.followedAgent) {
      const focused = scatterData.find(d => d.agentId === state.followedAgent?.agentId);
      if (focused) {
        out.push(new ScatterplotLayer({
          id: 'focused-ring',
          data: [focused],
          getPosition: (d: ScatterData) => d.position,
          getFillColor: [255, 215, 0, 255],
          getRadius: 16,
          radiusMinPixels: 12,
          getLineColor: [255, 255, 255, 200],
          getLineWidth: 2,
          stroked: true,
        } as any));
        out.push(new TextLayer({
          id: 'focused-label',
          data: [focused],
          getPosition: (d: ScatterData) => d.position,
          getText: (d: ScatterData) => d.agentId,
          getSize: 14,
          getColor: [255, 215, 0, 255],
          getPixelOffset: [16, 0],
          getTextAnchor: 'start',
          fontFamily: 'IBM Plex Mono',
          fontWeight: 700,
        } as any));
      }
    }

    if (scatterData.length) {
      const bubbles: Array<{ position: [number,number]; text: string }> = [];
      state.simulationData.agents.forEach(agent => {
        if (!agent.conversation?.length) return;
        const idx = agent.conversation_timestamps?.findIndex(
          (t: number) => Math.abs(t - state.currentStep) < 2
        );
        if (idx >= 0 && agent.conversation[idx]) {
          const sd = scatterData.find(d => d.agentId === agent.agent_id);
          if (sd) bubbles.push({ position: sd.position, text: `"${agent.conversation[idx]}"` });
        }
      });
      if (bubbles.length) {
        out.push(new TextLayer({
          id: 'conversations',
          data: bubbles,
          getPosition: (d: any) => d.position,
          getText: (d: any) => d.text,
          getSize: 12,
          getColor: [255, 255, 255, 230],
          getPixelOffset: [0, -24],
          getTextAnchor: 'middle',
          fontFamily: 'IBM Plex Mono',
          background: true,
          getBackgroundColor: [0, 0, 0, 170],
        } as any));
      }
    }

    return out;
  }, [state, time]);

  // Tourism layer — hotspot scatter sized by Tour value
  const tourismLayers = useMemo(() => {
    const yearData = getScenarioYear(state.selectedScenario, state.selectedYear);
    if (!yearData) return [];

    // Normalise to [0.4, 1.0] across realistic tour range 8M–14M
    const intensity = Math.min(1, Math.max(0.4, (yearData.Tour - 8_000_000) / 6_000_000));

    const hotspots = ANDORRA_TOURISM_HOTSPOTS.map(h => ({
      ...h,
      position: [h.lon, h.lat] as [number, number],
      radius: 800 * h.weight * intensity,
      color: [249, 115, 22, Math.round(180 * h.weight * intensity)] as [number, number, number, number],
    }));

    const parishes = ANDORRA_PARISHES.map(p => ({
      ...p,
      position: [p.lon, p.lat] as [number, number],
      radius: 300 * p.weight * intensity,
      color: [251, 191, 36, Math.round(120 * p.weight * intensity)] as [number, number, number, number],
    }));

    return [
      new ScatterplotLayer({
        id: 'tourism-hotspots',
        data: hotspots,
        getPosition: (d: any) => d.position,
        getFillColor: (d: any) => d.color,
        getRadius: (d: any) => d.radius,
        radiusMinPixels: 20,
        opacity: 0.7,
        pickable: false,
      } as any),
      new ScatterplotLayer({
        id: 'tourism-parishes',
        data: parishes,
        getPosition: (d: any) => d.position,
        getFillColor: (d: any) => d.color,
        getRadius: (d: any) => d.radius,
        radiusMinPixels: 8,
        opacity: 0.5,
        pickable: false,
      } as any),
      new TextLayer({
        id: 'tourism-labels',
        data: hotspots,
        getPosition: (d: any) => d.position,
        getText: (d: any) => d.name,
        getSize: 11,
        getColor: [255, 255, 255, 200],
        getPixelOffset: [0, -20],
        getTextAnchor: 'middle',
        fontFamily: 'IBM Plex Mono',
        fontWeight: 700,
      } as any),
    ];
  }, [state.selectedScenario, state.selectedYear]);

  // Growth layer — parish scatter colored by GDP/pop growth rate
  const growthLayers = useMemo(() => {
    const yearData = getScenarioYear(state.selectedScenario, state.selectedYear);
    const prevYear = state.selectedYear > 2025
      ? getScenarioYear(state.selectedScenario, state.selectedYear - 1)
      : null;
    if (!yearData) return [];

    const gdpGrowth = prevYear
      ? (yearData.GDPpc - prevYear.GDPpc) / prevYear.GDPpc
      : 0.025; // default continuity rate
    const popGrowth = prevYear
      ? (yearData.Pop - prevYear.Pop) / prevYear.Pop
      : 0.016;

    // Color: blue (contraction) → green (growth)
    const growthToColor = (g: number): [number, number, number, number] => {
      if (g < 0) return [96, 165, 250, 200];   // blue = shrinking
      if (g < 0.02) return [74, 222, 128, 200]; // green = steady
      return [251, 146, 60, 220];               // orange = high growth
    };

    const parishes = ANDORRA_PARISHES.map((p, i) => ({
      ...p,
      position: [p.lon, p.lat] as [number, number],
      // Vary each parish slightly so it's not a uniform blob
      gdpG: gdpGrowth * (0.8 + i * 0.07),
      popG: popGrowth * (0.9 + i * 0.05),
      radius: 600 * p.weight,
    }));

    return [
      new ScatterplotLayer({
        id: 'growth-gdp',
        data: parishes,
        getPosition: (d: any) => d.position,
        getFillColor: (d: any) => growthToColor(d.gdpG),
        getRadius: (d: any) => d.radius,
        radiusMinPixels: 15,
        opacity: 0.65,
        pickable: false,
        updateTriggers: { getFillColor: [state.selectedScenario, state.selectedYear] },
      } as any),
      new TextLayer({
        id: 'growth-labels',
        data: parishes,
        getPosition: (d: any) => d.position,
        getText: (d: any) => `${d.name}\n+${(d.gdpG * 100).toFixed(1)}% GDP`,
        getSize: 10,
        getColor: [255, 255, 255, 210],
        getPixelOffset: [0, -18],
        getTextAnchor: 'middle',
        fontFamily: 'IBM Plex Mono',
        fontWeight: 600,
      } as any),
      // Pop growth overlay (smaller, layered)
      new ScatterplotLayer({
        id: 'growth-pop',
        data: parishes,
        getPosition: (d: any) => d.position,
        getFillColor: (d: any) => growthToColor(d.popG),
        getRadius: (d: any) => d.radius * 0.45,
        radiusMinPixels: 6,
        opacity: 0.9,
        pickable: false,
        updateTriggers: { getFillColor: [state.selectedScenario, state.selectedYear] },
      } as any),
    ];
  }, [state.selectedScenario, state.selectedYear]);

  const keystoneLayer = useMemo(() => new ScatterplotLayer({
    id: 'keystone-corners',
    data: KEYSTONE_DOTS,
    getPosition: (d: any) => d.position,
    getFillColor: [255, 51, 51, 230] as [number, number, number, number],
    getLineColor: [255, 255, 255, 255] as [number, number, number, number],
    getLineWidth: 2,
    getRadius: 8,
    radiusUnits: 'pixels',
    radiusMinPixels: 6,
    radiusMaxPixels: 10,
    stroked: true,
  } as any), []);

  const layers = useMemo(() => {
    const base = (() => {
      switch (state.activeMapLayer) {
        case 'agents':  return agentLayers;
        case 'tourism': return tourismLayers;
        case 'growth':  return growthLayers;
        case 'base':    return [];
        default:        return [];
      }
    })();
    return [...(base ?? []), keystoneLayer];
  }, [state.activeMapLayer, agentLayers, tourismLayers, growthLayers, keystoneLayer]);

  // ── Agent click → sends to KPI via shared state ───────────────────────────

  const handlePick = (info: PickingInfo) => {
    if (!info.object) return;
    const d = info.object as ScatterData;
    setFollowedAgent({
      agentId: d.agentId,
      agentType: d.agentType,
      emotion: d.emotion,
      transport: d.transport,
    });
  };

  const mapStyle = state.useRealisticMap
    ? 'mapbox://styles/mapbox/satellite-streets-v12'
    : 'mapbox://styles/mapbox/dark-v10';

  const hasFilter = !!(state.selectedAgentType || state.selectedEmotionFilter);
  const visibleCount = useMemo(() => {
    if (!state.simulationData?.agents) return 0;
    return state.simulationData.agents.filter(a => {
      if (state.selectedAgentType && a.type !== state.selectedAgentType) return false;
      if (state.selectedEmotionFilter) {
        const step = Math.min(state.currentStep, a.emotion.length - 1);
        const ekman = COLOR_TO_EKMAN[a.emotion[step]] ?? 'ENJOYMENT';
        if (ekman !== state.selectedEmotionFilter) return false;
      }
      return true;
    }).length;
  }, [state.simulationData, state.selectedAgentType, state.selectedEmotionFilter, state.currentStep]);

  return (
    <FullMap ref={squareRef}>
        {/* ── Map ─────────────────────────────────────────────────────────── */}
        <DeckGL
          viewState={viewState}
          onViewStateChange={({ viewState: vs }: any) => setViewState(vs)}
          layers={layers}
          controller={true}
          onClick={handlePick}
          getTooltip={({ object }: PickingInfo) => {
            if (!object) return null;
            const d = object as ScatterData;
            const ekman = COLOR_TO_EKMAN[d.emotion] ?? d.emotion;
            return {
              html: `<div style="font-family:'IBM Plex Mono',monospace;font-size:11px;line-height:1.9;padding:4px 2px">
                <b>${d.agentId}</b><br/>
                Type: ${d.agentType}<br/>
                Emotion: ${ekman}<br/>
                Transport: ${d.transport}
              </div>`,
              style: {
                background: 'rgba(0,0,0,0.9)', border: '1px solid #374151',
                borderRadius: '6px', color: '#e5e7eb',
              },
            };
          }}
        >
          <MapGL
            mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
            mapStyle={mapStyle}
            attributionControl={false}
            reuseMaps={false}
          />
        </DeckGL>

        {/* ── Step counter (top-center) ────────────────────────────────────── */}
        <StepBadge>
          {state.activeMapLayer === 'agents'
            ? <>STEP&nbsp;&nbsp;{state.currentStep}&nbsp;&nbsp;·&nbsp;&nbsp;{state.isPlaying ? '▶ LIVE' : '⏸ PAUSED'}&nbsp;&nbsp;·&nbsp;&nbsp;{visibleCount}&nbsp;AGENTS{hasFilter ? ' (FILTERED)' : ''}</>
            : <>{SCENARIO_LABELS[state.selectedScenario]}&nbsp;&nbsp;·&nbsp;&nbsp;{state.selectedYear}&nbsp;&nbsp;·&nbsp;&nbsp;{MAP_LAYER_LABELS[state.activeMapLayer]}</>
          }
        </StepBadge>

        {/* ── Sync indicator (top-right) ───────────────────────────────────── */}
        <SyncBadge>
          <SyncDot $active={state.isPlaying} />
          KPI SYNC
        </SyncBadge>

        {/* ── Scenario badge (top-left) — shown for non-agent layers ──────── */}
        {state.activeMapLayer !== 'agents' && !state.followedAgent && (
          <ScenarioBadge $color={SCENARIO_COLORS[state.selectedScenario]}>
            {SCENARIO_LABELS[state.selectedScenario]}<br />
            <span style={{ fontSize: 9, color: '#9ca3af', fontWeight: 400 }}>
              {state.selectedYear}&nbsp;·&nbsp;{MAP_LAYER_LABELS[state.activeMapLayer]}
            </span>
          </ScenarioBadge>
        )}

        {/* ── Followed agent label (top-left, only when following) ─────────── */}
        {state.followedAgent && (
          <AgentLabel>
            ◉&nbsp;&nbsp;{state.followedAgent.agentId}<br />
            <span style={{ color: '#9ca3af', fontSize: 9 }}>
              {state.followedAgent.agentType}&nbsp;·&nbsp;
              {COLOR_TO_EKMAN[state.followedAgent.emotion] ?? state.followedAgent.emotion}&nbsp;·&nbsp;
              {state.followedAgent.transport}
            </span>
          </AgentLabel>
        )}

        {/* ── Active filter badge (bottom-right) ──────────────────────────── */}
        {hasFilter && state.activeMapLayer === 'agents' && (
          <FilterNotice>
            FILTER: {state.selectedAgentType ?? '—'} / {state.selectedEmotionFilter ?? '—'}
          </FilterNotice>
        )}

        {/* ── Layer switcher (bottom-center) ───────────────────────────────── */}
        <LayerSwitcher>
          {MAP_LAYER_ORDER.map(l => (
            <LayerBtn
              key={l}
              $active={state.activeMapLayer === l}
              $color={l === 'agents' ? '#4ade80' : l === 'tourism' ? '#f97316' : l === 'growth' ? '#60a5fa' : '#9ca3af'}
              onClick={() => setMapLayer(l)}
            >
              {MAP_LAYER_LABELS[l]}
            </LayerBtn>
          ))}
        </LayerSwitcher>

        {/* ── Legend (bottom-left) — only for agents layer ──────────────────── */}
        {state.activeMapLayer === 'agents' && (
          <Legend>
            <LegendBlock>
              <div style={{ fontFamily: 'IBM Plex Mono', fontSize: 8, color: '#4b5563', letterSpacing: '0.1em', marginBottom: 3 }}>
                EMOTION · DOT COLOR
              </div>
              {Object.entries(EKMAN_COLORS).map(([name, rgb]) => (
                <LRow key={name}>
                  <LDot $r={rgb[0]} $g={rgb[1]} $b={rgb[2]} />
                  {name}
                </LRow>
              ))}
            </LegendBlock>
            <LegendBlock>
              <div style={{ fontFamily: 'IBM Plex Mono', fontSize: 8, color: '#4b5563', letterSpacing: '0.1em', marginBottom: 3 }}>
                TRANSPORT · TRAIL COLOR
              </div>
              {Object.entries(TRANSPORT_COLORS).map(([name, rgb]) => (
                <LRow key={name}>
                  <LDot $r={rgb[0]} $g={rgb[1]} $b={rgb[2]} />
                  {name}
                </LRow>
              ))}
            </LegendBlock>
          </Legend>
        )}

        {/* ── Tourism legend ───────────────────────────────────────────────── */}
        {state.activeMapLayer === 'tourism' && (
          <Legend>
            <LegendBlock>
              <div style={{ fontFamily: 'IBM Plex Mono', fontSize: 8, color: '#4b5563', letterSpacing: '0.1em', marginBottom: 3 }}>
                TOURISM INTENSITY
              </div>
              <LRow><LDot $r={249} $g={115} $b={22} />Ski resorts</LRow>
              <LRow><LDot $r={251} $g={191} $b={36} />Commercial zones</LRow>
            </LegendBlock>
          </Legend>
        )}

        {/* ── Growth legend ────────────────────────────────────────────────── */}
        {state.activeMapLayer === 'growth' && (
          <Legend>
            <LegendBlock>
              <div style={{ fontFamily: 'IBM Plex Mono', fontSize: 8, color: '#4b5563', letterSpacing: '0.1em', marginBottom: 3 }}>
                GDP GROWTH
              </div>
              <LRow><LDot $r={96}  $g={165} $b={250} />Contraction</LRow>
              <LRow><LDot $r={74}  $g={222} $b={128} />Steady growth</LRow>
              <LRow><LDot $r={251} $g={146} $b={60}  />High growth</LRow>
            </LegendBlock>
          </Legend>
        )}
    </FullMap>
  );
}
