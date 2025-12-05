/*
 * Andorra Dashboard Physical Controller
 * 
 * This Arduino sketch reads 4 buttons for scenario selection and a slider
 * for year selection, sending updates to the dashboard via USB Serial.
 * The dashboard uses Web Serial API to read these messages directly.
 * 
 * Hardware Setup:
 * - Button 1 (Current) on D2
 * - Button 2 (Overgrowth) on D3
 * - Button 3 (Degrowth) on D4
 * - Button 4 (Continuity) on D5
 * - All buttons: one side to pin, other side to GND (with pull-up resistors)
 * - Slider (potentiometer) on A1
 *   - One leg to 3.3V/5V, one leg to GND, wiper to A1
 * 
 * Software Requirements:
 * - Any Arduino board (Uno, Nano, ESP32, etc.)
 * - ArduinoJson library (optional, for JSON format)
 * 
 * Message Format (JSON):
 * {"type":"scenario_change","scenario":0,"name":"Current"}
 * {"type":"year_change","year":2024}
 */

// Hardware pins
const int BUTTON_PINS[] = {2, 3, 4, 5}; // D2, D3, D4, D5
const int SLIDER_PIN = A1; // Year slider

// Scenario mapping
const int SCENARIOS[] = {0, 1, 2, 3}; // Current, Overgrowth, Degrowth, Continuity
const char* SCENARIO_NAMES[] = {"Current", "Overgrowth", "Degrowth", "Continuity"};

// Year range for each scenario
const int YEAR_MIN_CURRENT = 2014;
const int YEAR_MAX_CURRENT = 2024;
const int YEAR_MIN_FUTURE = 2024;
const int YEAR_MAX_FUTURE = 2034;

// Variables
int lastScenario = -1;
int lastYear = -1;
int lastButtonStates[] = {HIGH, HIGH, HIGH, HIGH}; // Pull-up: HIGH = not pressed
unsigned long lastUpdate = 0;
const unsigned long UPDATE_INTERVAL = 50; // Update every 50ms for responsive buttons
const unsigned long DEBOUNCE_DELAY = 20; // Button debounce delay

void setup() {
  Serial.begin(115200);
  
  // Wait for serial connection (optional, remove if you want it to work without Serial Monitor)
  // while (!Serial) {
  //   delay(10);
  // }
  
  // Initialize pins
  pinMode(SLIDER_PIN, INPUT);
  
  // Initialize button pins with pull-up resistors
  for (int i = 0; i < 4; i++) {
    pinMode(BUTTON_PINS[i], INPUT_PULLUP);
    lastButtonStates[i] = digitalRead(BUTTON_PINS[i]);
  }
  
  Serial.println("Arduino Dashboard Controller Ready!");
  Serial.println("Button 1 (D2): Current");
  Serial.println("Button 2 (D3): Overgrowth");
  Serial.println("Button 3 (D4): Degrowth");
  Serial.println("Button 4 (D5): Continuity");
  Serial.println("Slider (A1): Year selection");
  Serial.println("Waiting for dashboard connection...");
}

void loop() {
  // Read buttons and slider, update dashboard
  if (millis() - lastUpdate > UPDATE_INTERVAL) {
    checkButtons();
    updateYear();
    lastUpdate = millis();
  }
}

void checkButtons() {
  // Check each button for press (LOW = pressed with pull-up)
  for (int i = 0; i < 4; i++) {
    int currentState = digitalRead(BUTTON_PINS[i]);
    
    // Detect button press (transition from HIGH to LOW)
    if (lastButtonStates[i] == HIGH && currentState == LOW) {
      // Debounce delay
      delay(DEBOUNCE_DELAY);
      currentState = digitalRead(BUTTON_PINS[i]);
      
      if (currentState == LOW) { // Still pressed after debounce
        int scenarioIndex = SCENARIOS[i];
        
        // Update scenario (always send, even if same button pressed)
        lastScenario = scenarioIndex;
        
        // Send scenario update as JSON
        Serial.print("{\"type\":\"scenario_change\",\"scenario\":");
        Serial.print(scenarioIndex);
        Serial.print(",\"name\":\"");
        Serial.print(SCENARIO_NAMES[scenarioIndex]);
        Serial.println("\"}");
        Serial.flush(); // Ensure message is sent immediately
        
        // Debug output
        Serial.print("DEBUG: Button ");
        Serial.print(i + 1);
        Serial.print(" pressed, scenario: ");
        Serial.println(scenarioIndex);
        Serial.flush();
      }
    }
    
    // Update last state
    lastButtonStates[i] = currentState;
  }
}

void updateYear() {
  // Read slider value (0-1023)
  int sliderValue = analogRead(SLIDER_PIN);
  
  // Determine year range based on current scenario
  int yearMin, yearMax;
  if (lastScenario == 0) {
    // Current scenario: 2014-2024
    yearMin = YEAR_MIN_CURRENT;
    yearMax = YEAR_MAX_CURRENT;
  } else {
    // Future scenarios: 2024-2034
    yearMin = YEAR_MIN_FUTURE;
    yearMax = YEAR_MAX_FUTURE;
  }
  
  // Map slider to year range
  int year = map(sliderValue, 0, 1023, yearMin, yearMax);
  year = constrain(year, yearMin, yearMax);
  
  // Only update if year changed (with some hysteresis to avoid constant updates)
  if (abs(year - lastYear) >= 1 || lastYear == -1) {
    lastYear = year;
    
    // Send year update as JSON
    Serial.print("{\"type\":\"year_change\",\"year\":");
    Serial.print(year);
    Serial.println("}");
    Serial.flush(); // Ensure message is sent immediately
  }
}

