import { useEffect, useState } from 'react';

// Live UTC mission clock — ticks once a second.
function useMissionClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const hh = String(now.getUTCHours()).padStart(2, '0');
  const mm = String(now.getUTCMinutes()).padStart(2, '0');
  const ss = String(now.getUTCSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}Z`;
}

export default function Header({
  selectedYear,
  setSelectedYear,
  arduinoConnected,
  onArduinoToggle,
  arduinoStatus,
}) {
  const clock = useMissionClock();
  const yearRange = { min: 2010, max: 2049 };
  const timeLabels = [];
  for (let y = yearRange.min; y <= yearRange.max; y += 2) timeLabels.push(y);
  if (timeLabels[timeLabels.length - 1] !== yearRange.max) timeLabels.push(yearRange.max);
  const clampedYear = Math.min(2049, Math.max(2010, selectedYear));

  return (
    <div className="header">
      <div className="container">
        <div className="header-content">
          <div>
            <div className="station-eyebrow">SPECTRE // SOVEREIGN INTELLIGENCE</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.6rem', marginBottom: '0.25rem' }}>
              <h1>Andorra</h1>
              <span style={{
                fontFamily: 'var(--mono)',
                fontSize: 10, fontWeight: 600,
                color: 'var(--text2)',
                background: 'rgba(120,200,220,0.07)',
                border: '1px solid var(--glass-bdr)',
                borderRadius: 3, padding: '1px 6px',
                letterSpacing: '0.08em',
              }}>V2.1</span>
              <span className="classified-tag">CLASSIFIED</span>
            </div>
            <p>Advanced Scenario Modeling &amp; Impact Assessment</p>
            <button
              type="button"
              onClick={onArduinoToggle}
              data-connected={arduinoConnected ? 'true' : 'false'}
            >
              {arduinoConnected ? 'Disconnect Arduino' : 'Connect Arduino'}
            </button>
            {arduinoStatus && (
              <span style={{
                marginLeft: '0.5rem',
                fontSize: '11px',
                letterSpacing: 0,
                fontFamily: 'var(--mono)',
                color: arduinoStatus === 'Connected' ? 'var(--sys-green)' : 'var(--lbl)',
              }}>
                {arduinoStatus}
              </span>
            )}
          </div>

          {/* Mission-control telemetry cluster */}
          <div className="station-status">
            <div className="station-readout">
              <div className="k">Mission Time</div>
              <div className="v">{clock}</div>
            </div>
            <div className="station-readout">
              <div className="k">Station</div>
              <div className="v gold">42.5078°N&nbsp;&nbsp;1.5211°E</div>
            </div>
            <div className="status-led">
              <span className="dot" /> Tracking
            </div>
          </div>

          <div className="time-slider">
            <div className="scenario-info">
              <p className="label">Temporal Index</p>
              <p className="name">{clampedYear}</p>
              <p className="description">{yearRange.min} — {yearRange.max}</p>
            </div>
            <div className="slider-container">
              <input
                type="range"
                min={yearRange.min}
                max={yearRange.max}
                value={clampedYear}
                step="1"
                className="slider"
                onChange={(e) => setSelectedYear(Math.min(2049, Math.max(2010, parseInt(e.target.value, 10))))}
              />
              <div className="slider-labels" style={{ position: 'relative', height: '18px' }}>
                {timeLabels.map((y) => {
                  const pct = ((y - yearRange.min) / (yearRange.max - yearRange.min)) * 100;
                  return (
                    <span key={y} style={{
                      position: 'absolute',
                      left: `${pct}%`,
                      transform: 'translateX(-50%)',
                      whiteSpace: 'nowrap',
                    }}>{y}</span>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
