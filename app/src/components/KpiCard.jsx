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
import DataLabelsPlugin from 'chartjs-plugin-datalabels';
import { getChartType, getChartData, getChartOptions, generateTrendData } from '../utils/chartUtils';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, RadialLinearScale, Filler, Legend, Tooltip, DataLabelsPlugin);

export default function KpiCard({ kpi, activeScenario, selectedYear, overlayData, onMouseEnter, onMouseLeave, isActive }) {
  const trendIcon = kpi.trend === 'up' ? '↗' : kpi.trend === 'down' ? '↘' : '→';
  const type = getChartType(kpi.chartType);
  const useOverlay = overlayData?.datasets?.length > 0 && ['line', 'area', 'bar'].includes(kpi.chartType);

  const isBarOverlay = kpi.chartType === 'bar' && useOverlay;

  const chartData = useMemo(() => {
    if (isBarOverlay) {
      // One bar per scenario at the selected year — direct comparison view
      const labels = overlayData.datasets.map((ds) => ds.label);
      const values = overlayData.datasets.map((ds) => {
        const vals = ds.data.filter((v) => v != null);
        return vals[vals.length - 1] ?? 0;
      });
      const colors = overlayData.datasets.map((ds) => ds.borderColor);
      return {
        labels,
        datasets: [{
          label: kpi.title,
          data: values,
          backgroundColor: colors.map((c) => c + 'BB'),
          borderColor: colors,
          borderWidth: 1,
          borderRadius: 6,
          borderSkipped: false,
        }],
      };
    }
    if (useOverlay) {
      return {
        labels: overlayData.labels,
        datasets: overlayData.datasets.map((ds) => ({
          ...ds,
          fill: false,
          borderRadius: 0,
          borderSkipped: false,
        })),
      };
    }
    const data = generateTrendData(kpi.value, kpi.trend, 10, kpi, activeScenario, selectedYear);
    return getChartData(data, kpi, activeScenario);
  }, [kpi, activeScenario, selectedYear, overlayData, useOverlay, isBarOverlay]);

  const scaleData = useMemo(() => {
    if (isBarOverlay) {
      return overlayData.datasets.map((ds) => {
        const vals = ds.data.filter((v) => v != null);
        return { value: vals[vals.length - 1] ?? 0 };
      });
    }
    if (useOverlay) return overlayData.datasets.flatMap((ds) => ds.data).filter((v) => v != null && typeof v === 'number').map((v) => ({ value: v }));
    const data = generateTrendData(kpi.value, kpi.trend, 10, kpi, activeScenario, selectedYear);
    return data;
  }, [kpi, activeScenario, selectedYear, overlayData, useOverlay, isBarOverlay]);

  const options = useMemo(() => {
    const base = getChartOptions(kpi.chartType, kpi, scaleData);
    if (isBarOverlay) {
      return {
        ...base,
        plugins: {
          ...base.plugins,
          legend: { display: false },
          tooltip: { ...base.plugins.tooltip, callbacks: {
            label: (ctx) => {
              const v = ctx.raw;
              return typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 1 }) + (kpi.unit ? ' ' + kpi.unit : '') : v;
            },
          }},
          datalabels: {
            anchor: 'end', align: 'end',
            color: '#aaa',
            font: { size: 10 },
            formatter: (v) => typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : v,
          },
        },
      };
    }
    return {
      ...base,
      plugins: {
        ...base.plugins,
        legend: useOverlay ? { display: true, position: 'bottom', labels: { color: '#888', font: { size: 10 }, usePointStyle: true, padding: 10 } } : base.plugins.legend,
      },
    };
  }, [kpi, scaleData, useOverlay, isBarOverlay]);

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
