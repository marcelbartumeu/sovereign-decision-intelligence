// Andorra bus line frequencies — sourced from bus.ad & govern.ad (April 2026)
// Network restructured July 7, 2025: LC discontinued, L7 created, L3/L4/L6 rerouted.
// Used for bus animation: spawn interval = weekday_headway_min * 60 (seconds)

export const BUS_FREQUENCIES = [
  {
    ref: 'L1',
    name: 'Escaldes-Engordany – Sant Julià de Lòria',
    operator: 'Autocars Nadal',
    colour: '#E63946',
    days: 'daily',
    weekday: {
      headway_min: 20,       // every 20 min 06:20–21:00, then 30 min until 22:00
      peak_headway_min: 20,
      first_bus: '06:20',
      last_bus:  '22:00',
    },
    weekend: {
      headway_min: 30,
      first_bus: '06:30',
      last_bus:  '22:30',
    },
  },
  {
    ref: 'L2',
    name: 'Andorra la Vella – Encamp',
    operator: 'Coopalsa',
    colour: '#2196F3',
    days: 'daily',
    weekday: {
      headway_min: 15,       // 12 min peak (06:45–08:25 & 15:25–19:22), 15 min off-peak
      peak_headway_min: 12,
      first_bus: '06:45',
      last_bus:  '22:05',
    },
    weekend: {
      headway_min: 30,
      first_bus: '06:50',
      last_bus:  '21:20',
    },
  },
  {
    ref: 'L3',
    name: 'Andorra la Vella – Soldeu (– Grau Roig ski season)',
    operator: 'Coopalsa',
    colour: '#9C27B0',
    days: 'mon-sat',         // no Sunday service
    weekday: {
      headway_min: 20,       // peak only: 06:40–09:20 & 14:50–20:50 — midday gap
      peak_headway_min: 20,
      first_bus: '06:40',
      last_bus:  '20:50',
      note: 'Peak-direction only — no midday service Mon–Fri',
    },
    weekend: {
      headway_min: 30,       // Saturday only
      first_bus: '06:40',
      last_bus:  '20:40',
      note: 'Saturday only; no Sunday service',
    },
  },
  {
    ref: 'L4',
    name: 'Andorra la Vella – Pas de la Casa',
    operator: 'Coopalsa',
    colour: '#FF9800',
    days: 'daily',
    weekday: {
      headway_min: 30,
      first_bus: '06:25',
      last_bus:  '22:00',
    },
    weekend: {
      headway_min: 30,
      first_bus: '06:25',
      last_bus:  '21:25',
    },
  },
  {
    ref: 'L5',
    name: 'Andorra la Vella – Arinsal',
    operator: 'Coopalsa',
    colour: '#4CAF50',
    days: 'daily',
    weekday: {
      headway_min: 30,       // 20 min peak (06:50–08:50 & 15:30–19:50), 30 min off-peak
      peak_headway_min: 20,
      first_bus: '06:50',
      last_bus:  '22:00',
    },
    weekend: {
      headway_min: 30,
      first_bus: '07:10',
      last_bus:  '21:40',
    },
  },
  {
    ref: 'L6',
    name: 'Andorra la Vella – Ordino – La Cortinada',
    operator: 'Coopalsa',
    colour: '#009688',
    days: 'daily',
    weekday: {
      headway_min: 30,
      first_bus: '06:55',
      last_bus:  '22:10',
    },
    weekend: {
      headway_min: 30,
      first_bus: '06:55',
      last_bus:  '21:25',
    },
  },
  {
    ref: 'L7',
    name: 'Andorra la Vella – La Massana – Ordino',
    operator: 'Coopalsa',
    colour: '#00BCD4',
    days: 'daily',
    note: 'New line from July 2025, extended to Ordino in early 2026',
    weekday: {
      headway_min: 15,       // 15 min 06:43–20:13, then 20 min until 21:53
      peak_headway_min: 15,
      first_bus: '06:43',
      last_bus:  '21:53',
    },
    weekend: {
      headway_min: 30,
      first_bus: '06:55',
      last_bus:  '21:55',
    },
  },
  {
    ref: 'é',
    name: 'Andorra la Vella – Escaldes-Engordany (Electric)',
    operator: 'Cooperativa Interurbana Andorrana',
    colour: '#8BC34A',
    days: 'daily',
    weekday: {
      headway_min: 10,       // highest frequency in the network
      first_bus: '06:30',
      last_bus:  '22:00',
    },
    weekend: {
      headway_min: 10,
      first_bus: '06:30',
      last_bus:  '22:00',
    },
  },
  {
    ref: 'Lé',
    name: 'Escaldes-Engordany – Sant Julià de Lòria (Express)',
    operator: 'Autocars Nadal',
    colour: '#CDDC39',
    days: 'daily',
    note: 'Also called Bus Exprés — same service, two names',
    weekday: {
      headway_min: 20,       // 10 min peak (07–10 & 16–18), 20 min off-peak
      peak_headway_min: 10,
      first_bus: '06:30',
      last_bus:  '22:00',
    },
    weekend: {
      headway_min: 30,
      first_bus: '06:30',
      last_bus:  '22:00',
    },
  },
  {
    ref: 'BN1',
    name: 'Bus Nocturn: Andorra la Vella – Escaldes – Sant Julià de Lòria',
    operator: 'Autocars Nadal',
    colour: '#3F51B5',
    days: 'nightly',
    weekday: {
      headway_min: null,     // fixed departures only (3 runs): 23:30, 00:00, 00:30
      first_bus: '23:30',
      last_bus:  '01:00',
    },
    weekend: {               // Fri/Sat & eve of holidays
      headway_min: 60,       // ~every 60 min, 23:00–05:00 (6 departures)
      first_bus: '23:00',
      last_bus:  '05:00',
    },
  },
  {
    ref: 'BN2',
    name: 'Bus Nocturn: Andorra la Vella – Encamp – Canillo',
    operator: 'Coopalsa',
    colour: '#673AB7',
    days: 'nightly',
    weekday: {
      headway_min: null,     // 3 fixed departures: 23:40, 00:20, 01:00
      first_bus: '23:40',
      last_bus:  '01:00',
    },
    weekend: {
      headway_min: 35,       // ~every 30–40 min, 22:20–05:40
      first_bus: '22:20',
      last_bus:  '05:40',
    },
  },
  {
    ref: 'BN3',
    name: 'Bus Nocturn: Andorra la Vella – Ordino – Arinsal',
    operator: 'Coopalsa',
    colour: '#795548',
    days: 'nightly',
    weekday: {
      headway_min: null,     // 3 fixed departures: 23:40, 00:20, 01:00
      first_bus: '23:40',
      last_bus:  '01:00',
    },
    weekend: {
      headway_min: 35,       // ~every 30–40 min, 22:20–05:40
      first_bus: '22:20',
      last_bus:  '05:40',
    },
  },
  {
    ref: 'EE',
    name: 'EE Bus – Escaldes-Engordany (Engolasters + On-Demand)',
    operator: 'Comú d\'Escaldes-Engordany',
    colour: '#FF5722',
    days: 'daily',
    note: 'Engolasters fixed line (~hourly) + RIDE PINGO on-demand within Escaldes-Engordany',
    weekday: {
      headway_min: 60,       // fixed Engolasters line; on-demand available 07:00–22:00
      first_bus: '07:00',
      last_bus:  '21:15',
    },
    weekend: {
      headway_min: 60,
      first_bus: '07:00',
      last_bus:  '21:15',
      note: 'On-demand: 09:00–22:00 on Sat/Sun/holidays',
    },
  },
  // LC — DISCONTINUED July 7, 2025
  // {
  //   ref: 'LC',
  //   name: 'Línia Circular (Escaldes ↔ Andorra la Vella)',
  //   note: 'Discontinued July 7 2025 — replaced by L7',
  //   colour: '#FF5722',
  //   days: 'discontinued',
  //   weekday: { headway_min: 30, first_bus: '06:30', last_bus: '21:30' },
  //   weekend: { headway_min: 30, first_bus: '06:30', last_bus: '21:30' },
  // },
];

// Convenience: spawn interval in seconds for a given line and day type
// e.g. spawnInterval('L2', 'weekday') → 15 * 60 = 900s
export function spawnInterval(ref, dayType = 'weekday') {
  const line = BUS_FREQUENCIES.find(l => l.ref === ref);
  if (!line) return null;
  const sched = line[dayType] || line.weekday;
  const headway = sched.peak_headway_min || sched.headway_min;
  return headway ? headway * 60 : null;
}
