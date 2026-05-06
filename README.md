# Andorra V1.9

An interactive scenario modeling and visualization system for Andorra, simulating different future development paths through an agent-based model (ABM) and a real-time web dashboard. Optionally controlled via Arduino hardware.

---

## Dashboard

The dashboard has six views:

| Tab | Description |
|-----|-------------|
| **Main** | Headline KPIs and scenario overview |
| **Economic Matrix** | GDP, income, housing, business formation |
| **Social Systems** | Population, employment, family stability |
| **Environmental Grid** | CO₂, air quality, water, temperature, renewables |
| **Infrastructure** | Electricity, water, hospitals, schools, roads |
| **Agent Analytics** | ABM simulation — track individual agents, emotions, paths |

Four scenarios are modeled: **Continuity**, **Overgrowth**, **Degrowth**, and **Density**.

---

## Running Locally

### Requirements

- [Node.js](https://nodejs.org) 18 or later

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Meimus/ANDORRA-V1.0-MIT.git
cd ANDORRA-V1.0-MIT

# 2. Install dashboard dependencies
cd "Front end/dashboard"
npm install

# 3. Install and build the ABM visualization
cd viz-abm-emotion-main
npm install
npm run build
cd ..

# 4. Start the dev server
npm run dev
```

Open **http://localhost:5173** in your browser (may use 5174 if 5173 is busy).

---

## Project Structure

```
├── Front end/
│   ├── dashboard/          # React + Vite dashboard (main app)
│   │   ├── src/            # Components, hooks, pages
│   │   ├── public/         # GeoJSON map layers
│   │   ├── viz-abm-emotion-main/   # ABM visualization (embedded as iframe)
│   │   │   └── src/simulation_output/  # Agent simulation data (~2300 agents)
│   │   └── vite.config.js  # Dev server + static file middleware
│   └── Public/             # Scenario images
├── Arduino/                # Hardware controller sketches
├── conf/scenarios/         # Scenario parameter files (JSON)
├── andorra h3/             # Street network and GIS data
├── cdm-server-maqueta/     # Unity 3D model
└── paper/                  # Research paper (LaTeX)
```

---

## Arduino (Optional)

The dashboard can be controlled by an Arduino connected via USB (Web Serial API). The `Arduino/ScenarioSlider.ino` sketch maps physical inputs to dashboard controls (year slider, tab switching, scenario overlays, agent selection).

Connect the Arduino, then click the **Arduino** button in the dashboard header to pair it.

---

## Tech Stack

- **Frontend**: React 18, Vite, Leaflet, deck.gl, Chart.js
- **ABM Visualization**: React, deck.gl, Three.js, Recharts
- **Hardware**: Arduino (Web Serial API)
- **Data**: JSON scenario files, GeoJSON map layers
