import { useState, useCallback, useEffect, useRef } from 'react';
import Header from './components/Header';
import TabNav from './components/TabNav';
import OverlayBadges from './components/OverlayBadges';
import KpiGrid from './components/KpiGrid';
import AgentAnalyticsPanel from './components/AgentAnalyticsPanel';
import NetworkView from './components/NetworkView';
import MapVisualization from './components/MapVisualization';
import EarthView from './components/EarthView';
import SpectreIntro from './components/SpectreIntro';
import HudFrame from './components/HudFrame';
import MapErrorBoundary from './components/MapErrorBoundary';
import { useSerial } from './hooks/useSerial';

// Scenario name → numeric overlay index (matches OVERLAY_SCENARIOS in chartUtils.js)
const SCENARIO_INDEX = {
  historical: 0, overgrowth: 1, degrowth: 2, continuity: 3, density: 4,
};

const initialOverlay = { 0: true, 1: true, 2: true, 3: true, 4: true };

const SYNC_CHANNEL = 'andorra-dashboard-sync';

// KPI-grid tabs (each shows its own KPI dashboard, no map behind it).
const KPI_TABS = ['main', 'economic', 'social', 'environmental', 'infrastructure'];

// ── Per-tab session ("hard reset" detection) ────────────────────────────────
// A normal refresh keeps sessionStorage → skip the SPECTRE intro + globe search and
// land back in the dashboard. A new tab / reopened browser clears it → full boot again.
const SESSION_KEY = 'spectre_session_v1';
const TAB_KEY     = 'spectre_tab';
const hasSession  = () => { try { return sessionStorage.getItem(SESSION_KEY) === '1'; } catch { return false; } };

export default function App() {
  const [phase,           setPhase]           = useState(() => (hasSession() ? 'app' : 'intro')); // intro | earth | app
  const [activeTab,       setActiveTab]       = useState(() => {
    try { return (hasSession() && sessionStorage.getItem(TAB_KEY)) || 'main'; } catch { return 'main'; }
  });
  const [selectedYear,    setSelectedYear]    = useState(2024);
  const [overlayEnabled,  setOverlayEnabled]  = useState(initialOverlay);
  const [activeMapLayer,  setActiveMapLayer]  = useState('base');
  const mapLayerTimerRef  = useRef(null);   // debounce timer for map layer changes
  const [simulationOn,    setSimulationOn]    = useState(false);
  const [hoveredAgent,    setHoveredAgent]    = useState(-1);
  const [selectedAgent,   setSelectedAgent]   = useState(-1);
  const [entering,        setEntering]        = useState(false); // globe → dashboard reveal

  // Persist the active tab so a refresh restores it.
  useEffect(() => {
    try { sessionStorage.setItem(TAB_KEY, activeTab); } catch (_) {}
  }, [activeTab]);

  // ── BroadcastChannel sync (dual-screen) ─────────────────────────────────────

  const channelRef = useRef(null);
  const rxRef      = useRef({});  // tracks last value received from channel to break echo loops

  useEffect(() => {
    const ch = new BroadcastChannel(SYNC_CHANNEL);
    channelRef.current = ch;

    ch.onmessage = ({ data }) => {
      if (data.selectedYear   !== undefined) { rxRef.current.selectedYear   = data.selectedYear;   setSelectedYear(data.selectedYear);   }
      if (data.activeTab      !== undefined) { rxRef.current.activeTab      = data.activeTab;      setActiveTab(data.activeTab);         }
      if (data.overlayEnabled !== undefined) { rxRef.current.overlayEnabled = data.overlayEnabled; setOverlayEnabled(data.overlayEnabled); }
      if (data.activeMapLayer !== undefined) { rxRef.current.activeMapLayer = data.activeMapLayer; setActiveMapLayer(data.activeMapLayer); }
    };

    return () => ch.close();
  }, []);

  useEffect(() => {
    if (rxRef.current.selectedYear   === selectedYear)   return;
    channelRef.current?.postMessage({ selectedYear });
  }, [selectedYear]);

  useEffect(() => {
    if (rxRef.current.activeTab      === activeTab)      return;
    channelRef.current?.postMessage({ activeTab });
  }, [activeTab]);

  useEffect(() => {
    if (rxRef.current.overlayEnabled === overlayEnabled) return;
    channelRef.current?.postMessage({ overlayEnabled });
  }, [overlayEnabled]);

  useEffect(() => {
    if (rxRef.current.activeMapLayer === activeMapLayer) return;
    channelRef.current?.postMessage({ activeMapLayer });
  }, [activeMapLayer]);

  // ── Boot / navigation ───────────────────────────────────────────────────────

  const enterApp = useCallback(() => {
    try { sessionStorage.setItem(SESSION_KEY, '1'); } catch (_) {}
    setActiveTab('main');
    setEntering(true);
    setPhase('app');
    setTimeout(() => setEntering(false), 1200);
  }, []);

  const handleTabChange = useCallback((tabId) => {
    setActiveTab(tabId);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, []);

  // ── Listen for Andorra entry from the Earth globe iframe ────────────────────

  useEffect(() => {
    const handler = (event) => {
      if (event.data?.action === 'enterAndorra') enterApp();
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [enterApp]);

  // ── Arduino callbacks ────────────────────────────────────────────────────────

  const handleYearChange = useCallback((year) => setSelectedYear(year), []);

  const handleOverlayChange = useCallback((scenario, state) => {
    const idx = SCENARIO_INDEX[scenario];
    if (idx === undefined) return;
    setOverlayEnabled((prev) => ({ ...prev, [idx]: state }));
  }, []);

  const handleMapLayerChange = useCallback((layerId) => {
    // Debounce: only switch after the controller holds the same position for 400ms.
    if (mapLayerTimerRef.current) clearTimeout(mapLayerTimerRef.current);
    mapLayerTimerRef.current = setTimeout(() => {
      setActiveMapLayer(layerId);
      setActiveTab('map'); // hardware layer changes surface the map tab
    }, 400);
  }, []);

  const handleSimulationToggle = useCallback(() => setSimulationOn((v) => !v), []);
  const handleAgentHover  = useCallback((index) => setHoveredAgent(index), []);
  const handleAgentSelect = useCallback((index) => setSelectedAgent(index), []);

  // ── Web Serial connection ────────────────────────────────────────────────────

  const { connected: arduinoConnected, status: arduinoStatus, toggle: onArduinoToggle } =
    useSerial(
      handleYearChange,
      handleTabChange,
      handleOverlayChange,
      handleMapLayerChange,
      handleSimulationToggle,
      handleAgentHover,
      handleAgentSelect,
    );

  // ── UI-driven overlay toggle (on-screen badges) ───────────────────────────────

  const handleOverlayToggle = useCallback((index) => {
    setOverlayEnabled((prev) => ({ ...prev, [index]: !prev[index] }));
  }, []);

  // Primary scenario for headline KPI = lowest-index active overlay, null if none active
  const primaryScenario = Object.keys(overlayEnabled)
    .map(Number)
    .find((i) => overlayEnabled[i]) ?? null;

  // ── Boot screens ─────────────────────────────────────────────────────────────
  if (phase === 'intro') {
    return <SpectreIntro onComplete={() => setPhase('earth')} />;
  }

  if (phase === 'earth') {
    return (
      <div className="earth-stage" style={{ position: 'fixed', inset: 0 }}>
        <EarthView />
        <HudFrame />
      </div>
    );
  }

  // ── Simulation dashboard ──────────────────────────────────────────────────
  const isKpiTab = KPI_TABS.includes(activeTab);

  return (
    <div className={`app-shell ${entering ? 'is-entering' : ''}`} style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {entering && <div className="enter-veil" />}
      <HudFrame />
      <Header
        selectedYear={selectedYear}
        setSelectedYear={setSelectedYear}
        arduinoConnected={arduinoConnected}
        onArduinoToggle={onArduinoToggle}
        arduinoStatus={arduinoStatus}
      />

      {/* ── Tab nav bar ── */}
      <div className="subnav" style={{ flexShrink: 0, zIndex: 20 }}>
        <div className="container" style={{ paddingTop: '0.75rem', paddingBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button className="glass-pill-btn" onClick={() => setPhase('earth')}>
                ← Globe
              </button>
              <TabNav activeTab={activeTab} setActiveTab={handleTabChange} />
            </div>
            {/* Map is a view mode, kept separate from the dashboard section tabs */}
            <button
              className={`glass-pill-btn ${activeTab === 'map' ? 'active' : ''}`}
              onClick={() => handleTabChange('map')}
            >
              ◳ Map
            </button>
          </div>
        </div>
      </div>

      {/* ── Content area ── */}
      <div className="content-area" style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>

        {activeTab === 'map' && (
          <div style={{ position: 'absolute', inset: 0 }}>
            <MapErrorBoundary>
              <MapVisualization
                overlayEnabled={overlayEnabled}
                selectedYear={selectedYear}
                activeLayer={activeMapLayer}
                onLayerChange={setActiveMapLayer}
                hoveredAgent={hoveredAgent}
                selectedAgent={selectedAgent}
              />
            </MapErrorBoundary>
          </div>
        )}

        {activeTab === 'agents' && (
          <div style={{ position: 'absolute', inset: 0 }}>
            <AgentAnalyticsPanel hoveredAgent={hoveredAgent} selectedAgent={selectedAgent} />
          </div>
        )}

        {activeTab === 'network' && (
          <div style={{ position: 'absolute', inset: 0 }}>
            <NetworkView />
          </div>
        )}

        {isKpiTab && (
          <div className="kpi-dashboard" style={{ position: 'absolute', inset: 0, overflowY: 'auto' }}>
            <div className="container" style={{ paddingTop: '1.25rem', paddingBottom: '2rem' }}>
              <OverlayBadges
                overlayEnabled={overlayEnabled}
                setOverlayEnabled={setOverlayEnabled}
                onToggle={handleOverlayToggle}
              />
              <KpiGrid
                activeScenario={primaryScenario}
                activeTab={activeTab}
                selectedYear={selectedYear}
                overlayEnabled={overlayEnabled}
                onOverlayToggle={handleOverlayToggle}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
