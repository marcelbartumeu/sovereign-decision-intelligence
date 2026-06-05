import { useState, useMemo } from 'react';
import { generateKpiData } from '../utils/kpiData';
import { buildOverlayDataForKpi } from '../utils/chartUtils';
import KpiCard from './KpiCard';

const SCENARIOS = [
  { id: 'current', name: 'Historical', image: '/Public/HISTORICAL.jpg' },
  { id: 'overgrowth', name: 'Overgrowth', image: '/Public/overgrowth.png' },
  { id: 'degrowth', name: 'Degrowth', image: '/Public/degrowth.png' },
  { id: 'continuity', name: 'Continuity', image: '/Public/continuity.png' },
  { id: 'density', name: 'Density', image: '/Public/density.png' },
];

export default function KpiGrid({ activeScenario, activeTab, selectedYear, overlayEnabled, onOverlayToggle }) {
  const [hoverCard, setHoverCard] = useState(null);
  const [isHovering, setIsHovering] = useState(false);

  const kpiData = useMemo(() => {
    if (activeScenario === null) {
      // Generate structure from scenario 0 with empty series — renders axes/grid but no data lines
      try {
        const raw = generateKpiData(0, selectedYear);
        const emptied = {};
        for (const tab of Object.keys(raw)) {
          emptied[tab] = raw[tab].map(kpi => ({ ...kpi, series: [], value: '—', trendValue: '' }));
        }
        return emptied;
      } catch (e) {
        return { main: [], economic: [], social: [], environmental: [], infrastructure: [] };
      }
    }
    try {
      return generateKpiData(activeScenario, selectedYear);
    } catch (e) {
      return { main: [], economic: [], social: [], environmental: [], infrastructure: [] };
    }
  }, [activeScenario, selectedYear]);

  const kpis = kpiData[activeTab] || [];
  const currentScenario = activeScenario !== null ? SCENARIOS[activeScenario] : null;

  const getKpiData = (scenarioIndex) => {
    if (scenarioIndex === null) return {};
    try {
      return generateKpiData(scenarioIndex, selectedYear);
    } catch (e) {
      return {};
    }
  };

  return (
    <>
      <div
        className={`kpi-grid ${isHovering ? 'is-hovering' : ''}`}
        onMouseLeave={() => {
          setIsHovering(false);
          setHoverCard(null);
        }}
      >
        {currentScenario?.image && (
          <div className="scenario-image">
            {currentScenario.image.endsWith('.mp4') ? (
              <video src={currentScenario.image} autoPlay muted loop playsInline
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              <img src={currentScenario.image} alt={currentScenario.name}
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
            )}
          </div>
        )}
        {kpis.map((kpi, index) => {
          const overlayData = buildOverlayDataForKpi(index, activeTab, overlayEnabled, getKpiData, selectedYear);
          return (
            <KpiCard
              key={kpi.title}
              kpi={kpi}
              activeScenario={activeScenario}
              selectedYear={selectedYear}
              overlayData={overlayData}
              isActive={hoverCard === kpi.title}
              onMouseEnter={() => {
                setIsHovering(true);
                setHoverCard(kpi.title);
              }}
              onMouseLeave={() => setHoverCard(null)}
            />
          );
        })}
      </div>
    </>
  );
}
