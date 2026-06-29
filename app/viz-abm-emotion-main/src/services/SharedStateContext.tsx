import { createContext, useContext, useState, ReactNode, useEffect, useRef, useCallback } from 'react';
import { tabSyncService } from './TabSyncService';
import { type ScenarioId, type MapLayerId } from './ScenarioDataService';

// ── Data model ────────────────────────────────────────────────────────────────

export interface TripAgent {
  id:      string;
  nat:     string;   // nationality
  inc:     string;   // income_bracket
  emotion: string;   // dominant Ekman emotion
  color:   [number, number, number];  // RGB derived from emotion
  path:    [number, number][];        // [lon, lat] waypoints
  ts:      number[];                  // minutes from midnight, one per waypoint
  bounds?: number[];                  // start index of each trip segment in path
}

// Rich per-agent profile (agent_profiles_*.json). Loose-typed — see export_profiles.py.
export type AgentProfile = Record<string, any>;

export interface EmotionCounts {
  ANGER:    number;
  CONTEMPT: number;
  DISGUST:  number;
  ENJOYMENT:number;
  FEAR:     number;
  SADNESS:  number;
  SURPRISE: number;
}

interface SharedState {
  // Population data
  agents:        TripAgent[];
  totalAgents:   number;
  emotionCounts: EmotionCounts;
  natCounts:     Record<string, number>;

  // Rich profiles (lazy) + precomputed dashboard aggregates
  profiles:        Map<string, AgentProfile> | null;
  profilesLoading: boolean;
  aggregates:      Record<string, any> | null;

  // Playback
  isPlaying:      boolean;
  currentTimeMin: number;   // minutes from midnight, 0–1440
  playSpeed:      number;   // sim-minutes per real second (default 60)

  // Filters
  natFilter:     string | null;
  emotionFilter: string | null;

  // Followed agent
  followedAgentId: string | null;

  // Cross-dashboard sync
  selectedScenario: ScenarioId;
  selectedYear:     number;
  activeMapLayer:   MapLayerId;
}

interface SharedStateContextType {
  state:          SharedState;
  updateState:    (s: Partial<SharedState>) => void;
  togglePlayback: () => void;
  setNatFilter:   (n: string | null) => void;
  setEmotionFilter:(e: string | null) => void;
  setFollowedAgent:(id: string | null) => void;
  setScenario:    (s: ScenarioId) => void;
  setYear:        (y: number) => void;
  setMapLayer:    (l: MapLayerId) => void;
  loadSimulationData: () => Promise<void>;
  loadProfiles:   () => Promise<void>;
}

const EMPTY_EMOTIONS: EmotionCounts = {
  ANGER: 0, CONTEMPT: 0, DISGUST: 0, ENJOYMENT: 0, FEAR: 0, SADNESS: 0, SURPRISE: 0,
};

const initialState: SharedState = {
  agents:         [],
  totalAgents:    0,
  emotionCounts:  { ...EMPTY_EMOTIONS },
  natCounts:      {},
  profiles:        null,
  profilesLoading: false,
  aggregates:      null,
  isPlaying:      new URLSearchParams(window.location.search).has('embed'),
  currentTimeMin: 420,   // start at 07:00
  playSpeed:      20,    // 20 sim-min per real second — full day loops in ~72s, commutes clearly visible
  natFilter:      null,
  emotionFilter:  null,
  followedAgentId:null,
  selectedScenario: 'continuity',
  selectedYear:     2025,
  activeMapLayer:   'agents',
};

const SharedStateContext = createContext<SharedStateContextType | undefined>(undefined);

export function SharedStateProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SharedState>(initialState);
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // ── Tab sync ───────────────────────────────────────────────────────────────
  useEffect(() => {
    const unsub = tabSyncService.subscribe((msg) => {
      switch (msg.type) {
        case 'PLAY':
          setState(p => ({ ...p, isPlaying: true }));
          break;
        case 'PAUSE':
          setState(p => ({ ...p, isPlaying: false }));
          break;
        case 'STEP_UPDATE':
          if (typeof msg.data?.currentTimeMin === 'number') {
            setState(p => ({ ...p, currentTimeMin: msg.data!.currentTimeMin! }));
          }
          break;
        case 'FILTER_UPDATE':
          setState(p => ({
            ...p,
            ...(msg.data?.natFilter     !== undefined && { natFilter:     msg.data.natFilter ?? null }),
            ...(msg.data?.emotionFilter !== undefined && { emotionFilter: msg.data.emotionFilter ?? null }),
          }));
          break;
        case 'SCENARIO_CHANGE':
          if (msg.data?.scenario) setState(p => ({ ...p, selectedScenario: msg.data!.scenario as ScenarioId }));
          break;
        case 'YEAR_CHANGE':
          if (typeof msg.data?.year === 'number') setState(p => ({ ...p, selectedYear: msg.data!.year! }));
          break;
        case 'MAP_LAYER_CHANGE':
          if (msg.data?.mapLayer) setState(p => ({ ...p, activeMapLayer: msg.data!.mapLayer as MapLayerId }));
          break;
      }
    });
    return () => unsub();
  }, []);

  // ── Playback animation loop ────────────────────────────────────────────────
  useEffect(() => {
    if (!state.isPlaying) return;
    let lastTs: number | null = null;
    let accumMs = 0;            // time accrued since the last state update
    const STEP_MS = 50;        // commit state at ~20fps, not every frame — the RAF still
                               // runs at 60fps so timing stays accurate, but we re-render
                               // the (heavy) React tree 3x less often.
    let rafId: number;

    const tick = (now: number) => {
      if (lastTs !== null) {
        accumMs += now - lastTs;
        if (accumMs >= STEP_MS) {
          const dtSec = accumMs / 1000;
          accumMs = 0;
          setState(p => {
            const next = (p.currentTimeMin + dtSec * p.playSpeed) % 1440;
            tabSyncService.broadcast({ type: 'STEP_UPDATE', data: { currentTimeMin: next } });
            return { ...p, currentTimeMin: next };
          });
        }
      }
      lastTs = now;
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [state.isPlaying, state.playSpeed]);

  // ── Data loading ───────────────────────────────────────────────────────────
  const loadSimulationData = useCallback(async () => {
    try {
      const CHUNKS = 6;
      console.log(`Loading andorra_trips (${CHUNKS} chunks)…`);
      const chunks = await Promise.all(
        Array.from({ length: CHUNKS }, (_, i) =>
          fetch(`/model/andorra_trips_${i}.json`).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status} on chunk ${i}`);
            return r.json() as Promise<TripAgent[]>;
          })
        )
      );
      const agents: TripAgent[] = ([] as TripAgent[]).concat(...chunks);

      // Precomputed dashboard aggregates (tiny — load alongside trips)
      const aggregates = await fetch('/model/agent_aggregates.json')
        .then(r => (r.ok ? r.json() : null)).catch(() => null);

      // Compute static summary stats from profiles
      const emotionCounts = { ...EMPTY_EMOTIONS };
      const natCounts: Record<string, number> = {};

      for (const a of agents) {
        const em = a.emotion as keyof EmotionCounts;
        if (em in emotionCounts) emotionCounts[em]++;
        natCounts[a.nat] = (natCounts[a.nat] ?? 0) + 1;
      }

      console.log(`Loaded ${agents.length.toLocaleString()} agents.`);

      setState(p => ({
        ...p,
        agents,
        totalAgents:   agents.length,
        emotionCounts,
        natCounts,
        aggregates,
      }));

      tabSyncService.broadcast({ type: 'SIMULATION_LOADED', data: { totalAgents: agents.length } });
    } catch (err) {
      console.error('Failed to load andorra_trips.json:', err);
    }
  }, []);

  useEffect(() => { loadSimulationData(); }, []);

  // Lazily load the rich per-agent profiles (~140 MB, 6 chunks) — only when the
  // Agent Analytics tab needs them, not on the initial map load.
  const loadProfiles = useCallback(async () => {
    if (stateRef.current.profiles || stateRef.current.profilesLoading) return;
    setState(p => ({ ...p, profilesLoading: true }));
    try {
      const CHUNKS = 6;
      const chunks = await Promise.all(
        Array.from({ length: CHUNKS }, (_, i) =>
          fetch(`/model/agent_profiles_${i}.json`).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status} on profile chunk ${i}`);
            return r.json() as Promise<AgentProfile[]>;
          })
        )
      );
      const profiles = new Map<string, AgentProfile>();
      for (const chunk of chunks) for (const rec of chunk) profiles.set(rec.id, rec);
      console.log(`Loaded ${profiles.size.toLocaleString()} agent profiles.`);
      setState(p => ({ ...p, profiles, profilesLoading: false }));
    } catch (err) {
      console.error('Failed to load agent_profiles:', err);
      setState(p => ({ ...p, profilesLoading: false }));
    }
  }, []);

  // ── Public actions ─────────────────────────────────────────────────────────
  const updateState = (s: Partial<SharedState>) => setState(p => ({ ...p, ...s }));

  const togglePlayback = () => {
    const next = !stateRef.current.isPlaying;
    setState(p => ({ ...p, isPlaying: next }));
    tabSyncService.broadcast({ type: next ? 'PLAY' : 'PAUSE' });
  };

  const setNatFilter = (n: string | null) => {
    setState(p => ({ ...p, natFilter: n }));
    tabSyncService.broadcast({ type: 'FILTER_UPDATE', data: { natFilter: n } });
  };

  const setEmotionFilter = (e: string | null) => {
    setState(p => ({ ...p, emotionFilter: e }));
    tabSyncService.broadcast({ type: 'FILTER_UPDATE', data: { emotionFilter: e } });
  };

  const setFollowedAgent = (id: string | null) =>
    setState(p => ({ ...p, followedAgentId: id }));

  const setScenario = (s: ScenarioId) => {
    setState(p => ({ ...p, selectedScenario: s }));
    tabSyncService.broadcast({ type: 'SCENARIO_CHANGE', data: { scenario: s } });
  };

  const setYear = (y: number) => {
    setState(p => ({ ...p, selectedYear: y }));
    tabSyncService.broadcast({ type: 'YEAR_CHANGE', data: { year: y } });
  };

  const setMapLayer = (l: MapLayerId) => {
    setState(p => ({ ...p, activeMapLayer: l }));
    tabSyncService.broadcast({ type: 'MAP_LAYER_CHANGE', data: { mapLayer: l } });
  };

  return (
    <SharedStateContext.Provider value={{
      state, updateState, togglePlayback,
      setNatFilter, setEmotionFilter, setFollowedAgent,
      setScenario, setYear, setMapLayer, loadSimulationData, loadProfiles,
    }}>
      {children}
    </SharedStateContext.Provider>
  );
}

export function useSharedState() {
  const ctx = useContext(SharedStateContext);
  if (!ctx) throw new Error('useSharedState must be used within SharedStateProvider');
  return ctx;
}
