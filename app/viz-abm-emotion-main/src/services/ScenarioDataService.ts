import continuityData from '../data/scenarios/continuity.json';
import overgrowthData from '../data/scenarios/overgrowth.json';
import degrowthData from '../data/scenarios/degrowth.json';
import densityData from '../data/scenarios/density.json';

export type ScenarioId = 'continuity' | 'overgrowth' | 'degrowth' | 'density';
export type MapLayerId = 'agents' | 'base' | 'tourism' | 'growth';

export interface ScenarioYear {
  Year: number;
  Pop: number;
  ForeignBorn: number;
  sForeignBorn: number;
  Access: number;
  LE: number;
  WLB: number;
  GDPpc: number;
  Income: number;
  Salary: number;
  BusinessFormation: number;
  B: number;
  HPrice: number;
  Afford: number;
  NatCov: number;
  CO2pc: number;
  CO2_total: number;
  Ren: number;
  AQI: number;
  Water: number;
  Temp: number;
  Tour: number;
  GDP: number;
  Marriages: number;
  Divorces: number;
  FamilyStability: number;
  Emp: number;
  ElectricityDemand_kWh_year: number;
  ElectricityCapacity_kW: number;
  ElectricityRenewable_kW: number;
  ElectricityFossil_kW: number;
  WaterPerCapita_L_day: number;
  WaterHousehold_m3_year: number;
  WaterTotal_m3_year: number;
  WaterSecurityIndex: number;
  HospitalBaselineBeds: number;
  HospitalRequiredBeds: number;
  HospitalDeltaBeds: number;
  SchoolStudents: number;
  SchoolClassrooms: number;
  SchoolSchools: number;
  RoadTotalLength_km: number;
  RoadPerCapita_m: number;
}

const SCENARIOS: Record<ScenarioId, ScenarioYear[]> = {
  continuity: continuityData as ScenarioYear[],
  overgrowth: overgrowthData as ScenarioYear[],
  degrowth: degrowthData as ScenarioYear[],
  density: densityData as ScenarioYear[],
};

export function getScenarioTimeseries(scenario: ScenarioId): ScenarioYear[] {
  return SCENARIOS[scenario] ?? [];
}

export function getScenarioYear(scenario: ScenarioId, year: number): ScenarioYear | null {
  return SCENARIOS[scenario]?.find(d => d.Year === year) ?? null;
}

export function getYearRange() {
  return { min: 2025, max: 2035 };
}

export const SCENARIO_LABELS: Record<ScenarioId, string> = {
  continuity: 'CONTINUITY',
  overgrowth: 'OVERGROWTH',
  degrowth:   'DEGROWTH',
  density:    'DENSITY',
};

export const SCENARIO_COLORS: Record<ScenarioId, string> = {
  continuity: '#4ade80',
  overgrowth: '#f97316',
  degrowth:   '#60a5fa',
  density:    '#a855f7',
};

export const MAP_LAYER_LABELS: Record<MapLayerId, string> = {
  agents:  'AGENTS',
  base:    'BASE',
  tourism: 'TOURISM',
  growth:  'GROWTH',
};

// Known geographic points in Andorra for synthetic map layers
export const ANDORRA_PARISHES = [
  { name: 'Andorra la Vella', lon: 1.5218, lat: 42.5075, weight: 1.0 },
  { name: 'Escaldes-Engordany', lon: 1.5375, lat: 42.5069, weight: 0.85 },
  { name: 'Encamp',   lon: 1.5833, lat: 42.5350, weight: 0.60 },
  { name: 'Canillo',  lon: 1.5983, lat: 42.5667, weight: 0.45 },
  { name: 'La Massana', lon: 1.5167, lat: 42.5500, weight: 0.55 },
  { name: 'Ordino',   lon: 1.5333, lat: 42.5667, weight: 0.40 },
  { name: 'Sant Julià de Lòria', lon: 1.4917, lat: 42.4667, weight: 0.65 },
];

export const ANDORRA_TOURISM_HOTSPOTS = [
  { name: 'Grandvalira',   lon: 1.7000, lat: 42.5200, weight: 1.0 },
  { name: 'Vallnord',      lon: 1.5167, lat: 42.6000, weight: 0.75 },
  { name: 'Pas de la Casa', lon: 1.7333, lat: 42.5428, weight: 0.85 },
  { name: 'Caldea Spa',    lon: 1.5375, lat: 42.5069, weight: 0.70 },
  { name: 'Shopping District', lon: 1.5218, lat: 42.5075, weight: 0.90 },
  { name: 'Naturlandia',   lon: 1.4833, lat: 42.4833, weight: 0.55 },
];
