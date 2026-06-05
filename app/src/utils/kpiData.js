const scenarioData = typeof window !== 'undefined' && window.scenarioData ? window.scenarioData : {};

/**
 * Generate KPI data from scenarioData for a given scenario and selected year.
 * @param {number} scenarioIndex - Index in [current, overgrowth, degrowth, continuity, density]
 * @param {number} selectedYear - Year to resolve values for (e.g. 2024 or 2035)
 * @returns {{ main: Array, economic: Array, social: Array, environmental: Array, infrastructure: Array }}
 */
export function generateKpiData(scenarioIndex, selectedYear) {
    const scenarioNames = ['current', 'overgrowth', 'degrowth', 'continuity', 'density'];
    const scenarioName = scenarioNames[scenarioIndex];
    const data = scenarioData[scenarioName];
    const currentData = scenarioData['current']; // Always have access to historical scenario for 2024 baseline

    if (!data) return { main: [], economic: [], social: [], environmental: [], infrastructure: [] };

    const formatNumber = (value, decimals = 0) => {
        if (typeof value === 'number') {
            return value.toLocaleString('en-US', {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals
            });
        }
        return value.toString();
    };

    // Compute YoY % change for a raw series at the selected year
    const computeTrend = (rawSeries) => {
        if (!Array.isArray(rawSeries) || rawSeries.length < 2) return { trend: 'stable', trendValue: '±0%' };
        const startYear = scenarioName === 'current'
            ? (rawSeries.length === 15 ? 2010 : 2014)
            : 2024;
        const idx = Math.max(0, Math.min(rawSeries.length - 1, selectedYear - startYear));
        if (idx === 0) return { trend: 'stable', trendValue: '±0%' };
        const curr = rawSeries[idx];
        const prev = rawSeries[idx - 1];
        if (curr == null || prev == null || prev === 0) return { trend: 'stable', trendValue: '±0%' };
        const pct = ((curr - prev) / Math.abs(prev)) * 100;
        const sign = pct >= 0 ? '+' : '';
        const trendValue = `${sign}${pct.toFixed(1)}%`;
        const trend = Math.abs(pct) < 0.05 ? 'stable' : pct > 0 ? 'up' : 'down';
        return { trend, trendValue };
    };

    const getHistoricalSeries = (key) => {
        if (key === 'sForeignBorn') {
            let foreignBornSeries, popSeries;

            if (scenarioName === 'current' && data.historicalData) {
                foreignBornSeries = data.historicalData['ForeignBorn']?.series;
                popSeries = data.historicalData['Pop']?.series;
            } else if (data.timeseriesData) {
                foreignBornSeries = data.timeseriesData['ForeignBorn']?.series;
                popSeries = data.timeseriesData['Pop']?.series;

                if (foreignBornSeries && popSeries && currentData && currentData.historicalData) {
                    const currentForeignBorn = currentData.historicalData['ForeignBorn']?.series;
                    const currentPop = currentData.historicalData['Pop']?.series;
                    if (currentForeignBorn && currentPop && currentForeignBorn.length > 0 && currentPop.length > 0) {
                        const lastIndex = currentForeignBorn.length - 1;
                        foreignBornSeries = [currentForeignBorn[lastIndex], ...foreignBornSeries];
                        popSeries = [currentPop[lastIndex], ...popSeries];
                    }
                }
            }

            if (foreignBornSeries && popSeries && Array.isArray(foreignBornSeries) && Array.isArray(popSeries)) {
                if (scenarioName !== 'current' && foreignBornSeries.length >= 2 && foreignBornSeries.length < 12) {
                    const lastFB = foreignBornSeries[foreignBornSeries.length - 1];
                    const secondLastFB = foreignBornSeries[foreignBornSeries.length - 2];
                    const growthRateFB = (lastFB - secondLastFB) / Math.abs(secondLastFB);
                    foreignBornSeries = [...foreignBornSeries, lastFB * (1 + growthRateFB)];
                }
                if (scenarioName !== 'current' && popSeries.length >= 2 && popSeries.length < 12) {
                    const lastPop = popSeries[popSeries.length - 1];
                    const secondLastPop = popSeries[popSeries.length - 2];
                    const growthRatePop = (lastPop - secondLastPop) / Math.abs(secondLastPop);
                    popSeries = [...popSeries, lastPop * (1 + growthRatePop)];
                }

                const minLength = Math.min(foreignBornSeries.length, popSeries.length);
                return foreignBornSeries.slice(0, minLength).map((foreignBorn, i) => {
                    if (popSeries[i] > 0) {
                        return foreignBorn / popSeries[i];
                    }
                    return 0;
                });
            }
            return null;
        }

        if (scenarioName === 'current' && data.historicalData && data.historicalData[key]) {
            return data.historicalData[key].series;
        } else if (data.timeseriesData && data.timeseriesData[key]) {
            let series = data.timeseriesData[key].series;
            if (scenarioName !== 'current' && Array.isArray(series)) {
                const baseline2024 = currentData?.historicalData?.[key]?.series?.length > 0
                    ? currentData.historicalData[key].series[currentData.historicalData[key].series.length - 1]
                    : (currentData && key in currentData ? currentData[key] : null);
                if (baseline2024 != null) {
                    series = [baseline2024, ...series];
                }
                if (series.length >= 2 && series.length < 12) {
                    const lastValue = series[series.length - 1];
                    const secondLastValue = series[series.length - 2];
                    const growthRate = (lastValue - secondLastValue) / Math.abs(secondLastValue);
                    series = [...series, lastValue * (1 + growthRate)];
                }
            }
            return series;
        }
        return null;
    };

    const getValueForYear = (key) => {
        if (key === 'sForeignBorn') {
            let foreignBornSeries, popSeries;

            if (scenarioName === 'current' && data.historicalData) {
                foreignBornSeries = data.historicalData['ForeignBorn']?.series;
                popSeries = data.historicalData['Pop']?.series;
            } else if (data.timeseriesData) {
                foreignBornSeries = data.timeseriesData['ForeignBorn']?.series;
                popSeries = data.timeseriesData['Pop']?.series;

                if (foreignBornSeries && popSeries && currentData && currentData.historicalData) {
                    const currentForeignBorn = currentData.historicalData['ForeignBorn']?.series;
                    const currentPop = currentData.historicalData['Pop']?.series;
                    if (currentForeignBorn && currentPop && currentForeignBorn.length > 0 && currentPop.length > 0) {
                        const lastIndex = currentForeignBorn.length - 1;
                        foreignBornSeries = [currentForeignBorn[lastIndex], ...foreignBornSeries];
                        popSeries = [currentPop[lastIndex], ...popSeries];
                    }
                }
            }

            if (foreignBornSeries && popSeries && Array.isArray(foreignBornSeries) && Array.isArray(popSeries)) {
                let startYear;
                if (scenarioName === 'current') {
                    startYear = popSeries.length === 15 ? 2010 : 2014;
                } else {
                    startYear = 2024;
                }

                let yearIndex = selectedYear - startYear;

                if (yearIndex >= 0 && yearIndex < foreignBornSeries.length && yearIndex < popSeries.length) {
                    const share = foreignBornSeries[yearIndex] / popSeries[yearIndex];
                    return share;
                }
            }
            return null;
        }

        const series = getHistoricalSeries(key);
        if (!series || !Array.isArray(series)) return null;

        let startYear;
        if (scenarioName === 'current') {
            startYear = series.length === 15 ? 2010 : 2014;
        } else {
            startYear = 2024;
        }

        const yearIndex = selectedYear - startYear;

        if (scenarioName !== 'current' && selectedYear === 2024 && yearIndex < 0 && currentData) {
            if (key in currentData) return currentData[key];
            const hist = currentData.historicalData?.[key]?.series;
            if (hist && hist.length > 0) return hist[hist.length - 1];
        }

        if (yearIndex >= 0 && yearIndex < series.length) {
            return series[yearIndex];
        } else if (yearIndex >= series.length && series.length >= 2 && selectedYear === 2035) {
            const lastValue = series[series.length - 1];
            const secondLastValue = series[series.length - 2];
            const growthRate = (lastValue - secondLastValue) / Math.abs(secondLastValue);
            return lastValue * (1 + growthRate);
        } else if (series.length > 0) {
            return series[series.length - 1];
        }
        return null;
    };

    // Pre-compute raw series for trend calculation
    const s = (key) => getHistoricalSeries(key);
    const t = (key) => computeTrend(s(key));

    return {
        main: [
            { title: "Population",          value: formatNumber(getValueForYear('Pop') || data.Pop),                                                                   unit: "People",     ...t('Pop'),             chartType: "area",    maxValue: 200000,    color: "#0088FE", secondaryColor: "#82CA9D", series: s('Pop') },
            { title: "Forest Coverage",     value: formatNumber((getValueForYear('NatCov') || data.NatCov) * 100, 2),                                                  unit: "%",          ...t('NatCov'),          chartType: "area",    maxValue: 100,       color: "#00C49F", secondaryColor: "#8DD1E1", series: s('NatCov')?.map(v => v * 100) },
            { title: "Total GDP",           value: formatNumber((getValueForYear('GDP') || data.GDP) / 1000000, 1),                                                    unit: "M$",         ...t('GDP'),             chartType: "area",    maxValue: 15000,     color: "#0088FE", secondaryColor: "#00C49F", series: s('GDP')?.map(v => v / 1000000) },
            { title: "Monthly Salary",      value: formatNumber(getValueForYear('Salary') || data.Salary, 0),                                                          unit: "$",          ...t('Salary'),          chartType: "line",    maxValue: 8000,      color: "#0088FE", secondaryColor: "#00C49F", series: s('Salary') },
            { title: "Total CO₂ Emissions", value: formatNumber((getValueForYear('CO2_total') || data.CO2_total) / 1000, 0),                                           unit: "kt",         ...t('CO2_total'),       chartType: "area",    maxValue: 1000,      color: "#FF8042", secondaryColor: "#FFBB28", series: s('CO2_total')?.map(v => v / 1000) },
            { title: "Tourist Arrivals",    value: formatNumber(getValueForYear('Tour') || data.Tour),                                                                 unit: "",           ...t('Tour'),            chartType: "line",    maxValue: 15000000,  color: "#8884D8", secondaryColor: "#82CA9D", series: s('Tour') },
            { title: "Buildings Count",     value: formatNumber(getValueForYear('B') || data.B),                                                                       unit: "",           ...t('B'),               chartType: "area",    maxValue: 25000,     color: "#8884D8", secondaryColor: "#82CA9D", series: s('B') },
            { title: "Housing Affordability", value: (() => { const v = getValueForYear('Afford') || data.Afford; return formatNumber(v >= 1 ? v : v * 100, 1); })(), unit: "%",          ...t('Afford'),          chartType: "bar",     maxValue: 100,       color: "#FF8042", secondaryColor: "#FFBB28", series: s('Afford')?.map(v => v >= 1 ? v : v * 100) },
            { title: "Business Formation",  value: formatNumber(getValueForYear('BusinessFormation') || data.BusinessFormation),                                       unit: "/year",      ...t('BusinessFormation'), chartType: "bar",   maxValue: 5000,      color: "#FFBB28", secondaryColor: "#FF8042", series: s('BusinessFormation') },
            { title: "Foreign-born Share",  value: formatNumber((getValueForYear('sForeignBorn') || data.sForeignBorn) * 100, 1),                                      unit: "%",          ...t('sForeignBorn'),    chartType: "bar",     maxValue: 100,       color: "#8884D8", secondaryColor: "#82CA9D", series: s('sForeignBorn')?.map(v => v * 100) }
        ],
        economic: [
            { title: "GDP per Capita",      value: formatNumber(getValueForYear('GDPpc') || data.GDPpc, 2),                                                            unit: "$",          ...t('GDPpc'),           chartType: "area",    maxValue: 80000,     color: "#00C49F", secondaryColor: "#82CA9D", series: s('GDPpc') },
            { title: "Total GDP",           value: formatNumber((getValueForYear('GDP') || data.GDP) / 1000000, 1),                                                    unit: "M$",         ...t('GDP'),             chartType: "area",    maxValue: 15000,     color: "#0088FE", secondaryColor: "#00C49F", series: s('GDP')?.map(v => v / 1000000) },
            { title: "Annual Income",       value: formatNumber(data.Income, 0),                                                                                       unit: "$",          ...t('Income'),          chartType: "line",    maxValue: 100000,    color: "#8884D8", secondaryColor: "#82CA9D", series: s('Income') },
            { title: "Monthly Salary",      value: formatNumber(getValueForYear('Salary') || data.Salary, 0),                                                          unit: "$",          ...t('Salary'),          chartType: "line",    maxValue: 8000,      color: "#0088FE", secondaryColor: "#00C49F", series: s('Salary') },
            { title: "Housing Affordability", value: (() => { const v = getValueForYear('Afford') || data.Afford; return formatNumber(v >= 1 ? v : v * 100, 1); })(), unit: "%",          ...t('Afford'),          chartType: "bar",     maxValue: 100,       color: "#FF8042", secondaryColor: "#FFBB28", series: s('Afford')?.map(v => v >= 1 ? v : v * 100) },
            { title: "Housing Price",       value: formatNumber(getValueForYear('HPrice') || data.HPrice, 0),                                                          unit: "$/month",    ...t('HPrice'),          chartType: "line",    maxValue: 50000,     color: "#FFBB28", secondaryColor: "#FF8042", series: s('HPrice') },
            { title: "Employment Rate",     value: formatNumber((getValueForYear('Emp') || data.Emp) * 100, 2),                                                        unit: "%",          ...t('Emp'),             chartType: "line",    maxValue: 100,       color: "#00C49F", secondaryColor: "#8DD1E1", series: s('Emp')?.map(v => v * 100) },
            { title: "Business Formation",  value: formatNumber(getValueForYear('BusinessFormation') || data.BusinessFormation),                                       unit: "/year",      ...t('BusinessFormation'), chartType: "bar",   maxValue: 5000,      color: "#FFBB28", secondaryColor: "#FF8042", series: s('BusinessFormation') },
            { title: "Tourist Arrivals",    value: formatNumber(getValueForYear('Tour') || data.Tour),                                                                 unit: "",           ...t('Tour'),            chartType: "line",    maxValue: 15000000,  color: "#8884D8", secondaryColor: "#82CA9D", series: s('Tour') },
            { title: "Buildings Count",     value: formatNumber(getValueForYear('B') || data.B),                                                                       unit: "",           ...t('B'),               chartType: "area",    maxValue: 25000,     color: "#8884D8", secondaryColor: "#82CA9D", series: s('B') }
        ],
        social: [
            { title: "Population",            value: formatNumber(getValueForYear('Pop') || data.Pop),                                                                 unit: "People",     ...t('Pop'),             chartType: "area",    maxValue: 200000,    color: "#0088FE", secondaryColor: "#82CA9D", series: s('Pop') },
            { title: "Foreign-born Population", value: formatNumber(getValueForYear('ForeignBorn') || data.ForeignBorn),                                               unit: "People",     ...t('ForeignBorn'),     chartType: "area",    maxValue: 200000,    color: "#FFBB28", secondaryColor: "#FF8042", series: s('ForeignBorn') },
            { title: "Foreign-born Share",    value: formatNumber((getValueForYear('sForeignBorn') || data.sForeignBorn) * 100, 1),                                    unit: "%",          ...t('sForeignBorn'),    chartType: "bar",     maxValue: 100,       color: "#8884D8", secondaryColor: "#82CA9D", series: s('sForeignBorn')?.map(v => v * 100) },
            { title: "Life Expectancy",       value: formatNumber(getValueForYear('LE') || data.LE, 1),                                                                unit: "Years",      ...t('LE'),              chartType: "bar",     maxValue: 100,       color: "#00C49F", secondaryColor: "#8DD1E1", series: s('LE') },
            { title: "Marriages",             value: formatNumber(data.Marriages),                                                                                     unit: "/year",      ...t('Marriages'),       chartType: "bar",     maxValue: 1000,      color: "#00C49F", secondaryColor: "#8DD1E1", series: s('Marriages') },
            { title: "Divorces",              value: formatNumber(data.Divorces),                                                                                      unit: "/year",      ...t('Divorces'),        chartType: "bar",     maxValue: 100,       color: "#FF8042", secondaryColor: "#FFBB28", series: s('Divorces') },
            { title: "Employment Rate",       value: formatNumber((getValueForYear('Emp') || data.Emp) * 100, 2),                                                      unit: "%",          ...t('Emp'),             chartType: "line",    maxValue: 100,       color: "#00C49F", secondaryColor: "#8DD1E1", series: s('Emp')?.map(v => v * 100) },
            { title: "Access to Health",      value: formatNumber(data.Access * 100, 1),                                                                               unit: "%",          ...t('Access'),          chartType: "bar",     maxValue: 100,       color: "#8884D8", secondaryColor: "#82CA9D", series: s('Access')?.map(v => v * 100) }
        ],
        environmental: [
            { title: "Forest Coverage",         value: formatNumber((getValueForYear('NatCov') || data.NatCov) * 100, 2),                                              unit: "%",          ...t('NatCov'),          chartType: "area",    maxValue: 100,       color: "#00C49F", secondaryColor: "#8DD1E1", series: s('NatCov')?.map(v => v * 100) },
            { title: "CO₂ Emissions per Capita", value: formatNumber(getValueForYear('CO2pc') || data.CO2pc, 1),                                                       unit: "t/capita",   ...t('CO2pc'),           chartType: "area",    maxValue: 10,        color: "#FF8042", secondaryColor: "#FFBB28", series: s('CO2pc') },
            { title: "Total CO₂ Emissions",     value: formatNumber((getValueForYear('CO2_total') || data.CO2_total) / 1000, 0),                                       unit: "kt",         ...t('CO2_total'),       chartType: "area",    maxValue: 1000,      color: "#FF8042", secondaryColor: "#FFBB28", series: s('CO2_total')?.map(v => v / 1000) },
            { title: "Renewable Energy",        value: formatNumber((getValueForYear('Ren') || data.Ren) * 100, 1),                                                    unit: "%",          ...t('Ren'),             chartType: "bar",     maxValue: 100,       color: "#00C49F", secondaryColor: "#82CA9D", series: s('Ren')?.map(v => v * 100) },
            { title: "Air Quality Index",       value: formatNumber(getValueForYear('AQI') || data.AQI, 0),                                                            unit: "AQI",        ...t('AQI'),             chartType: "line",    maxValue: 100,       color: "#0088FE", secondaryColor: "#8DD1E1", series: s('AQI') },
            { title: "Water Consumption",       value: formatNumber(getValueForYear('Water') || data.Water),                                                           unit: "L/day",      ...t('Water'),           chartType: "area",    maxValue: 100000,    color: "#0088FE", secondaryColor: "#00C49F", series: s('Water') },
            { title: "Average Temperature",     value: formatNumber(getValueForYear('Temp') || data.Temp, 2),                                                          unit: "°C",         ...t('Temp'),            chartType: "area",    maxValue: 30,        color: "#FF8042", secondaryColor: "#FFBB28", series: s('Temp') }
        ],
        infrastructure: [
            { title: "Electricity Capacity",  value: formatNumber(getValueForYear('ElectricityCapacity_kW') || data.ElectricityCapacity_kW, 0),                        unit: "kW",         ...t('ElectricityCapacity_kW'),          chartType: "area", maxValue: 200000,  color: "#FFD700", secondaryColor: "#FFA500", series: s('ElectricityCapacity_kW') },
            { title: "Electricity Demand",    value: formatNumber((getValueForYear('ElectricityDemand_kWh_year') || data.ElectricityDemand_kWh_year) / 1000000, 1),    unit: "M kWh/year", ...t('ElectricityDemand_kWh_year'),      chartType: "area", maxValue: 1000,    color: "#FFD700", secondaryColor: "#FFA500", series: s('ElectricityDemand_kWh_year')?.map(v => v / 1000000) },
            { title: "Renewable Capacity",    value: formatNumber(getValueForYear('ElectricityRenewable_kW') || data.ElectricityRenewable_kW, 0),                      unit: "kW",         ...t('ElectricityRenewable_kW'),         chartType: "bar",  maxValue: 150000,  color: "#00C49F", secondaryColor: "#82CA9D", series: s('ElectricityRenewable_kW') },
            { title: "Fossil Capacity",       value: formatNumber(getValueForYear('ElectricityFossil_kW') || data.ElectricityFossil_kW, 0),                            unit: "kW",         ...t('ElectricityFossil_kW'),            chartType: "bar",  maxValue: 100000,  color: "#FF8042", secondaryColor: "#FFBB28", series: s('ElectricityFossil_kW') },
            { title: "Water Total Demand",    value: formatNumber((getValueForYear('WaterTotal_m3_year') || data.WaterTotal_m3_year) / 1000000, 1),                    unit: "M m³/year",  ...t('WaterTotal_m3_year'),              chartType: "area", maxValue: 100,     color: "#0088FE", secondaryColor: "#00C49F", series: s('WaterTotal_m3_year')?.map(v => v / 1000000) },
            { title: "Water Security Index",  value: formatNumber(getValueForYear('WaterSecurityIndex') || data.WaterSecurityIndex, 3),                                unit: "",           ...t('WaterSecurityIndex'),              chartType: "bar",  maxValue: 1,       color: "#8884D8", secondaryColor: "#82CA9D", series: s('WaterSecurityIndex') },
            { title: "Hospital Required Beds", value: formatNumber(getValueForYear('HospitalRequiredBeds') || data.HospitalRequiredBeds, 1),                           unit: "beds",       ...t('HospitalRequiredBeds'),            chartType: "bar",  maxValue: 1000,    color: "#FF6B6B", secondaryColor: "#FF8787", series: s('HospitalRequiredBeds') },
            { title: "Hospital Delta Beds",   value: formatNumber(getValueForYear('HospitalDeltaBeds') || data.HospitalDeltaBeds, 1),                                  unit: "beds",       ...t('HospitalDeltaBeds'),               chartType: "bar",  maxValue: 500,     color: "#FF6B6B", secondaryColor: "#FF8787", series: s('HospitalDeltaBeds') },
            { title: "School Students",       value: formatNumber(getValueForYear('SchoolStudents') || data.SchoolStudents, 0),                                         unit: "students",   ...t('SchoolStudents'),                  chartType: "area", maxValue: 30000,   color: "#4ECDC4", secondaryColor: "#44A08D", series: s('SchoolStudents') },
            { title: "School Classrooms",     value: formatNumber(getValueForYear('SchoolClassrooms') || data.SchoolClassrooms, 1),                                    unit: "classrooms", ...t('SchoolClassrooms'),                chartType: "bar",  maxValue: 1500,    color: "#4ECDC4", secondaryColor: "#44A08D", series: s('SchoolClassrooms') },
            { title: "School Schools",        value: formatNumber(getValueForYear('SchoolSchools') || data.SchoolSchools, 1),                                          unit: "schools",    ...t('SchoolSchools'),                   chartType: "bar",  maxValue: 100,     color: "#4ECDC4", secondaryColor: "#44A08D", series: s('SchoolSchools') },
            { title: "Road Per Capita",       value: formatNumber(getValueForYear('RoadPerCapita_m') || data.RoadPerCapita_m, 2),                                      unit: "m/person",   ...t('RoadPerCapita_m'),                 chartType: "area", maxValue: 10,      color: "#95A5A6", secondaryColor: "#7F8C8D", series: s('RoadPerCapita_m') }
        ]
    };
}
