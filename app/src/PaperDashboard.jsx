import React, { useMemo, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  RadialLinearScale,
  Filler,
  Legend,
  Tooltip,
} from 'chart.js';
import { Line, Radar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, RadialLinearScale, Filler, Legend, Tooltip);

const SCENARIOS = [
  { key: 'overgrowth', label: 'Overgrowth', color: '#bd0638' },
  { key: 'degrowth', label: 'Degrowth', color: '#076f37' },
  { key: 'continuity', label: 'Continuity', color: '#294daf' },
  { key: 'density', label: 'Density', color: '#eab308' },
];

const PROJ_YEARS = Array.from({ length: 25 }, (_, i) => (2025 + i).toString());
const HIST_YEARS = ['2010','2011','2012','2013','2014','2015','2016','2017','2018','2019','2020','2021','2022','2023','2024'];
const ALL_YEARS  = [...HIST_YEARS, ...PROJ_YEARS];

function getScenarioData() {
  if (typeof window === 'undefined' || !window.scenarioData) return null;
  return window.scenarioData;
}

function buildTimeSeriesDataset(scenarioData, indicatorKey, labelFn, transform = (v) => v) {
  const datasets = [];

  // Historical baseline (grey dashed)
  const hist = scenarioData.current?.historicalData?.[indicatorKey];
  if (hist?.series?.length) {
    const histYears = hist.years ?? HIST_YEARS.slice(-hist.series.length);
    // Pad to full HIST_YEARS length with nulls
    const histData = HIST_YEARS.map((y) => {
      const idx = histYears.indexOf(y);
      if (idx === -1) return null;
      const v = hist.series[idx];
      return v == null ? null : transform(v);
    });
    // Add null spacers for projection years
    const full = [...histData, ...Array(25).fill(null)];
    datasets.push({
      label: 'Historical',
      data: full,
      borderColor: '#9ca3af',
      backgroundColor: 'transparent',
      borderWidth: 2,
      borderDash: [5, 4],
      tension: 0.3,
      pointRadius: 2.5,
      pointHoverRadius: 4,
      fill: false,
    });
  }

  // Scenario projections (one line per scenario)
  for (const s of SCENARIOS) {
    const scenario = scenarioData[s.key];
    const ts = scenario?.timeseriesData?.[indicatorKey];
    if (!ts?.series || ts.series.length === 0) continue;
    // Pad with nulls for historical years, then projection values
    const projData = ts.series.map((v) => (v == null ? null : transform(v)));
    const full = [...Array(15).fill(null), ...projData];
    datasets.push({
      label: s.label,
      data: full,
      borderColor: s.color,
      backgroundColor: s.color + '18',
      borderWidth: 2.5,
      tension: 0.3,
      pointRadius: (ctx) => (ctx.dataIndex < 15 ? 0 : 3),
      pointHoverRadius: 5,
      fill: false,
    });
  }
  return { labels: ALL_YEARS, datasets };
}

function exportChartPng(ref, filename) {
  const chart = ref.current;
  if (!chart) return;
  const url = chart.toBase64Image('image/png', 1);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
}

export default function PaperDashboard() {
  const scenarioData = getScenarioData();

  const popRef = useRef(null);
  const gdpRef = useRef(null);
  const forestRef = useRef(null);
  const co2Ref = useRef(null);
  const radarRef = useRef(null);

  const populationSeries = useMemo(
    () => (scenarioData ? buildTimeSeriesDataset(scenarioData, 'Pop', () => 'Population', (v) => v / 1000) : null),
    [scenarioData],
  );
  const gdpSeries = useMemo(
    () => (scenarioData ? buildTimeSeriesDataset(scenarioData, 'GDPpc', () => 'GDP per Capita', (v) => v) : null),
    [scenarioData],
  );
  const forestSeries = useMemo(
    () => (scenarioData ? buildTimeSeriesDataset(scenarioData, 'NatCov', () => 'Natural Coverage', (v) => v * 100) : null),
    [scenarioData],
  );
  const co2Series = useMemo(
    () => (scenarioData ? buildTimeSeriesDataset(scenarioData, 'CO2_total', () => 'Total CO₂ Emissions', (v) => v / 1000) : null),
    [scenarioData],
  );

  const radarData = useMemo(() => {
    if (!scenarioData) return null;
    // Use last year in the timeseries (works for any horizon)
    const firstScenario = scenarioData[SCENARIOS[0]?.key];
    const firstTs = firstScenario?.timeseriesData?.['Pop'];
    const yearIndex = firstTs ? firstTs.series.length - 1 : 24;
    const endYear = firstTs?.years?.[yearIndex] ?? '2049';
    const indicators = [
      { key: 'GDPpc', label: 'GDP per Capita' },
      { key: 'GDP', label: 'Total GDP' },
      { key: 'CO2pc', label: 'CO₂ per Capita' },
      { key: 'AQI', label: 'Air Quality (AQI)' },
      { key: 'NatCov', label: 'Natural Coverage' },
      { key: 'WaterSecurityIndex', label: 'Water Security' },
      { key: 'WLB', label: 'Work–Life Balance' },
      { key: 'Access', label: 'Access to Health' },
    ];
    const labels = indicators.map((i) => i.label);
    // Baseline (2024) from current scenario
    const baseline = scenarioData.current || {};
    // Collect raw values for baseline + each scenario
    const allSeries = [{ key: 'current', label: 'Baseline 2024', color: '#9ca3af' }, ...SCENARIOS];
    const rawMatrix = allSeries.map((s) => {
      if (s.key === 'current') {
        return indicators.map((ind) => {
          let v = baseline[ind.key];
          if (v == null && baseline.historicalData?.[ind.key]?.series?.length) {
            const arr = baseline.historicalData[ind.key].series;
            v = arr[arr.length - 1];
          }
          if (v == null) return null;
          if (ind.key === 'NatCov' || ind.key === 'WLB' || ind.key === 'Access') v = v * 100;
          if (ind.key === 'WaterSecurityIndex') v = v * 100;
          return v;
        });
      }
      const scenario = scenarioData[s.key];
      return indicators.map((ind) => {
        const ts = scenario?.timeseriesData?.[ind.key];
        if (!ts?.series || ts.series.length <= yearIndex) return null;
        let v = ts.series[yearIndex];
        if (ind.key === 'NatCov' || ind.key === 'WLB' || ind.key === 'Access') v = v * 100;
        if (ind.key === 'WaterSecurityIndex') v = v * 100;
        return v;
      });
    });
    // Normalize each indicator column to 0–100 for comparability.
    // CO2pc and AQI are inverted so higher = better.
    const normalizedMatrix = rawMatrix.map((row) =>
      row.map((v, colIdx) => {
        if (v == null) return 0;
        const ind = indicators[colIdx];
        const colValues = rawMatrix.map((r) => r[colIdx]).filter((x) => x != null && isFinite(x));
        if (colValues.length === 0) return 0;
        const min = Math.min(...colValues);
        const max = Math.max(...colValues);
        if (max === min) return 50;
        if (ind.key === 'CO2pc' || ind.key === 'AQI') {
          // lower is better
          return ((max - v) / (max - min)) * 100;
        }
        return ((v - min) / (max - min)) * 100;
      }),
    );
    const datasets = allSeries.map((s, i) => ({
      label: s.label,
      data: normalizedMatrix[i],
      borderColor: s.color,
      backgroundColor: s.color === '#9ca3af' ? s.color + '40' : s.color + '30',
      borderWidth: s.key === 'current' ? 2.5 : 2,
      borderDash: s.key === 'current' ? [4, 4] : undefined,
      pointRadius: 3,
    }));
    return { labels, datasets };
  }, [scenarioData]);

  const baseLineOptions = (yTitle, unit) => ({
    responsive: true,
    maintainAspectRatio: false,
    devicePixelRatio: 3,
    plugins: {
      legend: { display: true, position: 'bottom', labels: { color: '#111', font: { size: 11 }, usePointStyle: true } },
      tooltip: {
        backgroundColor: '#ffffff',
        titleColor: '#111',
        bodyColor: '#111',
        borderColor: '#ccc',
        borderWidth: 1,
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed.y;
            const base = typeof v === 'number' ? v.toFixed(2) : v;
            return `${ctx.dataset.label}: ${base}${unit ? ` ${unit}` : ''}`;
          },
        },
      },
      title: { display: true, text: yTitle, color: '#111', font: { size: 14, weight: '600' } },
    },
    interaction: { mode: 'nearest', intersect: false },
    scales: {
      x: {
        grid: { color: '#eee' },
        ticks: {
          color: '#444', font: { size: 10 },
          callback: (val, idx) => (ALL_YEARS[idx] % 5 === 0 ? ALL_YEARS[idx] : ''),
          maxRotation: 0,
        },
      },
      y: {
        grid: { color: '#eee' },
        ticks: { color: '#444', font: { size: 10 } },
      },
    },
  });

  const forestOptions = {
    ...baseLineOptions('Natural coverage (% of territory)', '%'),
    scales: {
      x: { grid: { color: '#eee' }, ticks: { color: '#444', font: { size: 10 } } },
      y: {
        grid: { color: '#eee' },
        ticks: { color: '#444', font: { size: 10 }, stepSize: 5 },
        suggestedMin: 80,
        suggestedMax: 100,
      },
    },
  };

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    devicePixelRatio: 3,
    plugins: {
      legend: { display: true, position: 'bottom', labels: { color: '#111', font: { size: 11 } } },
      title: { display: true, text: 'Scenario comparison (2049)', color: '#111', font: { size: 14, weight: '600' } },
      tooltip: {
        backgroundColor: '#ffffff',
        titleColor: '#111',
        bodyColor: '#111',
        borderColor: '#ccc',
        borderWidth: 1,
      },
    },
    scales: {
      r: {
        angleLines: { color: '#ddd' },
        grid: { color: '#eee' },
        pointLabels: { color: '#111', font: { size: 12 } },
        ticks: { color: '#666', backdropColor: 'transparent' },
      },
    },
  };

  if (!scenarioData) {
    return (
      <div style={{ padding: '2rem', fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif' }}>
        Scenario data not loaded. Make sure `scenarioData.js` is included before the bundle.
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        padding: '2rem',
        backgroundColor: '#ffffff',
        color: '#111',
        fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
      }}
    >
      <h1 style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>Andorra scenarios – publication charts</h1>
      <p style={{ marginBottom: '0.75rem', maxWidth: '52rem', fontSize: '0.95rem', color: '#555' }}>
        Time series and radar plots prepared for high-quality export. Use the export buttons under each chart to download PNG images for your paper.
      </p>
      <p style={{ marginBottom: '2rem', maxWidth: '52rem', fontSize: '0.9rem', color: '#555', lineHeight: 1.5 }}>
        Time-series trajectories (2010–2049) for selected KPIs across scenarios. Historical values (2010–2024, grey dashed) provide calibration context;
        projections (2025–2049) are scenario outputs. Panels show: (a) population, (b) GDP per capita, (c) natural coverage, and (d)
        total CO₂ emissions.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '1.75rem', marginBottom: '2rem' }}>
        <div style={{ background: '#fff', borderRadius: '1rem', padding: '1.5rem', boxShadow: '0 6px 16px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb' }}>
          <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Population (thousands)</div>
          <div style={{ height: 320 }}>
            {populationSeries && <Line ref={popRef} data={populationSeries} options={baseLineOptions('Population (thousands)', 'k people')} />}
          </div>
          <button
            type="button"
            onClick={() => exportChartPng(popRef, 'population_scenarios_2025_2049.png')}
            style={{ marginTop: '0.75rem', fontSize: '0.8rem', padding: '0.4rem 0.9rem', borderRadius: '999px', border: '1px solid #d4d4d8', background: '#f9fafb', cursor: 'pointer' }}
          >
            Export PNG
          </button>
          {populationSeries && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#555' }}>
              <div style={{ fontWeight: 500, marginBottom: '0.25rem' }}>2049 population (thousands):</div>
              {populationSeries.datasets.map((ds, i) => (
                <div key={ds.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{ds.label}</span>
                  <span>{typeof ds.data[ds.data.length - 1] === 'number' ? ds.data[ds.data.length - 1].toFixed(1) : ds.data[ds.data.length - 1]}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ background: '#fff', borderRadius: '1rem', padding: '1.5rem', boxShadow: '0 6px 16px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb' }}>
          <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>GDP per capita (USD)</div>
          <div style={{ height: 320 }}>
            {gdpSeries && <Line ref={gdpRef} data={gdpSeries} options={baseLineOptions('GDP per capita (USD)', '$')} />}
          </div>
          <button
            type="button"
            onClick={() => exportChartPng(gdpRef, 'gdp_per_capita_scenarios_2025_2049.png')}
            style={{ marginTop: '0.75rem', fontSize: '0.8rem', padding: '0.4rem 0.9rem', borderRadius: '999px', border: '1px solid #d4d4d8', background: '#f9fafb', cursor: 'pointer' }}
          >
            Export PNG
          </button>
          {gdpSeries && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#555' }}>
              <div style={{ fontWeight: 500, marginBottom: '0.25rem' }}>2049 GDP per capita (USD):</div>
              {gdpSeries.datasets.map((ds) => (
                <div key={ds.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{ds.label}</span>
                  <span>{typeof ds.data[ds.data.length - 1] === 'number' ? ds.data[ds.data.length - 1].toFixed(0) : ds.data[ds.data.length - 1]}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ background: '#fff', borderRadius: '1rem', padding: '1.5rem', boxShadow: '0 6px 16px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb' }}>
          <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Natural coverage (% of territory)</div>
          <div style={{ height: 320 }}>
            {forestSeries && <Line ref={forestRef} data={forestSeries} options={forestOptions} />}
          </div>
          <button
            type="button"
            onClick={() => exportChartPng(forestRef, 'forest_coverage_scenarios_2025_2049.png')}
            style={{ marginTop: '0.75rem', fontSize: '0.8rem', padding: '0.4rem 0.9rem', borderRadius: '999px', border: '1px solid #d4d4d8', background: '#f9fafb', cursor: 'pointer' }}
          >
            Export PNG
          </button>
          {forestSeries && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#555' }}>
              <div style={{ fontWeight: 500, marginBottom: '0.25rem' }}>2049 natural coverage (%):</div>
              {forestSeries.datasets.map((ds) => (
                <div key={ds.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{ds.label}</span>
                  <span>{typeof ds.data[ds.data.length - 1] === 'number' ? ds.data[ds.data.length - 1].toFixed(2) : ds.data[ds.data.length - 1]}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ background: '#fff', borderRadius: '1rem', padding: '1.5rem', boxShadow: '0 6px 16px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb' }}>
          <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Total CO₂ emissions (kt)</div>
          <div style={{ height: 320 }}>
            {co2Series && <Line ref={co2Ref} data={co2Series} options={baseLineOptions('Total CO₂ emissions (kt)', 'kt')} />}
          </div>
          <button
            type="button"
            onClick={() => exportChartPng(co2Ref, 'co2_total_scenarios_2025_2049.png')}
            style={{ marginTop: '0.75rem', fontSize: '0.8rem', padding: '0.4rem 0.9rem', borderRadius: '999px', border: '1px solid #d4d4d8', background: '#f9fafb', cursor: 'pointer' }}
          >
            Export PNG
          </button>
          {co2Series && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#555' }}>
              <div style={{ fontWeight: 500, marginBottom: '0.25rem' }}>2049 total CO₂ emissions (kt):</div>
              {co2Series.datasets.map((ds) => (
                <div key={ds.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{ds.label}</span>
                  <span>{typeof ds.data[ds.data.length - 1] === 'number' ? ds.data[ds.data.length - 1].toFixed(0) : ds.data[ds.data.length - 1]}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{ background: '#fff', borderRadius: '1rem', padding: '1.5rem', boxShadow: '0 6px 16px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb', maxWidth: '52rem' }}>
        <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Scenario comparison – key indicators in 2049</div>
        <div style={{ height: 360 }}>
          {radarData && <Radar ref={radarRef} data={radarData} options={radarOptions} />}
        </div>
        <button
          type="button"
          onClick={() => exportChartPng(radarRef, 'scenario_radar_comparison_2049.png')}
          style={{ marginTop: '0.75rem', fontSize: '0.8rem', padding: '0.4rem 0.9rem', borderRadius: '999px', border: '1px solid #d4d4d8', background: '#f9fafb', cursor: 'pointer' }}
        >
          Export PNG
        </button>
        <p style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: '#555', lineHeight: 1.4 }}>
          Cross-scenario comparison (2049): radar plot comparing scenario endpoints against the 2024 baseline across eight indicators
          (min–max normalized across baseline and scenarios). CO₂ and AQI are inverted so higher scores reflect better environmental outcomes.
          Indicators: GDPpc, GDP, CO₂, AQI, NatCov, WaterSec, WLB, Access.
        </p>
      </div>
    </div>
  );
}

