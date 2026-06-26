export default function Header({
  selectedYear,
  setSelectedYear,
  arduinoConnected,
  onArduinoToggle,
  arduinoStatus,
}) {
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
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <h1>Andorra</h1>
              <span style={{
                fontSize: 10, fontWeight: 500,
                color: 'rgba(255,255,255,0.28)',
                background: 'rgba(255,255,255,0.07)',
                border: '0.5px solid rgba(255,255,255,0.12)',
                borderRadius: 5, padding: '1px 6px',
                letterSpacing: '0.02em',
                fontFamily: 'var(--font)',
              }}>V2.1</span>
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
                fontFamily: 'var(--font)',
                color: arduinoStatus === 'Connected' ? 'var(--sys-green)' : 'var(--lbl)',
              }}>
                {arduinoStatus}
              </span>
            )}
          </div>
          <div className="time-slider">
            <div className="scenario-info">
              <p className="label">Year</p>
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
