import { useMemo, useRef, useEffect, useState } from 'react';
import styled from 'styled-components';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
  LineChart, Line, CartesianGrid,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  AreaChart, Area,
} from 'recharts';
import { useSharedState } from '../services/SharedStateContext';
import {
  SCENARIO_LABELS, SCENARIO_COLORS, getScenarioYear, getScenarioTimeseries,
  getYearRange, type ScenarioId, type MapLayerId,
} from '../services/ScenarioDataService';

// ── Constants ─────────────────────────────────────────────────────────────────

const EKMAN_COLORS: Record<string, string> = {
  ANGER:    '#ef4444',
  CONTEMPT: '#a855f7',
  DISGUST:  '#22c55e',
  ENJOYMENT:'#eab308',
  FEAR:     '#f97316',
  SADNESS:  '#3b82f6',
  SURPRISE: '#ec4899',
};

const EKMAN_ORDER = ['ANGER','CONTEMPT','DISGUST','ENJOYMENT','FEAR','SADNESS','SURPRISE'];

const COLOR_TO_EKMAN: Record<string, string> = {
  red:    'ANGER',
  purple: 'CONTEMPT',
  green:  'ENJOYMENT',
  blue:   'SURPRISE',
  orange: 'FEAR',
  yellow: 'ENJOYMENT',
};

const TYPE_COLORS: Record<string, string> = {
  blue:   '#3b82f6',
  red:    '#ef4444',
  purple: '#a855f7',
  orange: '#f97316',
  Adult:  '#10b981',
  Carlos: '#10b981',
  Elena:  '#60a5fa',
};

const AGENT_TYPES = ['blue', 'red', 'purple', 'orange', 'Adult'];
const EKMAN_KEYS  = EKMAN_ORDER;

// ── Styled components ─────────────────────────────────────────────────────────

const Page = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #080810;
  color: #e5e7eb;
  font-family: 'IBM Plex Mono', 'Courier New', monospace;
  overflow: hidden;
`;

const TopBar = styled.div`
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0 1.5rem;
  height: 52px;
  border-bottom: 1px solid #1f2937;
  flex-shrink: 0;
`;

const Title = styled.h1`
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #6b7280;
  margin: 0;
  white-space: nowrap;
`;

const StatBadge = styled.div<{ $accent?: string }>`
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex-shrink: 0;
  span:first-child { font-size: 0.55rem; color: #4b5563; letter-spacing: 0.08em; }
  span:last-child  { font-size: 0.95rem; font-weight: 700; color: ${p => p.$accent || '#e5e7eb'}; }
`;

const Sep = styled.div`
  width: 1px; height: 24px;
  background: #1f2937;
  flex-shrink: 0;
`;

const PlayBtn = styled.button<{ $playing: boolean }>`
  margin-left: auto;
  padding: 6px 20px;
  border-radius: 6px;
  border: 1px solid ${p => p.$playing ? '#f87171' : '#4ade80'};
  background: ${p => p.$playing ? '#f8717115' : '#4ade8015'};
  color: ${p => p.$playing ? '#f87171' : '#4ade80'};
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.06em;
  white-space: nowrap;
`;

// ── Tab bar ───────────────────────────────────────────────────────────────────

const TabBar = styled.div`
  display: flex;
  gap: 0;
  padding: 0 1.5rem;
  border-bottom: 1px solid #1f2937;
  flex-shrink: 0;
`;

const Tab = styled.button<{ $active: boolean }>`
  padding: 8px 20px;
  border: none;
  border-bottom: 2px solid ${p => p.$active ? '#646cff' : 'transparent'};
  background: transparent;
  color: ${p => p.$active ? '#e5e7eb' : '#4b5563'};
  font-family: inherit;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
  &:hover { color: #9ca3af; }
`;

// ── Grid panels ───────────────────────────────────────────────────────────────

const MainGrid = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: 200px 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 1px;
  background: #111827;
  overflow: hidden;
  min-height: 0;
`;

const Panel = styled.div<{ $span?: string }>`
  background: #080810;
  padding: 1rem 1.2rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  ${p => p.$span ? `grid-row: ${p.$span};` : ''}
`;

const PanelTitle = styled.div`
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #374151;
  text-transform: uppercase;
  border-bottom: 1px solid #111827;
  padding-bottom: 5px;
  flex-shrink: 0;
`;

const FilterChip = styled.button<{ $active: boolean; $color: string }>`
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid ${p => p.$active ? p.$color : '#374151'};
  background: ${p => p.$active ? `${p.$color}20` : 'transparent'};
  color: ${p => p.$active ? p.$color : '#6b7280'};
  font-family: inherit;
  font-size: 0.6rem;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
  transition: all 0.12s;
  &:hover { border-color: ${p => p.$color}; color: ${p => p.$color}; }
`;

const ClearBtn = styled.button`
  width: 100%;
  padding: 5px 0;
  border-radius: 5px;
  border: 1px solid #374151;
  background: transparent;
  color: #6b7280;
  font-family: inherit;
  font-size: 0.6rem;
  cursor: pointer;
  letter-spacing: 0.06em;
  &:hover { border-color: #9ca3af; color: #9ca3af; }
`;

// ── Scenario bar ──────────────────────────────────────────────────────────────

const ScenarioBar = styled.div`
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 5px 1.5rem;
  border-bottom: 1px solid #1f2937;
  background: #080810;
  flex-shrink: 0;
`;

const ScenarioBtn = styled.button<{ $active: boolean; $color: string }>`
  padding: 3px 13px;
  border-radius: 4px;
  border: 1px solid ${p => p.$active ? p.$color : '#374151'};
  background: ${p => p.$active ? `${p.$color}22` : 'transparent'};
  color: ${p => p.$active ? p.$color : '#6b7280'};
  font-family: inherit;
  font-size: 0.58rem;
  font-weight: 700;
  cursor: pointer;
  letter-spacing: 0.09em;
  transition: all 0.12s;
  &:hover { border-color: ${p => p.$color}; color: ${p => p.$color}; }
`;

const YearSlider = styled.input`
  flex: 1;
  max-width: 220px;
  accent-color: #646cff;
  cursor: pointer;
  height: 3px;
`;

const YearLabel = styled.span`
  font-size: 0.95rem;
  font-weight: 700;
  color: #a3e635;
  letter-spacing: 0.06em;
  min-width: 3rem;
  text-align: center;
`;

// ── Scenario KPI cards ────────────────────────────────────────────────────────

const KPIGrid = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-template-rows: 1fr 1fr;
  gap: 1px;
  background: #111827;
  overflow: hidden;
  min-height: 0;
`;

const KPICard = styled.div<{ $accent?: string }>`
  background: #080810;
  padding: 1rem 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  overflow: hidden;
`;

const KPILabel = styled.div`
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #374151;
  text-transform: uppercase;
`;

const KPIValue = styled.div<{ $accent?: string }>`
  font-size: 1.4rem;
  font-weight: 700;
  color: ${p => p.$accent || '#e5e7eb'};
  letter-spacing: 0.02em;
  line-height: 1.1;
`;

const KPIUnit = styled.span`
  font-size: 0.65rem;
  color: #6b7280;
  margin-left: 3px;
  font-weight: 400;
`;

const KPITrend = styled.div<{ $up: boolean | null }>`
  font-size: 0.6rem;
  font-weight: 600;
  color: ${p => p.$up === null ? '#4b5563' : p.$up ? '#4ade80' : '#f87171'};
  letter-spacing: 0.04em;
`;

const AgentCard = styled.div<{ $selected: boolean; $color: string }>`
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 7px;
  border-radius: 5px;
  border: 1px solid ${p => p.$selected ? p.$color : 'transparent'};
  background: ${p => p.$selected ? `${p.$color}12` : 'transparent'};
  cursor: pointer;
  transition: all 0.12s;
  &:hover { background: ${p => p.$color}15; border-color: ${p => p.$color}55; }
`;

const AgentDot = styled.div<{ $color: string }>`
  width: 7px; height: 7px; border-radius: 50%;
  background: ${p => p.$color}; flex-shrink: 0;
`;

const AgentList = styled.div`
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1px;
  scrollbar-width: thin;
  scrollbar-color: #374151 transparent;
`;

// ── Agent Analytics tab styles ────────────────────────────────────────────────

const AnalyticsLayout = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: 260px 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 1px;
  background: #111827;
  overflow: hidden;
  min-height: 0;
`;

const AgentProfileCard = styled.div`
  background: #080810;
  padding: 1.2rem;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
`;

const ProfileRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.62rem;
  span:first-child { color: #4b5563; }
  span:last-child  { color: #e5e7eb; font-weight: 600; }
`;

const MoodBar = styled.div<{ $value: number; $color: string }>`
  height: 6px;
  border-radius: 3px;
  background: ${p => p.$color};
  width: ${p => Math.max(2, p.$value * 100)}%;
  transition: width 0.3s ease;
`;

const MoodRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.58rem;
  color: #6b7280;
  .label { width: 70px; flex-shrink: 0; }
  .bar-wrap { flex: 1; background: #111827; border-radius: 3px; overflow: hidden; height: 6px; }
  .val { width: 32px; text-align: right; flex-shrink: 0; color: #9ca3af; }
`;

const ConvLine = styled.div<{ $isSelf: boolean }>`
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: ${p => p.$isSelf ? 'flex-end' : 'flex-start'};
  margin-bottom: 6px;
`;

const ConvBubble = styled.div<{ $isSelf: boolean }>`
  background: ${p => p.$isSelf ? '#1d4ed820' : '#1f2937'};
  border: 1px solid ${p => p.$isSelf ? '#3b82f640' : '#374151'};
  border-radius: 8px;
  padding: 5px 10px;
  font-size: 0.62rem;
  color: #e5e7eb;
  max-width: 85%;
  line-height: 1.5;
`;

const ConvTs = styled.div`
  font-size: 0.5rem;
  color: #4b5563;
  letter-spacing: 0.06em;
`;

const ConvList = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
  scrollbar-width: thin;
  scrollbar-color: #374151 transparent;
`;

const EmptyState = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #374151;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-align: center;
`;

const SelectBtn = styled.button`
  padding: 8px 20px;
  border-radius: 6px;
  border: 1px solid #374151;
  background: transparent;
  color: #6b7280;
  font-family: inherit;
  font-size: 0.65rem;
  cursor: pointer;
  letter-spacing: 0.06em;
  &:hover { border-color: #646cff; color: #818cf8; }
`;

// ── Recharts tooltip ──────────────────────────────────────────────────────────

const CTip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(8,8,16,0.95)', border: '1px solid #374151',
      borderRadius: 6, padding: '6px 10px',
      fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: '#e5e7eb',
    }}>
      <div style={{ color: payload[0]?.color, marginBottom: 2, fontWeight: 700 }}>{label}</div>
      <div>{(payload[0]?.value ?? 0).toFixed(1)}%  ·  {payload[0]?.payload?.count ?? 0} agents</div>
    </div>
  );
};

// ── Scenario KPI helpers ──────────────────────────────────────────────────────

function fmt(v: number | undefined, decimals = 0): string {
  if (v === undefined || isNaN(v)) return '—';
  return v.toLocaleString('en-US', { maximumFractionDigits: decimals });
}

function pct(v: number | undefined): string {
  if (v === undefined) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

interface KPICardProps {
  label: string;
  value: string;
  unit?: string;
  accent?: string;
  timeseries: number[];
  inverted?: boolean; // true = lower is better (green when falling)
}

function KPICardItem({ label, value, unit, accent, timeseries, inverted }: KPICardProps) {
  const trend = useMemo(() => {
    if (timeseries.length < 2) return null;
    const last = timeseries[timeseries.length - 1];
    const prev = timeseries[timeseries.length - 2];
    if (!prev) return null;
    return ((last - prev) / Math.abs(prev)) * 100;
  }, [timeseries]);

  const sparkData = timeseries.map((v, i) => ({ i, v }));
  const isUp = trend === null ? null : inverted ? trend < 0 : trend > 0;

  return (
    <KPICard $accent={accent}>
      <KPILabel>{label}</KPILabel>
      <KPIValue $accent={accent}>
        {value}
        {unit && <KPIUnit>{unit}</KPIUnit>}
      </KPIValue>
      {trend !== null && (
        <KPITrend $up={isUp}>
          {trend > 0 ? '▲' : '▼'} {Math.abs(trend).toFixed(1)}% YoY
        </KPITrend>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparkData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={accent || '#646cff'} stopOpacity={0.3} />
                <stop offset="95%" stopColor={accent || '#646cff'} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="v" stroke={accent || '#646cff'}
              fill={`url(#grad-${label})`} strokeWidth={1.5} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </KPICard>
  );
}

// ── Scenario Main Tab ─────────────────────────────────────────────────────────

function ScenarioMainTab() {
  const { state } = useSharedState();
  const { selectedScenario, selectedYear } = state;
  const scenarioColor = SCENARIO_COLORS[selectedScenario];
  const yearData = getScenarioYear(selectedScenario, selectedYear);
  const timeseries = getScenarioTimeseries(selectedScenario);

  function ts(key: keyof typeof timeseries[0]) {
    return timeseries.slice(0, timeseries.findIndex(d => d.Year === selectedYear) + 1).map(d => d[key] as number);
  }

  return (
    <KPIGrid>
      <KPICardItem
        label="Population"
        value={fmt(yearData?.Pop)}
        unit="people"
        accent={scenarioColor}
        timeseries={ts('Pop')}
      />
      <KPICardItem
        label="GDP per Capita"
        value={fmt(yearData?.GDPpc)}
        unit="€"
        accent="#a3e635"
        timeseries={ts('GDPpc')}
      />
      <KPICardItem
        label="Tourism Arrivals"
        value={yearData ? `${(yearData.Tour / 1_000_000).toFixed(2)}M` : '—'}
        accent="#f97316"
        timeseries={ts('Tour')}
      />
      <KPICardItem
        label="Employment Rate"
        value={yearData ? pct(yearData.Emp) : '—'}
        accent="#4ade80"
        timeseries={ts('Emp')}
      />
      <KPICardItem
        label="CO₂ per Capita"
        value={fmt(yearData?.CO2pc, 2)}
        unit="t/yr"
        accent="#f87171"
        inverted
        timeseries={ts('CO2pc')}
      />
      <KPICardItem
        label="Renewables"
        value={yearData ? pct(yearData.Ren) : '—'}
        accent="#34d399"
        timeseries={ts('Ren')}
      />
      <KPICardItem
        label="Housing Price"
        value={fmt(yearData?.HPrice)}
        unit="€/m²"
        accent="#fbbf24"
        inverted
        timeseries={ts('HPrice')}
      />
      <KPICardItem
        label="Life Expectancy"
        value={fmt(yearData?.LE, 1)}
        unit="yr"
        accent="#60a5fa"
        timeseries={ts('LE')}
      />
    </KPIGrid>
  );
}

// ── Scenario Infrastructure Tab ───────────────────────────────────────────────

function ScenarioInfraTab() {
  const { state } = useSharedState();
  const { selectedScenario, selectedYear } = state;
  const scenarioColor = SCENARIO_COLORS[selectedScenario];
  const yearData = getScenarioYear(selectedScenario, selectedYear);
  const timeseries = getScenarioTimeseries(selectedScenario);

  function ts(key: keyof typeof timeseries[0]) {
    return timeseries.slice(0, timeseries.findIndex(d => d.Year === selectedYear) + 1).map(d => d[key] as number);
  }

  return (
    <KPIGrid>
      <KPICardItem
        label="Electricity Capacity"
        value={yearData ? `${(yearData.ElectricityCapacity_kW / 1000).toFixed(1)}k` : '—'}
        unit="kW"
        accent={scenarioColor}
        timeseries={ts('ElectricityCapacity_kW')}
      />
      <KPICardItem
        label="Renewable Power"
        value={yearData ? `${(yearData.ElectricityRenewable_kW / 1000).toFixed(1)}k` : '—'}
        unit="kW"
        accent="#34d399"
        timeseries={ts('ElectricityRenewable_kW')}
      />
      <KPICardItem
        label="Fossil Power"
        value={yearData ? `${(yearData.ElectricityFossil_kW / 1000).toFixed(1)}k` : '—'}
        unit="kW"
        accent="#f87171"
        inverted
        timeseries={ts('ElectricityFossil_kW')}
      />
      <KPICardItem
        label="Electricity Demand"
        value={yearData ? `${(yearData.ElectricityDemand_kWh_year / 1_000_000).toFixed(0)}M` : '—'}
        unit="kWh/yr"
        accent="#fbbf24"
        timeseries={ts('ElectricityDemand_kWh_year')}
      />
      <KPICardItem
        label="Water Security Index"
        value={yearData ? pct(yearData.WaterSecurityIndex) : '—'}
        accent="#60a5fa"
        timeseries={ts('WaterSecurityIndex')}
      />
      <KPICardItem
        label="Hospital Beds Required"
        value={fmt(yearData?.HospitalRequiredBeds, 0)}
        unit="beds"
        accent="#ec4899"
        timeseries={ts('HospitalRequiredBeds')}
      />
      <KPICardItem
        label="School Students"
        value={fmt(yearData?.SchoolStudents, 0)}
        unit="students"
        accent="#a78bfa"
        timeseries={ts('SchoolStudents')}
      />
      <KPICardItem
        label="Road Network"
        value={fmt(yearData?.RoadTotalLength_km, 0)}
        unit="km"
        accent="#9ca3af"
        timeseries={ts('RoadTotalLength_km')}
      />
    </KPIGrid>
  );
}

// ── KPI Grid Tab ──────────────────────────────────────────────────────────────

function KPIGridTab() {
  const {
    state,
    setFollowedAgent, setAgentTypeFilter, setEmotionFilter,
  } = useSharedState();

  const emotionHistoryRef = useRef<Array<Record<string, number>>>([]);
  const [trendData, setTrendData]   = useState<Array<Record<string, number>>>([]);

  const agents = state.simulationData?.agents ?? [];
  const step   = state.currentStep;

  const emotionData = useMemo(() => {
    if (!agents.length) return EKMAN_KEYS.map(k => ({ name: k, value: 0, count: 0 }));
    const counts: Record<string, number> = Object.fromEntries(EKMAN_KEYS.map(k => [k, 0]));
    agents.forEach(agent => {
      const color = agent.emotion[Math.min(step, agent.emotion.length - 1)] ?? 'green';
      counts[COLOR_TO_EKMAN[color] ?? 'ENJOYMENT']++;
    });
    const total = agents.length || 1;
    return EKMAN_KEYS.map(k => ({ name: k, value: counts[k] / total, count: counts[k] }));
  }, [agents, step]);

  const typeData = useMemo(() => {
    if (!agents.length) return [];
    const counts: Record<string, number> = {};
    agents.forEach(a => { counts[a.type] = (counts[a.type] || 0) + 1; });
    return Object.entries(counts).map(([name, value]) => ({
      name, value, color: TYPE_COLORS[name] || '#9ca3af',
    }));
  }, [agents]);

  const visibleAgents = useMemo(() => agents.filter(a => {
    if (state.selectedAgentType && a.type !== state.selectedAgentType) return false;
    if (state.selectedEmotionFilter) {
      const ekman = COLOR_TO_EKMAN[a.emotion[Math.min(step, a.emotion.length-1)] ?? 'green'] ?? 'ENJOYMENT';
      if (ekman !== state.selectedEmotionFilter) return false;
    }
    return true;
  }), [agents, step, state.selectedAgentType, state.selectedEmotionFilter]);

  useEffect(() => {
    const snap: Record<string,number> = { step };
    EKMAN_KEYS.forEach(k => {
      snap[k] = +((emotionData.find(e => e.name === k)?.value ?? 0) * 100).toFixed(1);
    });
    emotionHistoryRef.current = [...emotionHistoryRef.current.slice(-29), snap];
    setTrendData([...emotionHistoryRef.current]);
  }, [step]);

  const hasFilter = !!(state.selectedAgentType || state.selectedEmotionFilter);

  return (
    <MainGrid>
      {/* ── Filter sidebar (spans both rows) ─────────────────────────────── */}
      <Panel $span="1 / span 2" style={{ borderRight: '1px solid #111827' }}>
        <PanelTitle>Agent Type</PanelTitle>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {AGENT_TYPES.map(t => (
            <FilterChip
              key={t} $active={state.selectedAgentType === t}
              $color={TYPE_COLORS[t] || '#9ca3af'}
              onClick={() => setAgentTypeFilter(state.selectedAgentType === t ? null : t)}
            >{t}</FilterChip>
          ))}
        </div>

        <PanelTitle style={{ marginTop: 6 }}>Emotion Filter</PanelTitle>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {EKMAN_KEYS.map(e => (
            <FilterChip
              key={e} $active={state.selectedEmotionFilter === e}
              $color={EKMAN_COLORS[e]}
              onClick={() => setEmotionFilter(state.selectedEmotionFilter === e ? null : e)}
            >{e}</FilterChip>
          ))}
        </div>

        {hasFilter && (
          <ClearBtn style={{ marginTop: 6 }}
            onClick={() => { setAgentTypeFilter(null); setEmotionFilter(null); }}
          >
            CLEAR FILTERS
          </ClearBtn>
        )}

        <div style={{ marginTop: 'auto', fontSize: '0.58rem', color: '#374151', lineHeight: 1.8 }}>
          <div>TOTAL&nbsp;&nbsp;&nbsp;<span style={{ color: '#9ca3af' }}>{agents.length}</span></div>
          {hasFilter && <div>VISIBLE&nbsp;<span style={{ color: '#facc15' }}>{visibleAgents.length}</span></div>}
          <div>STEP&nbsp;&nbsp;&nbsp;&nbsp;<span style={{ color: '#a3e635' }}>{step}</span></div>
        </div>
      </Panel>

      {/* ── Emotion distribution ──────────────────────────────────────────── */}
      <Panel>
        <PanelTitle>Emotion Distribution — Step {step}</PanelTitle>
        <div style={{ flex: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={emotionData} margin={{ top: 4, right: 8, bottom: 20, left: -10 }}>
              <XAxis dataKey="name" tick={{ fontSize: 8, fill: '#6b7280', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fontSize: 8, fill: '#6b7280', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
              <Tooltip content={<CTip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Bar dataKey="value" radius={[3,3,0,0]} cursor="pointer"
                onClick={(d: any) => setEmotionFilter(state.selectedEmotionFilter === d.name ? null : d.name)}
              >
                {emotionData.map(entry => (
                  <Cell key={entry.name} fill={EKMAN_COLORS[entry.name]}
                    opacity={state.selectedEmotionFilter && state.selectedEmotionFilter !== entry.name ? 0.2 : 1}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* ── Agent type donut ──────────────────────────────────────────────── */}
      <Panel>
        <PanelTitle>Agent Type Breakdown</PanelTitle>
        <div style={{ flex: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={typeData} dataKey="value" nameKey="name"
                innerRadius="42%" outerRadius="68%"
                paddingAngle={2} cursor="pointer"
                onClick={(d: any) => setAgentTypeFilter(state.selectedAgentType === d.name ? null : d.name)}
              >
                {typeData.map(entry => (
                  <Cell key={entry.name} fill={entry.color}
                    opacity={state.selectedAgentType && state.selectedAgentType !== entry.name ? 0.2 : 1}
                  />
                ))}
              </Pie>
              <Legend formatter={(v: string) => <span style={{ fontSize: 9, color: '#9ca3af', fontFamily: 'IBM Plex Mono' }}>{v}</span>} />
              <Tooltip formatter={(v: number) => [`${v} agents`, '']}
                contentStyle={{ background: '#080810', border: '1px solid #374151', borderRadius: 6, fontFamily: 'IBM Plex Mono', fontSize: 11 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* ── Emotion trend ─────────────────────────────────────────────────── */}
      <Panel>
        <PanelTitle>Emotion Trend — Last 30 Steps</PanelTitle>
        <div style={{ flex: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData} margin={{ top: 4, right: 8, bottom: 4, left: -10 }}>
              <CartesianGrid strokeDasharray="2 4" stroke="#1f2937" />
              <XAxis dataKey="step" tick={{ fontSize: 8, fill: '#6b7280', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#6b7280', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: '#080810', border: '1px solid #374151', borderRadius: 6, fontFamily: 'IBM Plex Mono', fontSize: 10 }} />
              {EKMAN_KEYS.filter(k => !state.selectedEmotionFilter || k === state.selectedEmotionFilter).map(k => (
                <Line key={k} type="monotone" dataKey={k} stroke={EKMAN_COLORS[k]}
                  dot={false} strokeWidth={1.5}
                  opacity={state.selectedEmotionFilter && k !== state.selectedEmotionFilter ? 0.15 : 1}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* ── Agent roster ──────────────────────────────────────────────────── */}
      <Panel>
        <PanelTitle>
          Agent Roster &nbsp;
          <span style={{ color: '#6b7280', fontWeight: 400 }}>{visibleAgents.length} shown</span>
        </PanelTitle>
        <AgentList>
          {visibleAgents.slice(0, 120).map(agent => {
            const emotion  = agent.emotion[Math.min(step, agent.emotion.length-1)] ?? 'green';
            const ekman    = COLOR_TO_EKMAN[emotion] ?? 'ENJOYMENT';
            const tColor   = TYPE_COLORS[agent.type] || '#9ca3af';
            const selected = state.followedAgent?.agentId === agent.agent_id;
            return (
              <AgentCard key={agent.agent_id} $selected={selected} $color={tColor}
                onClick={() => {
                  const transport = agent.transport_method[Math.min(step, agent.transport_method.length-1)] ?? 'foot';
                  if (selected) {
                    setFollowedAgent(null);
                  } else {
                    setFollowedAgent({ agentId: agent.agent_id, agentType: agent.type, emotion, transport });
                  }
                }}
              >
                <AgentDot $color={EKMAN_COLORS[ekman]} />
                <span style={{ fontSize: '0.62rem', color: '#9ca3af', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {agent.agent_id}
                </span>
                <span style={{ fontSize: '0.55rem', color: tColor, flexShrink: 0 }}>{agent.type}</span>
                <span style={{ fontSize: '0.55rem', color: EKMAN_COLORS[ekman], flexShrink: 0 }}>{ekman}</span>
              </AgentCard>
            );
          })}
        </AgentList>
      </Panel>
    </MainGrid>
  );
}

// ── Agent Analytics Tab ───────────────────────────────────────────────────────

function AgentAnalyticsTab() {
  const { state, setFollowedAgent } = useSharedState();

  const agents = state.simulationData?.agents ?? [];
  const step   = state.currentStep;

  const followedAgentData = useMemo(() => {
    if (!state.followedAgent) return null;
    return agents.find(a => a.agent_id === state.followedAgent?.agentId) ?? null;
  }, [state.followedAgent, agents]);

  // Current mood vector
  const moodVectorData = useMemo(() => {
    if (!followedAgentData) return [];
    const vec = followedAgentData.mood_vector[Math.min(step, followedAgentData.mood_vector.length - 1)];
    if (!vec) return [];
    return EKMAN_ORDER.map((name, i) => ({
      name,
      value: +(vec[i] ?? 0).toFixed(3),
      fullValue: (vec[i] ?? 0) * 100,
      color: EKMAN_COLORS[name],
    }));
  }, [followedAgentData, step]);

  // Mood vector history (last 30 steps) for the followed agent
  const moodHistory = useMemo(() => {
    if (!followedAgentData) return [];
    const history = [];
    const start = Math.max(0, step - 29);
    for (let s = start; s <= step; s++) {
      const vec = followedAgentData.mood_vector[Math.min(s, followedAgentData.mood_vector.length - 1)];
      if (!vec) continue;
      const row: Record<string,number> = { step: s };
      EKMAN_ORDER.forEach((k, i) => { row[k] = +((vec[i] ?? 0) * 100).toFixed(1); });
      history.push(row);
    }
    return history;
  }, [followedAgentData, step]);

  // Radar data for current mood
  const radarData = useMemo(() => moodVectorData.map(d => ({
    emotion: d.name.slice(0, 3),
    value: +(d.value * 100).toFixed(1),
  })), [moodVectorData]);

  // Path progress
  const pathProgress = useMemo(() => {
    if (!followedAgentData?.path?.length) return 0;
    return Math.min(1, step / (followedAgentData.path.length - 1));
  }, [followedAgentData, step]);

  // Pick a random agent to follow
  const pickRandom = () => {
    if (!agents.length) return;
    const a = agents[Math.floor(Math.random() * agents.length)];
    const emotion   = a.emotion[Math.min(step, a.emotion.length-1)] ?? 'green';
    const transport = a.transport_method[Math.min(step, a.transport_method.length-1)] ?? 'foot';
    setFollowedAgent({ agentId: a.agent_id, agentType: a.type, emotion, transport });
  };

  if (!state.followedAgent || !followedAgentData) {
    return (
      <AnalyticsLayout style={{ display: 'flex', background: '#080810' }}>
        <EmptyState style={{ flex: 1 }}>
          <div style={{ fontSize: '1.4rem', opacity: 0.2 }}>◎</div>
          <div>NO AGENT SELECTED</div>
          <div style={{ color: '#374151', fontSize: '0.6rem', maxWidth: 220, lineHeight: 1.7 }}>
            Click an agent on the KPI roster or on the Map Dashboard to begin tracking
          </div>
          <SelectBtn onClick={pickRandom}>SELECT RANDOM AGENT</SelectBtn>
        </EmptyState>
      </AnalyticsLayout>
    );
  }

  const f = state.followedAgent;
  const d = followedAgentData;
  const currentEkman  = COLOR_TO_EKMAN[f.emotion] ?? f.emotion;
  const typeColor     = TYPE_COLORS[f.agentType] || '#9ca3af';
  const emotionColor  = EKMAN_COLORS[currentEkman] || '#9ca3af';

  return (
    <AnalyticsLayout>

      {/* ── Profile card (spans 2 rows) ──────────────────────────────────── */}
      <AgentProfileCard style={{ gridRow: '1 / span 2', borderRight: '1px solid #111827' }}>
        <div>
          <div style={{ fontSize: '0.6rem', color: '#4b5563', letterSpacing: '0.1em', marginBottom: 4 }}>
            FOLLOWED AGENT
          </div>
          <div style={{ fontSize: '1rem', fontWeight: 700, color: typeColor, letterSpacing: '0.04em' }}>
            {f.agentId}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <ProfileRow>
            <span>TYPE</span>
            <span style={{ color: typeColor }}>{f.agentType}</span>
          </ProfileRow>
          <ProfileRow>
            <span>EMOTION</span>
            <span style={{ color: emotionColor }}>{currentEkman}</span>
          </ProfileRow>
          <ProfileRow>
            <span>TRANSPORT</span>
            <span>{f.transport}</span>
          </ProfileRow>
          <ProfileRow>
            <span>STEP</span>
            <span style={{ color: '#a3e635' }}>{step} / {d.path.length - 1}</span>
          </ProfileRow>
        </div>

        {/* Path progress bar */}
        <div>
          <div style={{ fontSize: '0.55rem', color: '#4b5563', letterSpacing: '0.08em', marginBottom: 4 }}>
            PATH PROGRESS
          </div>
          <div style={{ height: 4, borderRadius: 2, background: '#1f2937', overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 2,
              background: `linear-gradient(90deg, ${typeColor}88, ${typeColor})`,
              width: `${(pathProgress * 100).toFixed(1)}%`,
              transition: 'width 0.3s ease',
            }} />
          </div>
          <div style={{ fontSize: '0.55rem', color: '#4b5563', marginTop: 3, textAlign: 'right' }}>
            {(pathProgress * 100).toFixed(0)}%
          </div>
        </div>

        {/* Mood vector bars */}
        <div>
          <div style={{ fontSize: '0.55rem', color: '#4b5563', letterSpacing: '0.08em', marginBottom: 6 }}>
            MOOD VECTOR — CURRENT STEP
          </div>
          {moodVectorData.map(m => (
            <MoodRow key={m.name}>
              <div className="label">{m.name}</div>
              <div className="bar-wrap">
                <MoodBar $value={m.value} $color={m.color} />
              </div>
              <div className="val">{m.fullValue.toFixed(0)}%</div>
            </MoodRow>
          ))}
        </div>

        <ClearBtn style={{ marginTop: 'auto' }} onClick={() => setFollowedAgent(null)}>
          RELEASE AGENT
        </ClearBtn>
      </AgentProfileCard>

      {/* ── Mood radar ────────────────────────────────────────────────────── */}
      <Panel>
        <PanelTitle>Emotion Radar — Step {step}</PanelTitle>
        <div style={{ flex: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
              <PolarGrid stroke="#1f2937" />
              <PolarAngleAxis dataKey="emotion" tick={{ fontSize: 9, fill: '#6b7280', fontFamily: 'IBM Plex Mono' }} />
              <Radar name="mood" dataKey="value" stroke={emotionColor} fill={emotionColor} fillOpacity={0.25} />
              <Tooltip contentStyle={{ background: '#080810', border: '1px solid #374151', borderRadius: 6, fontFamily: 'IBM Plex Mono', fontSize: 10 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* ── Mood trend for followed agent ─────────────────────────────────── */}
      <Panel>
        <PanelTitle>Mood History — Last 30 Steps</PanelTitle>
        <div style={{ flex: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={moodHistory} margin={{ top: 4, right: 8, bottom: 4, left: -10 }}>
              <CartesianGrid strokeDasharray="2 4" stroke="#1f2937" />
              <XAxis dataKey="step" tick={{ fontSize: 8, fill: '#6b7280', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#6b7280', fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: '#080810', border: '1px solid #374151', borderRadius: 6, fontFamily: 'IBM Plex Mono', fontSize: 10 }} />
              {EKMAN_ORDER.map(k => (
                <Line key={k} type="monotone" dataKey={k} stroke={EKMAN_COLORS[k]}
                  dot={false} strokeWidth={k === currentEkman ? 2.5 : 1}
                  opacity={k === currentEkman ? 1 : 0.35}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* ── Conversation history ──────────────────────────────────────────── */}
      <Panel style={{ gridColumn: '2 / span 2' }}>
        <PanelTitle>
          Conversation History
          {d.conversation?.length
            ? <span style={{ color: '#6b7280', fontWeight: 400 }}>&nbsp;{d.conversation.length} messages</span>
            : <span style={{ color: '#374151', fontWeight: 400 }}>&nbsp;no messages</span>
          }
        </PanelTitle>
        {d.conversation?.length ? (
          <ConvList>
            {d.conversation.map((text: string, i: number) => {
              const ts = d.conversation_timestamps?.[i] ?? 0;
              const isActive = Math.abs(ts - step) < 3;
              const isSelf = i % 2 === 0;
              return (
                <ConvLine key={i} $isSelf={isSelf}>
                  <ConvTs>STEP {ts} · {isSelf ? f.agentId : 'OTHER'}</ConvTs>
                  <ConvBubble $isSelf={isSelf}
                    style={isActive ? { borderColor: emotionColor, background: `${emotionColor}18` } : {}}
                  >
                    {text}
                  </ConvBubble>
                </ConvLine>
              );
            })}
          </ConvList>
        ) : (
          <div style={{ color: '#374151', fontSize: '0.62rem', padding: '8px 0' }}>
            No conversation data for this agent.
          </div>
        )}
      </Panel>

    </AnalyticsLayout>
  );
}

// ── Follow Agent Tab ──────────────────────────────────────────────────────────

function FollowAgentTab() {
  const { state, setFollowedAgent, setAgentTypeFilter } = useSharedState();
  const agents = state.simulationData?.agents ?? [];
  const step   = state.currentStep;
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  const filtered = useMemo(() => agents.filter(a => {
    if (typeFilter && a.type !== typeFilter) return false;
    return true;
  }), [agents, typeFilter]);

  const handleFollow = (agentId: string) => {
    const agent = agents.find(a => a.agent_id === agentId);
    if (!agent) return;
    const emotion   = agent.emotion[Math.min(step, agent.emotion.length-1)] ?? 'green';
    const transport = agent.transport_method[Math.min(step, agent.transport_method.length-1)] ?? 'foot';
    if (state.followedAgent?.agentId === agentId) {
      setFollowedAgent(null);
    } else {
      setFollowedAgent({ agentId, agentType: agent.type, emotion, transport });
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', gap: 1, background: '#111827', overflow: 'hidden', minHeight: 0 }}>
      {/* Filter sidebar */}
      <Panel style={{ width: 200, flexShrink: 0, borderRight: '1px solid #111827' }}>
        <PanelTitle>Filter by Type</PanelTitle>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {AGENT_TYPES.map(t => (
            <FilterChip key={t} $active={typeFilter === t} $color={TYPE_COLORS[t] || '#9ca3af'}
              onClick={() => setTypeFilter(typeFilter === t ? null : t)}
            >{t}</FilterChip>
          ))}
        </div>
        {typeFilter && <ClearBtn onClick={() => setTypeFilter(null)}>CLEAR</ClearBtn>}

        {state.followedAgent && (
          <>
            <PanelTitle style={{ marginTop: 12 }}>Currently Following</PanelTitle>
            <div style={{ fontSize: '0.7rem', fontWeight: 700, color: TYPE_COLORS[state.followedAgent.agentType] || '#e5e7eb' }}>
              {state.followedAgent.agentId}
            </div>
            <div style={{ fontSize: '0.6rem', color: '#6b7280', lineHeight: 1.8 }}>
              <div>Type: <span style={{ color: '#9ca3af' }}>{state.followedAgent.agentType}</span></div>
              <div>Emotion: <span style={{ color: EKMAN_COLORS[COLOR_TO_EKMAN[state.followedAgent.emotion]] || '#9ca3af' }}>
                {COLOR_TO_EKMAN[state.followedAgent.emotion] ?? state.followedAgent.emotion}
              </span></div>
              <div>Transport: <span style={{ color: '#9ca3af' }}>{state.followedAgent.transport}</span></div>
            </div>
            <ClearBtn onClick={() => setFollowedAgent(null)}>RELEASE</ClearBtn>
          </>
        )}

        <div style={{ marginTop: 'auto', fontSize: '0.58rem', color: '#374151' }}>
          <div>{filtered.length} agents listed</div>
        </div>
      </Panel>

      {/* Agent list */}
      <Panel style={{ flex: 1, minWidth: 0 }}>
        <PanelTitle>
          Select Agent to Follow
          <span style={{ color: '#4b5563', fontWeight: 400 }}>&nbsp;— updates Map Dashboard camera</span>
        </PanelTitle>
        <AgentList>
          {filtered.slice(0, 200).map(agent => {
            const emotion  = agent.emotion[Math.min(step, agent.emotion.length-1)] ?? 'green';
            const ekman    = COLOR_TO_EKMAN[emotion] ?? 'ENJOYMENT';
            const tColor   = TYPE_COLORS[agent.type] || '#9ca3af';
            const selected = state.followedAgent?.agentId === agent.agent_id;
            return (
              <AgentCard key={agent.agent_id} $selected={selected} $color={tColor}
                onClick={() => handleFollow(agent.agent_id)}
              >
                <AgentDot $color={EKMAN_COLORS[ekman]} />
                <span style={{ flex: 1, fontSize: '0.65rem', color: '#9ca3af', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {agent.agent_id}
                </span>
                <span style={{ fontSize: '0.6rem', color: tColor, flexShrink: 0 }}>{agent.type}</span>
                <span style={{ fontSize: '0.6rem', color: EKMAN_COLORS[ekman], flexShrink: 0 }}>{ekman}</span>
                {agent.follow && (
                  <span style={{ fontSize: '0.5rem', color: '#fbbf24', flexShrink: 0, marginLeft: 2 }}>★</span>
                )}
              </AgentCard>
            );
          })}
        </AgentList>
      </Panel>
    </div>
  );
}

// ── Root component ────────────────────────────────────────────────────────────

type TabId = 'main' | 'infra' | 'kpi' | 'analytics' | 'follow';

const SCENARIOS_ORDER: ScenarioId[] = ['continuity', 'overgrowth', 'degrowth', 'density'];

const searchParams = new URLSearchParams(window.location.search);
const IS_EMBED     = searchParams.has('embed');

function getInitialTab(): TabId {
  const param = searchParams.get('tab');
  const valid: TabId[] = ['main', 'infra', 'kpi', 'analytics', 'follow'];
  return valid.includes(param as TabId) ? (param as TabId) : 'main';
}

export default function KPIDashboard() {
  const { state, togglePlayback, setScenario, setYear } = useSharedState();
  const [activeTab, setActiveTab] = useState<TabId>(getInitialTab);
  const { min: yearMin, max: yearMax } = getYearRange();

  const agents = state.simulationData?.agents ?? [];
  const step   = state.currentStep;

  const emotionData = useMemo(() => {
    if (!agents.length) return [];
    const counts: Record<string, number> = Object.fromEntries(EKMAN_KEYS.map(k => [k, 0]));
    agents.forEach(a => {
      const color = a.emotion[Math.min(step, a.emotion.length-1)] ?? 'green';
      counts[COLOR_TO_EKMAN[color] ?? 'ENJOYMENT']++;
    });
    return EKMAN_KEYS.map(k => ({ name: k, count: counts[k] }));
  }, [agents, step]);

  const dominantEmotion = useMemo(() => {
    if (!emotionData.length) return '—';
    return emotionData.reduce((a, b) => b.count > a.count ? b : a).name;
  }, [emotionData]);

  const stressLevel = useMemo(() => {
    const total = agents.length || 1;
    const stressed = emotionData
      .filter(e => e.name !== 'ENJOYMENT')
      .reduce((s, e) => s + e.count, 0);
    return ((stressed / total) * 100).toFixed(0);
  }, [emotionData, agents.length]);

  return (
    <Page>
      {/* ── Top bar — hidden in embed mode ──────────────────────────────── */}
      <TopBar style={IS_EMBED ? { display: 'none' } : {}}>
        <Title>ANDORRA · KPI</Title>
        <Sep />
        <StatBadge>
          <span>AGENTS</span>
          <span>{state.totalAgents}</span>
        </StatBadge>
        <StatBadge>
          <span>STEP</span>
          <span $accent="#a3e635">{step}</span>
        </StatBadge>
        <StatBadge>
          <span>DOMINANT</span>
          <span $accent={EKMAN_COLORS[dominantEmotion] || '#e5e7eb'}>{dominantEmotion}</span>
        </StatBadge>
        <StatBadge>
          <span>STRESS PROXY</span>
          <span $accent="#f87171">{stressLevel}%</span>
        </StatBadge>
        {state.followedAgent && (
          <>
            <Sep />
            <StatBadge>
              <span>FOLLOWING</span>
              <span $accent={TYPE_COLORS[state.followedAgent.agentType] || '#e5e7eb'}>
                {state.followedAgent.agentId}
              </span>
            </StatBadge>
          </>
        )}
        <Sep />
        <StatBadge>
          <span>SCENARIO</span>
          <span $accent={SCENARIO_COLORS[state.selectedScenario]}>
            {SCENARIO_LABELS[state.selectedScenario]}
          </span>
        </StatBadge>
        <StatBadge>
          <span>YEAR</span>
          <span $accent="#a3e635">{state.selectedYear}</span>
        </StatBadge>
        <PlayBtn $playing={state.isPlaying} onClick={togglePlayback}>
          {state.isPlaying ? '⏸  PAUSE' : '▶  PLAY'}
        </PlayBtn>
      </TopBar>

      {/* ── Scenario + year selector — hidden in embed mode ────────────── */}
      <ScenarioBar style={IS_EMBED ? { display: 'none' } : {}}>
        {SCENARIOS_ORDER.map(s => (
          <ScenarioBtn
            key={s}
            $active={state.selectedScenario === s}
            $color={SCENARIO_COLORS[s]}
            onClick={() => setScenario(s)}
          >
            {SCENARIO_LABELS[s]}
          </ScenarioBtn>
        ))}
        <Sep />
        <span style={{ fontSize: '0.55rem', color: '#4b5563', letterSpacing: '0.08em', flexShrink: 0 }}>YEAR</span>
        <YearSlider
          type="range"
          min={yearMin}
          max={yearMax}
          step={1}
          value={state.selectedYear}
          onChange={e => setYear(Number(e.target.value))}
        />
        <YearLabel>{state.selectedYear}</YearLabel>
      </ScenarioBar>

      {/* ── Tab bar — hidden in embed mode (tab fixed by URL param) ───── */}
      <TabBar style={IS_EMBED ? { display: 'none' } : {}}>
        <Tab $active={activeTab === 'main'}      onClick={() => setActiveTab('main')}>MAIN</Tab>
        <Tab $active={activeTab === 'infra'}     onClick={() => setActiveTab('infra')}>INFRASTRUCTURE</Tab>
        <Tab $active={activeTab === 'kpi'}       onClick={() => setActiveTab('kpi')}>AGENT GRID</Tab>
        <Tab $active={activeTab === 'analytics'} onClick={() => setActiveTab('analytics')}>AGENT ANALYTICS</Tab>
        <Tab $active={activeTab === 'follow'}    onClick={() => setActiveTab('follow')}>FOLLOW AGENT</Tab>
      </TabBar>

      {/* ── Tab content ─────────────────────────────────────────────────── */}
      {activeTab === 'main'      && <ScenarioMainTab />}
      {activeTab === 'infra'     && <ScenarioInfraTab />}
      {activeTab === 'kpi'       && <KPIGridTab />}
      {activeTab === 'analytics' && <AgentAnalyticsTab />}
      {activeTab === 'follow'    && <FollowAgentTab />}
    </Page>
  );
}
