/**
 * AgentAnalyticsView
 * ─────────────────────────────────────────────────────────────────────────────
 * Embedded in the main Andorra dashboard as a single iframe.
 * Left 55%  → face animation, emotion sphere, real-time chat
 * Right 45% → agent list sidebar + full Follow Agent detail (profile, radar,
 *              mood history, conversation)
 *
 * One React tree, one SharedStateProvider, one data load.
 */

import { useMemo, useState, useRef, useEffect } from 'react';
import styled from 'styled-components';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  LineChart, Line, CartesianGrid,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, BitmapLayer, PathLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
import type { MapViewState } from '@deck.gl/core';
import { useSharedState } from '../services/SharedStateContext';
import { AgentProfile, AgentJourney, EmotionState, PopulationDashboards } from './AgentAnalyticsPanels';
import HABMSentiments from '../components/HABMSentiments';
import AgentVisualizationToggle from '../components/AgentVisualizationToggle';
import RealTimeChat from '../components/RealTimeChat';

const DeckGLAny: any = DeckGL;

// ── Constants ─────────────────────────────────────────────────────────────────

const EKMAN_COLORS: Record<string, string> = {
  ANGER:    '#FF453A',  // sys-red
  CONTEMPT: '#BF5AF2',  // sys-purple
  DISGUST:  '#FFD60A',  // sys-yellow
  ENJOYMENT:'#30D158',  // sys-green
  FEAR:     '#FF9F0A',  // sys-orange
  SADNESS:  '#0A84FF',  // sys-blue
  SURPRISE: '#64D2FF',  // sys-teal
};

const EKMAN_ORDER = ['ANGER','CONTEMPT','DISGUST','ENJOYMENT','FEAR','SADNESS','SURPRISE'];

const COLOR_TO_EKMAN: Record<string, string> = {
  red:    'ANGER',
  purple: 'CONTEMPT',
  green:  'ENJOYMENT',
  blue:   'SADNESS',
  orange: 'FEAR',
  yellow: 'DISGUST',
};

const TYPE_COLORS: Record<string, string> = {
  blue:   '#5ba8f5',  // sky, distinct from sadness blue
  red:    '#f26d63',  // warm coral
  purple: '#b98ef7',  // lavender
  orange: '#f7aa52',  // warm amber
  green:  '#2ed4a4',  // cyan-teal
  Adult:  '#2ed4a4',
  Carlos: '#2ed4a4',
  Elena:  '#7ec8f9',
};

const AGENT_TYPES = ['blue', 'red', 'green', 'orange', 'purple'];

// ── Fake name generator ───────────────────────────────────────────────────────

const FIRST_NAMES = [
  'Marc','Joan','Pere','Antoni','Jordi','Pau','Ricard','Guillem','Xavier','Andreu',
  'Ferran','Albert','Arnau','Bernat','Clàudia','Aina','Miriam','Laia','Marta','Rosa',
  'Sophie','Emma','Léa','Clara','Juliette','Antoine','Nicolas','Pierre','Thomas','Hugo',
  'Carlos','Miguel','Diego','Álvaro','Sergio','Elena','Sofía','Carmen','Laura','Lucía',
  'Maria','Anna','Núria','Montserrat','Carme','Irene','David','Daniel','Luc','Nathalie',
];

const LAST_NAMES = [
  'Martínez','García','López','Sánchez','González','Rodríguez','Fernández','Torres',
  'Pérez','Álvarez','Puig','Serra','Mas','Pons','Vila','Roca','Bosch','Coll',
  'Durand','Moreau','Simon','Laurent','Bernard','Dubois','Thomas','Robert',
  'Casal','Badia','Salvat','Farré','Planes','Solà','Valls','Font','Miró',
  'Vilaró','Xalabarder','Bartumeu','Alís','Barba','Bonnet','Mercier','Girard',
];

const SPECIAL_NAMES: Record<string, string> = {
  Carlos: 'Carlos García',
  Elena:  'Elena Bartumeu',
};

function hashStr(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function getFakeName(agentId: string): string {
  if (SPECIAL_NAMES[agentId]) return SPECIAL_NAMES[agentId];
  const h = hashStr(agentId);
  return `${FIRST_NAMES[h % FIRST_NAMES.length]} ${LAST_NAMES[(h >>> 4) % LAST_NAMES.length]}`;
}

const PERSONALITIES = [
  'Extroverted','Introverted','Ambivert','Analytical','Creative',
  'Pragmatic','Empathetic','Assertive','Independent','Social',
];

const OCCUPATIONS = [
  'Tourism Manager','Retail Merchant','Financial Advisor','Ski Instructor',
  'Hotel Manager','Teacher','Doctor','Engineer','Government Official',
  'Real Estate Agent','Restaurant Owner','IT Specialist','Nurse',
  'Border Guard','Chef','Banker','Pharmacist','Architect','Lawyer','Accountant',
];

function getFakeAge(agentId: string): number {
  const h = hashStr(agentId + 'age');
  return 18 + (h % 55); // 18–72
}

function getFakePersonality(agentId: string): string {
  const h = hashStr(agentId + 'pers');
  return PERSONALITIES[h % PERSONALITIES.length];
}

function getFakeOccupation(agentId: string): string {
  const h = hashStr(agentId + 'occ');
  return OCCUPATIONS[h % OCCUPATIONS.length];
}

// ── Design tokens (Apple dark mode) ──────────────────────────────────────────

const BG    = '#000000';
const BG_GRADIENT = 'linear-gradient(180deg, #000000 0%, #1D1D22 100%)'; // matches main app --bg-gradient (KPI grid)
const SURF  = '#1c1c1e';
const SURF2 = '#2c2c2e';
const BDR   = 'rgba(255,255,255,0.08)';
const LBL   = 'rgba(255,255,255,0.32)';
const TXT2  = 'rgba(255,255,255,0.55)';
const TXT   = 'rgba(255,255,255,0.86)';
const ACT   = '#ffffff';
const FONT  = `'SF Pro Text', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif`;
const TITLE = `'Syne', 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif`;

const Wrapper = styled.div`
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  background: ${BG_GRADIENT};
  background-attachment: fixed;
  font-family: ${FONT};
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
`;

// ── Left side ─────────────────────────────────────────────────────────────────

const LeftPane = styled.div`
  flex: 0 0 45%;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: transparent;
  font-family: ${FONT};
  color: ${TXT};
  border-right: 0.5px solid ${BDR};
`;

const LeftHeader = styled.div`
  display: flex;
  align-items: center;
  padding: 0 1.2rem;
  height: 44px;
  border-bottom: 0.5px solid ${BDR};
  flex-shrink: 0;
  font-family: ${TITLE};
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
  color: ${TXT};
  gap: 1rem;
`;

const TopContainer = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5px;
  background: ${BDR};
  min-height: 0;
`;

const BottomContainer = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 0.5px;
  background: ${BDR};
  min-height: 0;
`;

const LeftPanel = styled.div`
  background: ${BG};
  padding: 1rem 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  overflow: hidden;
`;

const PanelLabel = styled.div`
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0;
  color: ${LBL};
  border-bottom: 0.5px solid ${BDR};
  padding-bottom: 6px;
  margin-bottom: 2px;
  flex-shrink: 0;
`;

const InfoRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 12px;
  padding: 2px 0;
  span:first-child { color: ${LBL}; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; }
  span:last-child  { color: ${ACT}; font-weight: 400; }
`;

// ── Right side ────────────────────────────────────────────────────────────────

const RightPane = styled.div`
  flex: 0 0 55%;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: transparent;
  font-family: ${FONT};
  color: ${TXT};
`;

const RightHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0 1.2rem;
  height: 44px;
  border-bottom: 0.5px solid ${BDR};
  flex-shrink: 0;
  font-family: ${TITLE};
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
  color: ${TXT};
`;

const RightBody = styled.div`
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
`;

// ── Agent list sidebar ────────────────────────────────────────────────────────

const ListSidebar = styled.div`
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 0.5px solid ${BDR};
  overflow: hidden;
  background: transparent;
`;

const SidebarHeader = styled.div`
  padding: 8px 12px 7px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0;
  color: ${LBL};
  border-bottom: 0.5px solid ${BDR};
  flex-shrink: 0;
`;

const FilterRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 0.5px solid ${BDR};
  flex-shrink: 0;
`;

const FilterChip = styled.button<{ $active: boolean; $color: string }>`
  padding: 3px 10px;
  border-radius: 999px;
  border: 0.5px solid ${p => p.$active ? p.$color : 'rgba(255,255,255,0.14)'};
  background: ${p => p.$active ? `${p.$color}22` : 'transparent'};
  color: ${p => p.$active ? p.$color : LBL};
  font-family: inherit;
  font-size: 11px;
  font-weight: 400;
  cursor: pointer;
  letter-spacing: 0;
  transition: all 0.12s;
  &:hover { border-color: ${p => p.$color}; color: ${p => p.$color}; }
`;

const AgentList = styled.div`
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
  scrollbar-color: ${BDR} transparent;
  padding: 4px 0;
`;

const AgentCard = styled.div<{ $selected: boolean; $color: string; $hovered?: boolean }>`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 6px;
  margin: 0 5px;
  border: 0.5px solid ${p => p.$selected ? p.$color : p.$hovered ? 'rgba(255,255,255,0.18)' : 'transparent'};
  background: ${p => p.$selected ? `${p.$color}22` : p.$hovered ? SURF2 : 'transparent'};
  box-shadow: ${p => p.$selected ? `inset 2px 0 0 ${p.$color}` : 'none'};
  cursor: pointer;
  transition: all 0.12s;
  &:hover {
    background: ${p => p.$selected ? `${p.$color}30` : SURF};
    border-color: ${p => p.$selected ? p.$color : 'rgba(255,255,255,0.1)'};
  }
`;

const AgentDot = styled.div<{ $color: string }>`
  width: 6px; height: 6px; border-radius: 50%;
  background: ${p => p.$color}; flex-shrink: 0;
`;

// ── Detail panel ──────────────────────────────────────────────────────────────

const DetailPane = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  background: transparent;
`;

const DetailScroll = styled.div`
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background: transparent;
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.1) transparent;
`;

// Liquid glass matching the dashboard KPI cards exactly (--glass tokens from
// app/src/index.css): rgba(28,28,30,0.55) fill, 0.10 white border, layered drop
// shadows + inset specular top edge, blur(28px) saturate(1.7), and the same
// border-color lift on hover.
const Block = styled.div`
  background: rgba(28,28,30,0.55);
  border: 0.5px solid rgba(255,255,255,0.10);
  border-radius: var(--r-lg, 16px);
  padding: 1.25rem;
  box-shadow:
    0 8px 30px rgba(0,0,0,0.55),
    0 2px 8px rgba(0,0,0,0.4),
    inset 0 1px 0 rgba(255,255,255,0.12);
  backdrop-filter: blur(28px) saturate(1.7);
  -webkit-backdrop-filter: blur(28px) saturate(1.7);
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  transition: border-color 0.15s;
  &:hover {
    border-color: rgba(255,255,255,0.14);
  }
`;

const BlockTitle = styled.div`
  font-family: ${TITLE};
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
  color: ${TXT2};
  margin-bottom: 4px;
  flex-shrink: 0;
  display: flex;
  align-items: baseline;
`;

const ProfileRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 12px;
  padding: 2px 0;
  span:first-child { color: ${LBL}; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; }
  span:last-child  { color: ${ACT}; font-weight: 400; }
`;

const MoodBar = styled.div<{ $value: number; $color: string }>`
  height: 3px;
  border-radius: 999px;
  background: ${p => p.$color};
  width: ${p => Math.max(2, p.$value * 100)}%;
  transition: width 0.3s ease;
`;

const MoodRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: ${LBL};
  letter-spacing: 0.02em;
  .label { width: 76px; flex-shrink: 0; text-transform: uppercase; }
  .bar-wrap { flex: 1; background: rgba(255,255,255,0.08); border-radius: 999px; overflow: hidden; height: 3px; }
  .val { width: 34px; text-align: right; flex-shrink: 0; color: ${TXT}; }
`;

const ReleaseBtn = styled.button`
  padding: 6px 0;
  border-radius: 999px;
  border: 0.5px solid rgba(255,255,255,0.14);
  background: transparent;
  color: ${LBL};
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  letter-spacing: 0;
  transition: all 0.15s;
  &:hover { border-color: rgba(255,255,255,0.25); color: ${TXT}; }
`;

const SelectBtn = styled.button`
  padding: 7px 18px;
  border-radius: 999px;
  border: 0.5px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.07);
  color: ${LBL};
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
  letter-spacing: 0;
  transition: all 0.15s;
  &:hover { border-color: rgba(255,255,255,0.25); color: ${TXT}; background: rgba(255,255,255,0.1); }
`;

const MapBox = styled.div`
  height: 260px;
  flex-shrink: 0;
  position: relative;
  background: #000;
  border-bottom: 0.5px solid ${BDR};
`;

const MapLabel = styled.div`
  position: absolute;
  top: 8px;
  left: 10px;
  z-index: 10;
  font-family: ${FONT};
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0;
  color: ${TXT};
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 3px 8px;
  border-radius: 999px;
  pointer-events: none;
`;

const ConvList = styled.div`
  overflow-y: auto;
  max-height: 200px;
  padding: 4px 0;
  scrollbar-width: thin;
  scrollbar-color: ${BDR} transparent;
`;

const ConvLine = styled.div<{ $isSelf: boolean }>`
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: ${p => p.$isSelf ? 'flex-end' : 'flex-start'};
  margin-bottom: 6px;
`;

const ConvBubble = styled.div<{ $isSelf: boolean }>`
  background: ${p => p.$isSelf ? SURF2 : SURF};
  border: 0.5px solid ${BDR};
  border-radius: 12px;
  padding: 6px 11px;
  font-size: 12px;
  color: ${TXT};
  max-width: 90%;
  line-height: 1.55;
`;

const ConvTs = styled.div`
  font-size: 11px;
  color: ${LBL};
  letter-spacing: 0.06em;
`;

// ── Follow-map (close-up DeckGL, no Mapbox token) ────────────────────────────

const ESRI_SATELLITE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const ESRI_LABELS    = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}';

function makeTile(id: string, url: string) {
  return new TileLayer({
    id,
    data: url,
    minZoom: 0,
    maxZoom: 19,
    tileSize: 256,
    renderSubLayers: (props: any) => {
      const { bbox: { west, south, east, north } } = props.tile;
      return new BitmapLayer(props, { data: undefined, image: props.data, bounds: [west, south, east, north] });
    },
  });
}

function FollowMap() {
  const { state } = useSharedState();
  const t = state.currentTimeMin;

  const agent = useMemo(() =>
    state.followedAgentId ? state.agents.find(a => a.id === state.followedAgentId) ?? null : null,
  [state.followedAgentId, state.agents]);

  const position = useMemo((): [number, number] | null => {
    if (!agent) return null;
    let lo = 0, hi = agent.ts.length - 1, idx = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (agent.ts[mid] <= t) { idx = mid; lo = mid + 1; } else hi = mid - 1;
    }
    if (idx < 0 || idx >= agent.path.length) return null;
    return agent.path[idx] as [number, number];
  }, [agent, t]);

  const [viewState, setViewState] = useState<MapViewState>({
    longitude: 1.601, latitude: 42.546, zoom: 17, pitch: 0, bearing: 0,
  });

  useEffect(() => {
    if (!position) return;
    setViewState(v => ({ ...v, longitude: position[0], latitude: position[1], transitionDuration: 80 }));
  }, [position?.[0], position?.[1]]);

  const layers = useMemo(() => {
    const base = [makeTile('sat', ESRI_SATELLITE), makeTile('lbl', ESRI_LABELS)];
    if (!agent?.path?.length) return base;

    const pathLayer = new PathLayer({
      id: 'agent-path',
      data: [{ path: agent.path }],
      getPath: (d: any) => d.path,
      getColor: [...agent.color, 180] as [number, number, number, number],
      getWidth: 3,
      widthMinPixels: 2,
      widthMaxPixels: 5,
      rounded: true,
    });

    const dotLayer = position
      ? new ScatterplotLayer({
          id: 'agent-dot',
          data: [{ position }],
          getPosition: (d: any) => d.position,
          getFillColor: [255, 255, 255, 240],
          getLineColor: [0, 0, 0, 200],
          getLineWidth: 2,
          getRadius: 8,
          radiusMinPixels: 6,
          radiusMaxPixels: 12,
          stroked: true,
        })
      : null;

    return dotLayer ? [...base, pathLayer, dotLayer] : [...base, pathLayer];
  }, [agent, position]);

  if (!state.followedAgentId || !agent) return null;

  const eColor = EKMAN_COLORS[agent.emotion] ?? '#9ca3af';
  const hh = Math.floor(t / 60).toString().padStart(2, '0');
  const mm = Math.floor(t % 60).toString().padStart(2, '0');

  return (
    <MapBox>
      <MapLabel style={{ color: eColor }}>
        ◉ {agent.id} · {agent.emotion} · {hh}:{mm}
      </MapLabel>
      <DeckGLAny
        viewState={viewState}
        controller={false}
        onViewStateChange={({ viewState: vs }: { viewState: MapViewState }) => setViewState(vs)}
        layers={layers}
        style={{ position: 'absolute', inset: 0 }}
      />
    </MapBox>
  );
}

// ── Left panel ────────────────────────────────────────────────────────────────

// ── LEFT: who they are (agent selector + profile) ───────────────────────────

function AgentProfilePane() {
  const { state, setFollowedAgent } = useSharedState();
  const agents = state.agents;

  const [encoderHoverIdx, setEncoderHoverIdx] = useState(-1);
  const agentListRef = useRef<HTMLDivElement>(null);
  const handleFollow = (id: string) => setFollowedAgent(state.followedAgentId === id ? null : id);

  // sync hover/select coming from the main-app map iframe
  const msgHandlerRef = useRef<((e: MessageEvent) => void) | null>(null);
  msgHandlerRef.current = (e: MessageEvent) => {
    if (!agents.length) return;
    const wrap = (n: number) => ((n % agents.length) + agents.length) % agents.length;
    if (e.data?.type === 'AGENT_HOVER') setEncoderHoverIdx(wrap(e.data.pos as number));
    else if (e.data?.type === 'AGENT_SELECT') { setEncoderHoverIdx(-1); handleFollow(agents[wrap(e.data.pos as number)].id); }
  };
  useEffect(() => {
    const handler = (e: MessageEvent) => msgHandlerRef.current?.(e);
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);
  useEffect(() => {
    if (encoderHoverIdx < 0 || !agentListRef.current) return;
    const cards = agentListRef.current.querySelectorAll('[data-agent-card]');
    (cards[encoderHoverIdx] as HTMLElement | undefined)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [encoderHoverIdx]);

  const f = useMemo(() =>
    state.followedAgentId ? agents.find(a => a.id === state.followedAgentId) ?? null : null,
  [state.followedAgentId, agents]);
  const profile = f ? state.profiles?.get(f.id) : null;
  const eColor = f ? (EKMAN_COLORS[f.emotion] || '#9ca3af') : ACT;
  const pickRandom = () => { if (agents.length) setFollowedAgent(agents[Math.floor(Math.random() * agents.length)].id); };

  return (
    <LeftPane>
      <LeftHeader>
        Agent Profile
        {f && <span style={{ color: eColor, fontWeight: 500 }}>→ {getFakeName(f.id)}</span>}
        <span style={{ marginLeft: 'auto', color: LBL, fontSize: 11 }}>{agents.length.toLocaleString()} agents</span>
      </LeftHeader>

      <RightBody>
        <ListSidebar>
          <SidebarHeader>Select Agent</SidebarHeader>
          {!agents.length ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: LBL, fontSize: '11px', padding: '8px' }}>Loading…</div>
          ) : (
            <AgentList ref={agentListRef}>
              {agents.slice(0, 300).map((agent, listIdx) => {
                const aColor   = EKMAN_COLORS[agent.emotion] ?? '#9ca3af';
                const selected = state.followedAgentId === agent.id;
                const encHover = encoderHoverIdx === listIdx;
                return (
                  <AgentCard key={agent.id} $selected={selected} $color={aColor} $hovered={encHover} data-agent-card onClick={() => handleFollow(agent.id)}>
                    <AgentDot $color={aColor} />
                    <span style={{ flex: 1, fontSize: '11px', color: selected ? '#e5e7eb' : '#9ca3af', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{getFakeName(agent.id)}</span>
                    <span style={{ fontSize: '10px', color: aColor, flexShrink: 0 }}>{agent.emotion.slice(0, 3)}</span>
                  </AgentCard>
                );
              })}
            </AgentList>
          )}
          <div style={{ padding: '8px 10px', borderTop: `0.5px solid ${BDR}`, flexShrink: 0 }}>
            <SelectBtn onClick={pickRandom} style={{ width: '100%' }}>Random agent</SelectBtn>
          </div>
        </ListSidebar>

        <DetailPane>
          <DetailScroll>
            {!f ? (
              <Block><PopulationDashboards agg={state.aggregates} /></Block>
            ) : (
              <Block>
                <BlockTitle>
                  {getFakeName(f.id)}
                  <span style={{ marginLeft: 'auto', fontSize: 10, color: LBL, fontWeight: 400 }}>{f.id}</span>
                </BlockTitle>
                {state.profilesLoading && !state.profiles
                  ? <div style={{ color: LBL, fontSize: 11, padding: 12 }}>Loading profile…</div>
                  : <AgentProfile profile={profile} accent={eColor} />}
                <ReleaseBtn onClick={() => setFollowedAgent(null)}>Release agent</ReleaseBtn>
              </Block>
            )}
          </DetailScroll>
        </DetailPane>
      </RightBody>
    </LeftPane>
  );
}

// ── Right panel ───────────────────────────────────────────────────────────────

// ── RIGHT: what they're living (map + journey + emotion + conversations) ────

function AgentLifePane() {
  const { state, setFollowedAgent } = useSharedState();
  const t = state.currentTimeMin;

  const f = useMemo(() =>
    state.followedAgentId ? state.agents.find(a => a.id === state.followedAgentId) ?? null : null,
  [state.followedAgentId, state.agents]);
  const profile = f ? state.profiles?.get(f.id) : null;
  const emotion = f?.emotion ?? null;
  const eColor  = emotion ? (EKMAN_COLORS[emotion] || '#9ca3af') : '#9ca3af';

  // Population emotion mapping for the existing 7-shape Ekman cluster viz.
  const habmAgents = useMemo(() =>
    state.agents.slice(0, 500).map(a => ({
      id: a.id,
      emotions: {
        insecure: a.emotion === 'CONTEMPT'  ? 1 : 0,
        energize: a.emotion === 'ENJOYMENT' || a.emotion === 'SURPRISE' ? 1 : 0,
        threaten: a.emotion === 'ANGER'     || a.emotion === 'FEAR'     ? 1 : 0,
        stress:   a.emotion === 'DISGUST'   ? 1 : 0,
        calm:     a.emotion === 'SADNESS'   ? 1 : 0,
      },
    })),
  [state.agents]);

  const pathProgress = useMemo(() => {
    if (!f) return 0;
    const s = f.ts[0] ?? 0, e = f.ts[f.ts.length - 1] ?? 1440;
    return Math.min(1, Math.max(0, (t - s) / (e - s || 1)));
  }, [f, t]);
  const timeStr = `${Math.floor(t / 60).toString().padStart(2, '0')}:${Math.floor(t % 60).toString().padStart(2, '0')}`;

  return (
    <RightPane>
      <RightHeader>
        Daily life &amp; state
        {f
          ? <span style={{ marginLeft: 'auto', color: eColor, fontWeight: 500 }}>{emotion} · {timeStr}</span>
          : <span style={{ marginLeft: 'auto', color: LBL, fontSize: 11 }}>{timeStr}</span>}
      </RightHeader>

      {!f ? (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: LBL, fontSize: 12, textAlign: 'center', padding: 20 }}>
          <div style={{ fontSize: '1.4rem', opacity: 0.15 }}>◎</div>
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)' }}>No agent selected</div>
          <div style={{ maxWidth: 220, lineHeight: 1.7 }}>Select an agent on the left to follow their day, conversations and emotional state.</div>
        </div>
      ) : (
        <DetailScroll>
          {/* Movement map */}
          <FollowMap />

          {/* Day progress */}
          <Block>
            <div style={{ fontSize: 10, color: LBL, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 4 }}>Day progress · {timeStr}</div>
            <div style={{ height: 3, borderRadius: 999, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{ height: '100%', borderRadius: 999, background: eColor, width: `${(pathProgress * 100).toFixed(1)}%`, transition: 'width 0.3s ease' }} />
            </div>
          </Block>

          {/* Daily journey */}
          <Block><AgentJourney profile={profile} t={t} /></Block>

          {/* Ekman 3D emotion bubble + felt state */}
          <Block>
            <BlockTitle>Emotional state <span style={{ marginLeft: 'auto', color: eColor, fontWeight: 700 }}>{emotion}</span></BlockTitle>
            <div style={{ position: 'relative', height: 280, borderRadius: 12, overflow: 'hidden', marginBottom: 10 }}>
              <HABMSentiments agents={habmAgents} />
            </div>
            <EmotionState profile={profile} emotion={emotion} emotionColor={eColor} />
          </Block>

          {/* Conversations */}
          <Block>
            <BlockTitle>Conversations</BlockTitle>
            <div style={{ minHeight: 160 }}><RealTimeChat /></div>
          </Block>

          <Block>
            <ReleaseBtn onClick={() => setFollowedAgent(null)}>Release agent</ReleaseBtn>
          </Block>
        </DetailScroll>
      )}
    </RightPane>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function AgentAnalyticsView() {
  const { state, setFollowedAgent, loadProfiles } = useSharedState();

  // Lazily pull the rich profiles when this tab mounts
  useEffect(() => { loadProfiles(); }, [loadProfiles]);

  // Auto-follow a random agent when data arrives
  useEffect(() => {
    if (!state.agents.length || state.followedAgentId) return;
    setFollowedAgent(state.agents[Math.floor(Math.random() * state.agents.length)].id);
  }, [state.agents]);

  return (
    <Wrapper>
      <AgentProfilePane />
      <AgentLifePane />
    </Wrapper>
  );
}
