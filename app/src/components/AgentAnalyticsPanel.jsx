import { useEffect, useRef } from 'react';

export default function AgentAnalyticsPanel({ hoveredAgent = -1, selectedAgent = -1 }) {
  const iframeRef = useRef(null);

  useEffect(() => {
    if (hoveredAgent < 0) return;
    iframeRef.current?.contentWindow?.postMessage({ type: 'AGENT_HOVER', pos: hoveredAgent }, '*');
  }, [hoveredAgent]);

  useEffect(() => {
    if (selectedAgent < 0) return;
    iframeRef.current?.contentWindow?.postMessage({ type: 'AGENT_SELECT', pos: selectedAgent }, '*');
  }, [selectedAgent]);

  return (
    <div className="intel-feed-frame">
      <iframe
        ref={iframeRef}
        src="/andorra/agent-analytics?embed"
        title="agent-analytics"
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
        allow="clipboard-write"
      />
      <div className="feed-tag">◉ HUMINT · AGENT DOSSIER · LIVE</div>
      <div className="map-hud" aria-hidden="true">
        <span className="map-bracket tl" />
        <span className="map-bracket tr" />
        <span className="map-bracket bl" />
        <span className="map-bracket br" />
      </div>
    </div>
  );
}
