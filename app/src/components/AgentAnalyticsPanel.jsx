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
    <div style={{ width: '100%', height: '100%' }}>
      <iframe
        ref={iframeRef}
        src="/andorra/agent-analytics?embed"
        title="agent-analytics"
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
        allow="clipboard-write"
      />
    </div>
  );
}
