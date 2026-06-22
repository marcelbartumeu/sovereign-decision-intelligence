import { useState, useEffect, useRef } from 'react';
import MapVisualization from './components/MapVisualization';
import MapErrorBoundary from './components/MapErrorBoundary';

const SYNC_CHANNEL = 'andorra-dashboard-sync';

const initialOverlay = { 0: true, 1: true, 2: true, 3: true, 4: true };

export default function ProjectorView() {
  const [activeTab,      setActiveTab]      = useState('map');
  const [selectedYear,   setSelectedYear]   = useState(2024);
  const [overlayEnabled, setOverlayEnabled] = useState(initialOverlay);
  const [activeMapLayer, setActiveMapLayer] = useState('growth');
  const [synced,         setSynced]         = useState(false);
  const channelRef = useRef(null);
  const rxRef      = useRef({});

  // ── Receive sync from KPI dashboard ────────────────────────────────────────
  useEffect(() => {
    const ch = new BroadcastChannel(SYNC_CHANNEL);
    channelRef.current = ch;

    ch.onmessage = ({ data }) => {
      setSynced(true);
      if (data.activeTab      !== undefined) { setActiveTab(data.activeTab); }
      if (data.selectedYear   !== undefined) { rxRef.current.selectedYear   = data.selectedYear;   setSelectedYear(data.selectedYear);   }
      if (data.overlayEnabled !== undefined) { rxRef.current.overlayEnabled = data.overlayEnabled; setOverlayEnabled(data.overlayEnabled); }
      if (data.activeMapLayer !== undefined) { rxRef.current.activeMapLayer = data.activeMapLayer; setActiveMapLayer(data.activeMapLayer); }
    };

    return () => ch.close();
  }, []);

  // Broadcast map layer changes back (projector can also switch layers)
  useEffect(() => {
    if (rxRef.current.activeMapLayer === activeMapLayer) return;
    channelRef.current?.postMessage({ activeMapLayer });
  }, [activeMapLayer]);

  return (
    <div style={{
      width: '100vw', height: '100vh',
      background: '#1e1e1e',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
      fontFamily: "'IBM Plex Mono', monospace",
    }}>
      {/* ── Sync status bar (top) ───────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '1.2rem',
        padding: '6px 1.5rem',
        borderBottom: '1px solid #444',
        background: '#222',
        flexShrink: 0,
        fontSize: '10px', letterSpacing: '0.1em', color: '#888',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: synced ? '#4ade80' : '#555',
            boxShadow: synced ? '0 0 6px #4ade8088' : 'none',
          }} />
          <span style={{ color: synced ? '#4ade80' : '#555' }}>
            {synced ? 'KPI SYNC' : 'WAITING FOR KPI SCREEN'}
          </span>
        </div>

        <div style={{ width: 1, height: 16, background: '#444' }} />

        <div>
          YEAR&nbsp;&nbsp;
          <span style={{ color: '#a3e635', fontWeight: 700, fontSize: 13 }}>
            {selectedYear}
          </span>
        </div>

        <div style={{ marginLeft: 'auto', color: '#555', fontSize: 9 }}>
          ANDORRA V2.1 · PROJECTOR
        </div>
      </div>

      {/* ── Full-screen map ──────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <MapErrorBoundary>
          <MapVisualization
            overlayEnabled={overlayEnabled}
            selectedYear={selectedYear}
            activeLayer={activeMapLayer}
            onLayerChange={setActiveMapLayer}
            simulationOn={false}
            hoveredAgent={-1}
            selectedAgent={-1}
          />
        </MapErrorBoundary>
      </div>
    </div>
  );
}
