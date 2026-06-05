import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  RadialLinearScale,
  Filler,
  Legend,
  Tooltip,
} from 'chart.js';
import { Line, Bar, Doughnut, Radar } from 'react-chartjs-2';
import { getChartType, getChartData, getChartOptions, generateTrendData } from '../utils/chartUtils';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, RadialLinearScale, Filler, Legend, Tooltip);

export default function KpiCard({ kpi, activeScenario, selectedYear, overlayData, onMouseEnter, onMouseLeave, isActive }) {
  const trendIcon = kpi.trend === 'up' ? '↗' : kpi.trend === 'down' ? '↘' : '→';
  const type = getChartType(kpi.chartType);
  const useOverlay = overlayData?.datasets?.length > 0 && ['line', 'area', 'bar'].includes(kpi.chartType);

  const chartData = useMemo(() => {
    if (useOverlay) {
      return {
        labels: overlayData.labels,
        datasets: overlayData.datasets.map((ds) => ({
          ...ds,
          fill: false,
          borderRadius: kpi.chartType === 'bar' ? 4 : 0,
          borderSkipped: false,
        })),
      };
    }
    const data = generateTrendData(kpi.value, kpi.trend, 10, kpi, activeScenario, selectedYear);
    return getChartData(data, kpi, activeScenario);
  }, [kpi, activeScenario, selectedYear, overlayData, useOverlay]);

  const scaleData = useMemo(() => {
    if (useOverlay) return overlayData.datasets.flatMap((ds) => ds.data).filter((v) => v != null && typeof v === 'number').map((v) => ({ value: v }));
    const data = generateTrendData(kpi.value, kpi.trend, 10, kpi, activeScenario, selectedYear);
    return data;
  }, [kpi, activeScenario, selectedYear, overlayData, useOverlay]);

  const options = useMemo(() => {
    const base = getChartOptions(kpi.chartType, kpi, scaleData);
    return {
      ...base,
      plugins: {
        ...base.plugins,
        legend: useOverlay ? { display: true, position: 'bottom', labels: { color: '#888', font: { size: 10 }, usePointStyle: true, padding: 10 } } : base.plugins.legend,
      },
    };
  }, [kpi, scaleData, useOverlay]);

  const ChartComponent = type === 'line' ? Line : type === 'bar' ? Bar : type === 'doughnut' ? Doughnut : Radar;
  const chartHeight = kpi.chartType === 'pentagon' ? 300 : 200;

  return (
    <div
      className={`kpi-card ${isActive ? 'is-active' : ''}`}
      data-kpi-title={kpi.title}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="title">{kpi.title}</div>
      <div className="value-container">
        <div className="value">{kpi.value}</div>
        {kpi.unit && <div className="unit">{kpi.unit}</div>}
      </div>
      <div className={`chart ${kpi.chartType === 'pentagon' ? 'radar' : ''}`} style={{ height: chartHeight }}>
        <ChartComponent key={kpi.title} data={chartData} options={options} />
      </div>
      <div className={`trend ${kpi.trend}`}>
        <span>{trendIcon}</span>
        <span>{kpi.trendValue}</span>
      </div>
    </div>
  );
}
