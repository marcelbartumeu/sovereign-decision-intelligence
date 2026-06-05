import { OVERLAY_SCENARIOS } from '../utils/chartUtils';

export default function OverlayBadges({ overlayEnabled, setOverlayEnabled, onToggle }) {
  return (
    <header className="overlay-header">
      <h2>Scenario overlay</h2>
      <p>Toggle scenarios on or off to compare their trajectories on the same charts.</p>
      <div className="overlay-layer-badges">
        {OVERLAY_SCENARIOS.map(({ index, label, color }) => (
          <button
            type="button"
            key={index}
            className={`overlay-layer-badge ${overlayEnabled[index] ? 'active' : 'inactive'}`}
            onClick={() => onToggle(index)}
            title={label}
          >
            <span className="dot" style={{ background: color }} />
            {label}
          </button>
        ))}
      </div>
    </header>
  );
}
