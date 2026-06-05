import { useState, useCallback, useEffect, useRef } from 'react';
import Header from './components/Header';
import TabNav from './components/TabNav';
import OverlayBadges from './components/OverlayBadges';
import KpiGrid from './components/KpiGrid';
import AgentAnalyticsPanel from './components/AgentAnalyticsPanel';
import MapVisualization from './components/MapVisualization';
import EarthView from './components/EarthView';
import { useSerial } from './hooks/useSerial';

// Scenario name → numeric overlay index (matches OVERLAY_SCENARIOS in chartUtils.js)
const SCENARIO_INDEX = {
  historical: 0, overgrowth: 1, degrowth: 2, continuity: 3, density: 4,
};

const initialOverlay = { 0: true, 1: true, 2: true, 3: true, 4: true };

const SYNC_CHANNEL = 'andorra-dashboard-sync';

export default function App() {
  const [activeTab,       setActiveTab]       = useState('earth');
  const [selectedYear,    setSelectedYear]    = useState(2024);
  const [overlayEnabled,  setOverlayEnabled]  = useState(initialOverlay);
  const [activeMapLayer,  setActiveMapLayer]  = useState('base');
  const prevMapLayerRef   = useRef('base'); // remembers the layer before agents tab
  const mapLayerTimerRef  = useRef(null);   // debounce timer for map layer changes
  const [simulationOn,    setSimulationOn]    = useState(false);
  const [hoveredAgent,    setHoveredAgent]    = useState(-1);
  const [selectedAgent,   setSelectedAgent]   = useState(-1);
  const [kpiOpen,         setKpiOpen]         = useState(true);

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

  // Broadcast whenever state changes locally (skip if the value came from the channel)
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

  // ── Arduino callbacks ────────────────────────────────────────────────────────

  const handleYearChange = useCallback((year) => {
    setSelectedYear(year);
  }, []);

  const handleTabChange = useCallback((tabId) => {
    setActiveTab(tabId);
    window.scrollTo({ top: 0, behavior: 'instant' });
    if (tabId === 'agents') {
      prevMapLayerRef.current = activeMapLayer;
      setActiveMapLayer('agents');
    } else if (activeMapLayer === 'agents') {
      setActiveMapLayer('base');
    }
  }, [activeMapLayer]);

  // ── Listen for Andorra click from the Earth globe iframe ────────────────────

  useEffect(() => {
    const handler = (event) => {
      if (event.data?.action === 'enterAndorra') {
        handleTabChange('main');
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [handleTabChange]);

  // Toggle sends scenario name + explicit boolean state (not just a flip)
  const handleOverlayChange = useCallback((scenario, state) => {
    const idx = SCENARIO_INDEX[scenario];
    if (idx === undefined) return;
    setOverlayEnabled((prev) => ({ ...prev, [idx]: state }));
  }, []);

  const handleMapLayerChange = useCallback((layerId) => {
    // Debounce: only switch after the controller holds the same position for 400ms.
    // Prevents crashes when the Arduino encoder sweeps through positions quickly.
    if (mapLayerTimerRef.current) clearTimeout(mapLayerTimerRef.current);
    mapLayerTimerRef.current = setTimeout(() => {
      setActiveMapLayer(layerId);
    }, 400);
  }, []);

  const handleSimulationToggle = useCallback(() => {
    setSimulationOn((v) => !v);
  }, []);

  const handleAgentHover = useCallback((index) => {
    setHoveredAgent(index);
  }, []);

  const handleAgentSelect = useCallback((index) => {
    setSelectedAgent(index);
  }, []);

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

  // ── Full-page globe — no header, no tab bar ─────────────────────────────────
  if (activeTab === 'earth') {
    return (
      <div style={{ position: 'fixed', inset: 0 }}>
        <EarthView />
      </div>
    );
  }

  // ── Simulation dashboard ──────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Header
        selectedYear={selectedYear}
        setSelectedYear={setSelectedYear}
        arduinoConnected={arduinoConnected}
        onArduinoToggle={onArduinoToggle}
        arduinoStatus={arduinoStatus}
      />

      {/* ── Tab nav bar ── */}
      <div style={{
        flexShrink: 0, zIndex: 20,
        background: 'rgba(0,0,0,0.88)',
        backdropFilter: 'blur(24px) saturate(1.8)',
        WebkitBackdropFilter: 'blur(24px) saturate(1.8)',
        borderBottom: '0.5px solid rgba(255,255,255,0.08)',
      }}>
        <div className="container" style={{ paddingTop: '0.75rem', paddingBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button
                onClick={() => handleTabChange('earth')}
                style={{
                  background: 'rgba(255,255,255,0.07)',
                  border: '0.5px solid rgba(255,255,255,0.12)',
                  borderRadius: 980, padding: '5px 14px', cursor: 'pointer',
                  fontFamily: 'var(--font)', fontSize: 12, fontWeight: 400,
                  color: 'rgba(255,255,255,0.5)',
                  whiteSpace: 'nowrap', flexShrink: 0,
                }}
              >
                ← Back
              </button>
              <TabNav activeTab={activeTab} setActiveTab={handleTabChange} />
            </div>
            <button
              onClick={() => setKpiOpen(v => !v)}
              style={{
                background: 'rgba(255,255,255,0.07)',
                border: '0.5px solid rgba(255,255,255,0.12)',
                borderRadius: 980, padding: '5px 14px', cursor: 'pointer',
                fontFamily: 'var(--font)', fontSize: 12, fontWeight: 400,
                color: 'rgba(255,255,255,0.5)',
                whiteSpace: 'nowrap', flexShrink: 0,
              }}
            >
              {kpiOpen ? '▲ Hide' : '▼ Show'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Content area ── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0, background: '#0a0a0a' }} />

        {activeTab === 'agents' && (
          <div style={{ position: 'absolute', inset: 0 }}>
            <AgentAnalyticsPanel hoveredAgent={hoveredAgent} selectedAgent={selectedAgent} />
          </div>
        )}

        {activeTab !== 'agents' && (
          <div style={{ position: 'absolute', inset: 0 }}>
            <MapVisualization
              overlayEnabled={overlayEnabled}
              selectedYear={selectedYear}
              activeLayer={activeMapLayer}
              onLayerChange={handleMapLayerChange}
              hoveredAgent={hoveredAgent}
              selectedAgent={selectedAgent}
            />
          </div>
        )}

        {activeTab !== 'agents' && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
            background: kpiOpen ? 'rgba(0,0,0,0.88)' : 'transparent',
            backdropFilter: kpiOpen ? 'blur(24px) saturate(1.8)' : 'none',
            WebkitBackdropFilter: kpiOpen ? 'blur(24px) saturate(1.8)' : 'none',
            borderBottom: kpiOpen ? '0.5px solid rgba(255,255,255,0.08)' : 'none',
            transition: 'background 0.2s cubic-bezier(0.25, 0.1, 0.25, 1)',
          }}>
            {kpiOpen && (
              <div className="container" style={{ paddingTop: '0.75rem', paddingBottom: '1rem', maxHeight: 'calc(100vh - 160px)', overflowY: 'auto' }}>
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
            )}
          </div>
        )}
      </div>
    </div>
  );
}
