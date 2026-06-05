import { useMemo } from 'react';
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

const STAT_CARDS = [
  { label: 'TOTAL POPULATION',  value: '87,097',  unit: 'residents',        color: '#f97316' },
  { label: 'PEAK HEX DENSITY',  value: '399',     unit: 'residents per cell',color: '#ef4444' },
  { label: 'H3 HEXAGONS',       value: '10,299',  unit: '4,547 populated',   color: '#a855f7' },
  { label: 'MEDIAN DENSITY',    value: '2.7',     unit: 'residents per cell',color: '#3b82f6' },
];

// Approximate band data (will be replaced by live computation when map loads)
const BAND_LABELS  = ['0', '1–5', '6–15', '16–40', '41–80', '81–150', '151–250', '251+'];
const BAND_COLORS  = ['#374151','#1e3a8a','#1d4ed8','#4f46e5','#7c3aed','#c026d3','#f97316','#fbbf24'];
const BAND_POP_EST = [0, 8200, 9100, 14200, 12800, 10500, 14000, 18300]; // rough estimates

export default function PopulationKpis({ bandStats }) {
  const bStats = bandStats || BAND_LABELS.map((l, i) => ({ label: l, totalPop: BAND_POP_EST[i], color: BAND_COLORS[i] }));

  const barData = {
    labels: bStats.map(b => b.label),
    datasets: [{
      label: 'Residents',
      data:  bStats.map(b => b.totalPop),
      backgroundColor: bStats.map(b => b.color),
      borderRadius: 3,
      borderSkipped: false,
    }],
  };
  const barOptions = {
    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y.toLocaleString()} residents` } } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#9ca3af', font: { size: 9, family: 'IBM Plex Mono' } } },
      y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#9ca3af', font: { size: 9 }, callback: v => v >= 1000 ? (v/1000).toFixed(0)+'k' : v } },
    },
  };

  // Gradient legend
  const gradData = {
    labels: BAND_LABELS,
    datasets: [{
      label: 'Hexagons',
      data: [5752, 2100, 980, 640, 420, 280, 130, 47], // approximate counts
      backgroundColor: BAND_COLORS,
      borderRadius: 3,
      borderSkipped: false,
    }],
  };

  return (
    <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
      {STAT_CARDS.map(({ label, value, unit, color }) => (
        <div key={label} className="kpi-card" style={{ borderTop: `3px solid ${color}` }}>
          <div className="title">{label}</div>
          <div className="value-container">
            <div className="value">{value}</div>
            <div className="unit">{unit}</div>
          </div>
          {/* Color ramp bar as visual */}
          <div className="chart" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', paddingBottom: 8 }}>
            <div style={{ height: 12, borderRadius: 4, background: 'linear-gradient(to right, #172554, #1d4ed8, #7c3aed, #f97316, #fbbf24)', marginBottom: 8 }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#555', fontFamily: 'IBM Plex Mono,monospace' }}>
              <span>Low density</span><span>High density</span>
            </div>
          </div>
          <div className="trend stable"><span>→</span><span>2024 baseline</span></div>
        </div>
      ))}
      <div className="kpi-card" style={{ borderTop: '3px solid #6b7280', gridColumn: 'span 2' }}>
        <div className="title">POPULATION BY DENSITY BAND</div>
        <div className="value-container"><div className="value" style={{ fontSize: '1.2rem' }}>Distribution</div></div>
        <div className="chart">
          <Bar data={barData} options={barOptions} />
        </div>
        <div className="trend stable"><span>→</span><span>residents per H3 cell range</span></div>
      </div>
      <div className="kpi-card" style={{ borderTop: '3px solid #6b7280', gridColumn: 'span 2' }}>
        <div className="title">HEX COUNT BY DENSITY BAND</div>
        <div className="value-container"><div className="value" style={{ fontSize: '1.2rem' }}>10,299 cells</div></div>
        <div className="chart">
          <Bar data={gradData} options={{ ...barOptions, plugins: { ...barOptions.plugins, tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y.toLocaleString()} hexagons` } } } }} />
        </div>
        <div className="trend stable"><span>→</span><span>hexagon count per density band</span></div>
      </div>
    </div>
  );
}
