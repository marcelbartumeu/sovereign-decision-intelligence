import { useSharedState } from '../services/SharedStateContext';

const EMOTION_HEX: Record<string, string> = {
  ENJOYMENT: '#34d399', ANGER: '#f87171', FEAR: '#fb923c',
  SADNESS:   '#60a5fa', CONTEMPT: '#c084fc', DISGUST: '#fbbf24', SURPRISE: '#22d3ee',
};

const NAT_LABELS: Record<string, string> = {
  Andorran: 'AND', Spanish: 'ESP', Portuguese: 'PRT', French: 'FRA', Other: 'OTH',
};

const panel: React.CSSProperties = {
  position: 'absolute', top: 0, left: 0, right: 0,
  height: 48,
  display: 'flex', alignItems: 'center', gap: '0.75rem',
  padding: '0 1rem',
  background: 'rgba(10,10,15,0.92)',
  borderBottom: '1px solid #1f2937',
  zIndex: 10,
  fontFamily: "'IBM Plex Mono', monospace",
};

const divider: React.CSSProperties = {
  width: 1, height: 22, background: '#1f2937', flexShrink: 0,
};

const chip = (active: boolean, color: string): React.CSSProperties => ({
  fontSize: '0.65rem', padding: '3px 9px', borderRadius: 3, cursor: 'pointer',
  border: `1px solid ${active ? color : '#1f293755'}`,
  background: active ? `${color}22` : 'transparent',
  color: active ? color : '#6b7280',
  letterSpacing: '0.06em', transition: 'all .15s',
  userSelect: 'none',
});

export function SharedControlPanel() {
  const { state, togglePlayback, setNatFilter, setEmotionFilter, updateState } = useSharedState();

  const h  = Math.floor(state.currentTimeMin / 60).toString().padStart(2, '0');
  const m  = Math.floor(state.currentTimeMin % 60).toString().padStart(2, '0');

  const total = state.totalAgents || 1;
  const topEmotion = (Object.entries(state.emotionCounts) as [string, number][])
    .sort((a, b) => b[1] - a[1])[0]?.[0] ?? '—';

  return (
    <div style={panel}>
      {/* Play / Pause */}
      <button
        onClick={togglePlayback}
        style={{
          fontSize: '0.75rem', padding: '5px 12px', borderRadius: 4, cursor: 'pointer',
          border: `1px solid ${state.isPlaying ? '#f87171' : '#4ade80'}55`,
          background: state.isPlaying ? '#f8717112' : '#4ade8012',
          color: state.isPlaying ? '#f87171' : '#4ade80',
          letterSpacing: '0.06em', flexShrink: 0,
        }}
      >
        {state.isPlaying ? '⏸' : '▶'}
      </button>

      {/* HH:MM clock */}
      <span style={{ fontSize: '1rem', color: '#e5e7eb', letterSpacing: '0.12em', minWidth: 48, flexShrink: 0 }}>
        {h}:{m}
      </span>

      {/* Time scrubber */}
      <input
        type="range" min={0} max={1439} step={1}
        value={Math.floor(state.currentTimeMin)}
        onChange={e => updateState({ currentTimeMin: Number(e.target.value), isPlaying: false })}
        style={{ width: 120, accentColor: '#4ade80', cursor: 'pointer', flexShrink: 0 }}
      />

      {/* Speed */}
      <select
        value={state.playSpeed}
        onChange={e => updateState({ playSpeed: Number(e.target.value) })}
        style={{
          fontSize: '0.65rem', background: 'transparent', color: '#6b7280',
          border: '1px solid #1f2937', borderRadius: 3, padding: '3px 6px',
          fontFamily: 'inherit', cursor: 'pointer', flexShrink: 0,
        }}
      >
        {[1, 2, 5, 10, 30, 60].map(s => (
          <option key={s} value={s}>{s}×</option>
        ))}
      </select>

      <span style={divider} />

      {/* Agent count */}
      <span style={{ fontSize: '0.68rem', color: '#6b7280', letterSpacing: '0.06em', flexShrink: 0 }}>
        {state.totalAgents.toLocaleString()} AGENTS
      </span>

      <span style={divider} />

      {/* Nationality filters */}
      {Object.entries(NAT_LABELS).map(([nat, label]) => (
        <button
          key={nat}
          onClick={() => setNatFilter(state.natFilter === nat ? null : nat)}
          style={chip(state.natFilter === nat, '#4ade80')}
        >
          {label} {state.natCounts[nat] ? `${Math.round(state.natCounts[nat] / state.totalAgents * 100)}%` : ''}
        </button>
      ))}

      <span style={divider} />

      {/* Dominant emotion indicator */}
      <span style={{
        fontSize: '0.65rem', color: EMOTION_HEX[topEmotion] ?? '#9ca3af',
        letterSpacing: '0.06em', flexShrink: 0,
      }}>
        ● {topEmotion}
      </span>

      {/* Emotion filter chips */}
      {Object.keys(EMOTION_HEX).map(em => {
        const count = state.emotionCounts[em as keyof typeof state.emotionCounts] ?? 0;
        const pct   = Math.round(count / total * 100);
        if (pct === 0) return null;
        return (
          <button
            key={em}
            onClick={() => setEmotionFilter(state.emotionFilter === em ? null : em)}
            style={chip(state.emotionFilter === em, EMOTION_HEX[em])}
          >
            {em.slice(0, 3)} {pct}%
          </button>
        );
      })}
    </div>
  );
}
