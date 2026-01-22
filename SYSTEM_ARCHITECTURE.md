# Andorra V1.4 - System Architecture

## Overview
This is a **scenario modeling and visualization system** for Andorra that simulates different future development paths (Continuity, Overgrowth, Degrowth) and displays them in an interactive web dashboard. The system integrates Python-based economic/social modeling with a web-based visualization frontend and optional Arduino hardware control.

---

## System Components

### 1. **Data Layer** (Python Backend)

#### **CALCULATOR.py** - Core Simulation Engine
- **Purpose**: Main simulation script that models economic, social, and environmental indicators over time
- **Input**: `Current.json` (baseline 2024 data)
- **Output**: 
  - `{Scenario}_timeseries.json` (year-by-year data 2025-2035)
  - `{Scenario}_final.json` (final state for each scenario)
  - `Scenario_Rollup.json` (summary comparison)
- **Key Functions**:
  - `step_next()`: One-year forward simulation step
  - `simulate_path()`: Runs 11-year simulation for a scenario
  - `transform_data_from_list_format()`: Converts JSON data structure
- **Dependencies**: `infrastructure.py`

#### **infrastructure.py** - Infrastructure Calculation Module
- **Purpose**: Calculates infrastructure requirements (electricity, water, hospitals, schools, roads)
- **Key Functions**:
  - `computeInfrastructureScenario()`: Calculates infrastructure for a given population/scenario
  - `computeAllInfrastructureScenarios()`: Batch calculation for all scenarios
- **Configuration**: `INFRASTRUCTURE_CONFIG` dictionary with constants
- **Output**: Infrastructure metrics integrated into state objects

#### **Configuration Files** (`conf/scenarios/`)
- `continuity.json`, `overgrowth.json`, `degrowth.json`
- Define scenario-specific parameters (growth rates, assumptions)
- Used to configure simulation behavior

---

### 2. **Data Transformation Layer**

#### **scenarioData.js** - JavaScript Data Bridge
- **Purpose**: Converts Python JSON output into JavaScript format for dashboard consumption
- **Structure**:
  ```javascript
  scenarioData = {
    current: { /* 2024 baseline data */ },
    continuity: { /* 2035 projection */ },
    overgrowth: { /* 2035 projection */ },
    degrowth: { /* 2035 projection */ },
    historicalData: { /* 2010-2024 time series */ }
  }
  ```
- **Data Sources**:
  - `Current.json` → `current` object
  - `Continuity_timeseries.json` → historical + projected data
  - `Overgrowth_timeseries.json` → historical + projected data
  - `Degrowth_timeseries.json` → historical + projected data

---

### 3. **Presentation Layer** (Web Frontend)

#### **Dashboard.HTML** - Main Dashboard Application
- **Technology Stack**:
  - Pure HTML/CSS/JavaScript (no frameworks)
  - Chart.js for data visualization
  - Web Serial API for Arduino integration
- **Key Features**:
  - **Scenario Selection**: Switch between Historical (2010-2024) and 3 future scenarios (2025-2035)
  - **Year Slider**: Navigate through time within selected scenario
  - **KPI Cards**: Display key metrics with trend indicators
  - **Interactive Charts**: Line, area, bar, pie, radar charts
  - **Dynamic Images**: Scenario-specific visualizations per year
  - **Spain Comparison**: Historical data comparison for GDP, Housing, Salary, Employment

#### **Chart Types**:
- **Line Charts**: GDP per Capita, Housing Price, Monthly Salary, Tourism
- **Area Charts**: GDP, CO₂ Emissions, Population
- **Bar Charts**: Business Formation, Employment Rate, Housing Affordability
- **Radar/Pentagon Charts**: Employment Rate (5-year comparison)
- **Pie Charts**: Various breakdowns

#### **KPI Categories**:
1. **Main**: Overview metrics
2. **Economic**: GDP, Income, Salary, Housing, Employment, Business
3. **Social**: Population, Migration, Life Expectancy, Family Stability
4. **Environmental**: CO₂, Renewable Energy, Air Quality, Water, Temperature
5. **Infrastructure**: Electricity, Water, Hospitals, Schools, Roads

---

### 4. **Hardware Integration** (Optional)

#### **Arduino Controller**
- **Hardware**: Arduino board + 4 buttons + potentiometer (slider)
- **Communication**: Web Serial API (USB connection)
- **Functionality**:
  - Physical buttons switch scenarios
  - Potentiometer controls year slider
  - Real-time bidirectional communication
- **File**: `Arduino/ScenarioSlider.ino`
- **Protocol**: JSON messages over Serial (115200 baud)

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA GENERATION                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Current.json ──┐                                             │
│                 │                                             │
│  conf/scenarios/│───► CALCULATOR.py ──► Infrastructure.py    │
│  *.json         │                                             │
│                 │                                             │
│                 └───► {Scenario}_timeseries.json            │
│                 └───► {Scenario}_final.json                 │
│                 └───► Scenario_Rollup.json                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  DATA TRANSFORMATION                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  JSON Files ──► scenarioData.js ──► JavaScript Objects      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Dashboard.HTML                                              │
│  ├── Loads scenarioData.js                                   │
│  ├── Renders KPI cards                                       │
│  ├── Generates charts (Chart.js)                            │
│  ├── Updates images based on scenario/year                   │
│  └── Handles user interactions                               │
│                                                               │
│  Optional: Arduino Controller ──► Web Serial API            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Simulation Model Architecture

### **State Variables** (Per Year)
- **Demographic**: Population, Foreign-born, Foreign-born Share
- **Economic**: GDP, GDP per Capita, Income, Salary, Employment Rate
- **Housing**: Housing Price, Housing Affordability, Buildings Count
- **Social**: Life Expectancy, Work-Life Balance, Access to Health, Family Stability
- **Environmental**: CO₂ per Capita, Total CO₂, Renewable Energy Share, Air Quality, Water, Temperature
- **Infrastructure**: Electricity (capacity, demand, renewable/fossil), Water (per capita, total, security), Hospitals (beds), Schools (students, classrooms, schools), Roads (length, per capita)
- **Tourism**: Tourist Arrivals
- **Business**: Business Formation, Marriages, Divorces

### **Simulation Logic** (`step_next()`)
1. **Read current state** from baseline
2. **Apply exogenous targets** (population, tourism, buildings) if forced
3. **Calculate derived variables**:
   - Population growth (natural + migration based on economic factors)
   - GDP per capita growth
   - Employment rate changes
   - Housing price dynamics
   - Infrastructure requirements
4. **Apply scenario-specific parameters** from config files
5. **Return next year's state**

### **Scenario Types**
- **Continuity (CO)**: Steady growth (3% population, 8% tourism)
- **Overgrowth (OG)**: Rapid expansion (high population growth)
- **Degrowth (DG)**: Controlled decline (reduced population)

---

## File Structure

```
ANDORRA V1.4/
├── Front end/
│   ├── CALCULATOR.py              # Main simulation engine
│   ├── infrastructure.py           # Infrastructure calculations
│   ├── Dashboard.HTML             # Main dashboard application
│   ├── scenarioData.js            # JavaScript data bridge
│   ├── Current.json               # Baseline 2024 data
│   ├── {Scenario}_timeseries.json # Year-by-year projections
│   ├── {Scenario}_final.json     # Final state projections
│   ├── Scenario_Rollup.json       # Summary comparison
│   ├── Public/                    # Images/videos for scenarios
│   └── INFRASTRUCTURE_INTEGRATION.md
│
├── conf/
│   └── scenarios/
│       ├── continuity.json
│       ├── overgrowth.json
│       └── degrowth.json
│
└── Arduino/
    ├── ScenarioSlider.ino         # Arduino controller code
    ├── README.md
    └── WEBSERIAL_SETUP.md
```

---

## Technology Stack

### **Backend**
- **Python 3.x**: Core simulation logic
- **JSON**: Data serialization
- **Standard Library**: No external dependencies (except infrastructure module)

### **Frontend**
- **HTML5**: Structure
- **CSS3**: Styling (dark theme, responsive design)
- **Vanilla JavaScript**: No frameworks
- **Chart.js**: Data visualization library
- **Web Serial API**: Arduino communication (Chrome/Edge only)

### **Hardware** (Optional)
- **Arduino**: Microcontroller
- **USB Serial**: Communication protocol

---

## Key Design Patterns

### **1. Separation of Concerns**
- **Data Generation**: Python scripts
- **Data Transformation**: JavaScript bridge
- **Presentation**: HTML/CSS/JavaScript

### **2. Configuration-Driven**
- Scenario parameters in JSON config files
- Infrastructure constants in `INFRASTRUCTURE_CONFIG`
- Easy to modify without code changes

### **3. Modular Infrastructure**
- `infrastructure.py` is standalone and testable
- Can be imported or run independently
- Pure functions (no side effects)

### **4. Client-Side Rendering**
- All data loaded into browser memory
- No server-side rendering
- Fast, responsive interactions
- Works offline (after initial load)

### **5. Progressive Enhancement**
- Dashboard works without Arduino
- Arduino adds physical control layer
- Graceful degradation if hardware unavailable

---

## Data Formats

### **State Object Structure**
```json
{
  "state": {
    "Year": 2024,
    "Pop": 87097,
    "GDPpc": 42852.96,
    "Emp": 0.9852,
    "HPrice": 1332.734,
    // ... other variables
  },
  "params": {
    "gnat": 0.002,
    "beta1": 0.20,
    // ... scenario parameters
  },
  "exog": {
    "Pop_target": 87097,
    "force_pop": true,
    // ... exogenous inputs
  }
}
```

### **Timeseries Format**
```json
{
  "GDPpc": {
    "series": [37022.51, 37367.73, ...],
    "years": ["2010", "2011", ...]
  },
  "Pop": {
    "series": [78000, 79000, ...],
    "years": ["2010", "2011", ...]
  }
  // ... other indicators
}
```

---

## Execution Flow

### **1. Data Generation** (Run Once)
```bash
cd "Front end"
python3 CALCULATOR.py
```
- Reads `Current.json`
- Loads scenario configs from `conf/scenarios/`
- Runs 11-year simulation for each scenario
- Generates JSON output files

### **2. Dashboard Access**
```bash
cd "Front end"
python3 -m http.server 8000
```
- Open `http://localhost:8000/Dashboard.HTML`
- Dashboard loads `scenarioData.js`
- Renders interactive visualization

### **3. Arduino Control** (Optional)
- Connect Arduino via USB
- Click "Connect Arduino" in dashboard
- Physical controls update dashboard in real-time

---

## Performance Characteristics

- **Simulation Speed**: ~1-2 seconds per scenario (11 years)
- **Dashboard Load Time**: <1 second (all data in memory)
- **Chart Rendering**: <100ms per chart
- **Arduino Latency**: ~10-20ms (USB Serial)

---

## Extension Points

### **Adding New Indicators**
1. Add variable to `step_next()` in `CALCULATOR.py`
2. Add to state object output
3. Add to `scenarioData.js` structure
4. Add KPI card in `Dashboard.HTML`

### **Adding New Scenarios**
1. Create config file in `conf/scenarios/`
2. Add scenario name to `CALCULATOR.py` simulation loop
3. Add data to `scenarioData.js`
4. Add scenario option to dashboard UI

### **Adding New Chart Types**
1. Extend `getChartType()` mapping
2. Add case to `getChartData()` switch statement
3. Configure styling in `getChartOptions()`

---

## Dependencies

### **Python**
- Standard library only (no pip packages required)

### **JavaScript**
- Chart.js (loaded via CDN)
- Web Serial API (browser-native, Chrome/Edge only)

### **Arduino**
- Standard Arduino libraries
- Optional: ArduinoJson library

---

## Browser Compatibility

- **Chrome/Edge**: Full support (including Arduino)
- **Firefox/Safari**: Dashboard works, Arduino not supported
- **Mobile**: Responsive design, limited Arduino support

---

## Security Considerations

- **Local Only**: Designed for localhost use
- **No Authentication**: Not intended for public deployment
- **File Access**: Reads local JSON files only
- **Arduino**: Requires user permission for Serial port access

---

## Future Enhancements

- Database backend for historical data storage
- REST API for dynamic data updates
- Real-time collaboration features
- Export functionality (PDF, Excel)
- Advanced filtering and comparison tools
- Multi-language support

