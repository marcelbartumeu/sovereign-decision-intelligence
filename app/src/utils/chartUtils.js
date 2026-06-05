/**
 * Chart.js helpers: getChartType, getChartData, getChartOptions, generateTrendData, buildOverlayDataForKpi
 */

const SPAIN_TARGETS = {
  Salary: [1878.4, 1897.98, 1886.3, 1887.8, 1883.82, 1904.21, 1898.17, 1900.58, 1916.94, 1954.19, 1903.13, 2020.73, 2112.77, 2212.99, 2296.56],
  GDPpc: [30532, 31678, 28323, 29068, 22780, 23440, 24190, 25160, 25950, 26620, 23850, 26090, 28790, 30980, 32630],
  HPrice: [800, 750, 720, 700, 690, 700, 710, 725, 732, 750, 780, 820, 850, 900, 950],
  Emp: [61.1, 62.1, 63.2, 64.5, 66.2, 67.3, 65.8, 67.0, 68.6, 70.0, 71.4],
};

export function getChartType(chartType) {
  const mapping = { area: 'line', bar: 'bar', pie: 'pie', radial: 'doughnut', line: 'line', pentagon: 'radar' };
  return mapping[chartType] || 'line';
}

export function generateTrendData(baseValue, trend, points, kpi, activeScenario, selectedYear) {
  if (kpi?.series && Array.isArray(kpi.series)) {
    const len = kpi.series.length;
    const startYear = activeScenario === 0
      ? (len === 15 ? 2010 : 2014)
      : (len >= 12 ? 2024 : 2025);
    const endIndex = Math.min(len, Math.max(1, selectedYear - startYear + 1));
    const filteredSeries = kpi.series.slice(0, endIndex);
    return filteredSeries.map((value, i) => {
      let target = value * 1.05;
      const currentYear = startYear + i;
      if (activeScenario === 0 && kpi?.title) {
        if (kpi.title === 'Housing Price' && currentYear >= 2010 && currentYear <= 2024 && SPAIN_TARGETS.HPrice[currentYear - 2010] != null) target = SPAIN_TARGETS.HPrice[currentYear - 2010];
        else if (kpi.title === 'GDP per Capita' && currentYear >= 2010 && currentYear <= 2024 && SPAIN_TARGETS.GDPpc[currentYear - 2010] != null) target = SPAIN_TARGETS.GDPpc[currentYear - 2010];
        else if (kpi.title === 'Monthly Salary' && currentYear >= 2010 && currentYear <= 2024 && SPAIN_TARGETS.Salary[currentYear - 2010] != null) target = SPAIN_TARGETS.Salary[currentYear - 2010];
        else if (kpi.title === 'Employment Rate' && currentYear >= 2014 && currentYear <= 2024 && SPAIN_TARGETS.Emp[currentYear - 2014] != null) target = SPAIN_TARGETS.Emp[currentYear - 2014];
      }
      return { year: currentYear.toString(), value, target, secondary: value * 0.95 };
    });
  }
  const numericValue = parseFloat(String(baseValue).replace(/[^\d.-]/g, '')) || 0;
  const startYear = activeScenario === 0 ? 2014 : 2025;
  const data = [];
  for (let i = 0; i < points; i++) {
    data.push({ year: (startYear + i).toString(), value: numericValue, target: numericValue * 1.1, secondary: numericValue * 0.8 });
  }
  return data;
}

export function getChartData(data, kpi, activeScenario) {
  const years = data.map((d) => d.year);
  const values = data.map((d) => d.value);
  const targets = data.map((d) => d.target);

  switch (kpi.chartType) {
    case 'pie':
      return {
        labels: years,
        datasets: [{ data: values, backgroundColor: [kpi.color, kpi.secondaryColor, kpi.color + '80', kpi.secondaryColor + '80', kpi.color + '40'], borderWidth: 2, borderColor: '#1a1a1a' }],
      };
    case 'radial': {
      const currentValue = values[values.length - 1];
      const percentage = Math.min(100, (currentValue / (kpi.maxValue || 100)) * 100);
      return { labels: [kpi.title], datasets: [{ data: [percentage, 100 - percentage], backgroundColor: [kpi.color, '#333'], borderWidth: 0 }] };
    }
    case 'pentagon': {
      const last5Years = years.slice(-5);
      const last5Values = values.slice(-5);
      const last5Targets = targets.slice(-5);
      const pentagonDatasets = [{ label: 'Actual', data: last5Values, borderColor: kpi.color, backgroundColor: kpi.color + '20', borderWidth: 2, pointRadius: 4, pointBackgroundColor: kpi.color }];
      if (kpi.title === 'Employment Rate' && activeScenario === 0) {
        pentagonDatasets.push({ label: 'Spain', data: last5Targets, borderColor: kpi.secondaryColor, backgroundColor: kpi.secondaryColor + '10', borderWidth: 2, borderDash: [5, 5], pointRadius: 4, pointBackgroundColor: kpi.secondaryColor });
      }
      return { labels: last5Years, datasets: pentagonDatasets };
    }
    case 'bar':
      return { labels: years, datasets: [{ label: 'Value', data: values, backgroundColor: kpi.color + '80', borderColor: kpi.color, borderWidth: 2, borderRadius: 4, borderSkipped: false }] };
    case 'area': {
      const areaDatasets = [{ label: 'Actual', data: values, borderColor: kpi.color, backgroundColor: 'transparent', borderWidth: 2, fill: false, tension: 0.4, pointRadius: 4 }];
      if (kpi.title === 'GDP per Capita' && activeScenario === 0) {
        areaDatasets.push({ label: 'Spain', data: targets, borderColor: kpi.secondaryColor, backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], fill: false, tension: 0.4, pointRadius: 4 });
      }
      return { labels: years, datasets: areaDatasets };
    }
    default: {
      const isEmployment = kpi.title === 'Employment Rate';
      const lineDatasets = [{
        label: isEmployment ? 'Andorra' : 'Actual',
        data: values,
        borderColor: kpi.color,
        backgroundColor: isEmployment ? kpi.color + '18' : 'transparent',
        fill: isEmployment,
        borderWidth: isEmployment ? 2.5 : 2,
        tension: 0.35,
        pointRadius: isEmployment ? 5 : 4,
        pointHoverRadius: isEmployment ? 7 : 5,
        pointBackgroundColor: kpi.color,
        pointBorderColor: '#1a1a1a',
        pointBorderWidth: 1,
      }];
      if (activeScenario === 0 && ['Housing Price', 'GDP per Capita', 'Monthly Salary', 'Employment Rate'].includes(kpi.title)) {
        lineDatasets.push({
          label: 'Spain',
          data: targets,
          borderColor: kpi.secondaryColor,
          backgroundColor: 'transparent',
          borderWidth: 2,
          borderDash: [5, 5],
          tension: 0.35,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: kpi.secondaryColor,
        });
      }
      return { labels: years, datasets: lineDatasets };
    }
  }
}

export function getChartOptions(chartType, kpi, dataForScale) {
  const base = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 600 },
    plugins: {
      legend: { display: chartType === 'pie' || chartType === 'line', position: 'bottom', labels: { color: '#888', font: { size: 10 }, usePointStyle: true, padding: 15 } },
      tooltip: { backgroundColor: '#1a1a1a', titleColor: '#fff', bodyColor: '#fff', borderColor: '#333', borderWidth: 1, cornerRadius: 8 },
    },
    interaction: { mode: (chartType === 'pie' || chartType === 'radial') ? 'nearest' : 'index', intersect: false, axis: (chartType === 'pie' || chartType === 'radial' || chartType === 'pentagon') ? undefined : 'x' },
  };
  if (chartType === 'radial') return { ...base, plugins: { ...base.plugins, legend: { display: false } }, cutout: '60%' };
  if (chartType === 'pentagon') {
    return {
      ...base,
      scales: {
        r: {
          min: 40,
          max: 100,
          angleLines: { color: '#444' },
          grid: { color: '#444' },
          pointLabels: { color: '#ccc', font: { size: 16, weight: '600' }, padding: 25 },
          ticks: { color: '#888', stepSize: 10, callback: (v) => v + '%' },
        },
      },
      layout: { padding: { top: 30, bottom: 20, left: 30, right: 30 } },
    };
  }
  let suggested = {};
  const isEmploymentRate = chartType === 'line' && kpi?.title === 'Employment Rate';
  // Employment Rate and other % KPIs with maxValue 100: use fixed 0–100% scale for clarity
  if (chartType === 'line' && kpi?.maxValue === 100 && kpi?.unit === '%') {
    suggested = {
      suggestedMin: 0,
      suggestedMax: 100,
      ...(isEmploymentRate ? { ticks: { stepSize: 25, callback: (v) => v + '%' } } : {}),
    };
  } else if ((chartType === 'line' || chartType === 'area' || chartType === 'bar') && Array.isArray(dataForScale)) {
    const values = dataForScale.map((d) => d.value).filter((v) => typeof v === 'number' && isFinite(v));
    if (values.length > 0) {
      const minV = Math.min(...values);
      const maxV = Math.max(...values);
      const padding = (maxV - minV) * 0.1 || (minV || 1) * 0.05;
      suggested = { suggestedMin: Math.max(0, minV - padding), suggestedMax: maxV + padding };
    }
  }
  const scales = {
    x: { display: true, grid: { color: '#333' }, ticks: { color: '#888', font: { size: 10 }, maxRotation: 45 } },
    y: { display: true, grid: { color: '#333' }, ticks: { color: '#888', font: { size: 10 } }, ...suggested },
  };
  const plugins = { ...base.plugins };
  if (isEmploymentRate) {
    plugins.tooltip = {
      ...base.plugins.tooltip,
      callbacks: {
        ...base.plugins.tooltip?.callbacks,
        label: (ctx) => `${ctx.dataset.label}: ${typeof ctx.raw === 'number' ? ctx.raw.toFixed(1) : ctx.raw}%`,
      },
    };
  }
  return {
    ...base,
    plugins,
    scales,
  };
}

export const OVERLAY_SCENARIOS = [
  { index: 0, label: 'Historical', color: '#9ca3af' },
  { index: 1, label: 'Overgrowth', color: '#bd0638' },
  { index: 2, label: 'Degrowth', color: '#076f37' },
  { index: 3, label: 'Continuity', color: '#294daf' },
  { index: 4, label: 'Density', color: '#eab308' },
];

export function buildOverlayDataForKpi(kpiIndex, activeTab, overlayEnabled, getKpiData, selectedYear = 2049) {
  const enabledIndices = OVERLAY_SCENARIOS.filter((s) => overlayEnabled[s.index]).map((s) => s.index);
  if (enabledIndices.length === 0) return null;
  const allYears = [];
  for (let y = 2010; y <= 2049; y++) allYears.push(y.toString());
  const maxYear = Math.min(2049, Math.max(2010, selectedYear));
  const yearIndex = maxYear - 2010;
  const labels = allYears.slice(0, yearIndex + 1);
  const datasets = [];
  for (const idx of enabledIndices) {
    const kpiData = getKpiData(idx);
    const kpis = kpiData[activeTab];
    if (!kpis?.[kpiIndex]) continue;
    const kpi = kpis[kpiIndex];
    const series = kpi.series;
    if (!series?.length) continue;
    const startYear = idx === 0 ? (series.length === 15 ? 2010 : 2014) : 2024;
    const fullData = allYears.map((yr) => {
      const y = parseInt(yr, 10);
      const pos = y - startYear;
      return pos >= 0 && pos < series.length ? series[pos] : null;
    });
    const data = fullData.slice(0, yearIndex + 1);
    const cfg = OVERLAY_SCENARIOS.find((s) => s.index === idx);
    datasets.push({
      label: cfg?.label ?? `Scenario ${idx}`,
      data,
      borderColor: cfg?.color ?? '#888',
      backgroundColor: 'transparent',
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 3,
      pointBackgroundColor: cfg?.color ?? '#888',
    });
  }
  return { labels, datasets };
}
