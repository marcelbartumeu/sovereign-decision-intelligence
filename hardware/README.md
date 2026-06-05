# Arduino Dashboard Controller

This project connects a physical Arduino controller to your Andorra dashboard using **Web Serial API**, allowing you to control scenarios and years with physical buttons and a slider.

## Hardware Requirements

- **Any Arduino board** (Uno, Nano, ESP32, etc.)
- 4 push buttons
- 1 potentiometer (slider) - 10kΩ recommended
- Jumper wires
- Breadboard (optional)
- USB cable to connect Arduino to computer

## Hardware Setup

1. **Connect the buttons:**
   - Button 1 (Current) → Pin D2 → GND
   - Button 2 (Overgrowth) → Pin D3 → GND
   - Button 3 (Degrowth) → Pin D4 → GND
   - Button 4 (Continuity) → Pin D5 → GND
   - All buttons use internal pull-up resistors (no external resistors needed)

2. **Connect the potentiometer:**
   - One leg to 3.3V (or 5V for Arduino Uno)
   - One leg to GND
   - Wiper (middle pin) to analog pin A1

3. **Optional LED indicator:**
   - LED → Pin 13 → Resistor (220Ω) → GND

## Software Setup

### 1. Install Arduino Libraries

Open Arduino IDE → `Tools → Manage Libraries → Install:`
- **ArduinoJson** (by Benoit Blanchon) - Optional, for JSON formatting

**Note:** No WiFi or WebSocket libraries needed! This uses simple Serial communication.

### 2. Upload Arduino Code

1. Open `ScenarioSlider_Serial.ino` in Arduino IDE
2. Select your board:
   - `Tools → Board → Arduino AVR Boards → Arduino Uno` (or your board)
   - Or `Tools → Board → ESP32 Arduino → ESP32 Dev Module` (if using ESP32)
3. Select the correct COM port: `Tools → Port`
4. Click **Upload** button
5. Open Serial Monitor (`Tools → Serial Monitor`) at **115200 baud** to verify it's working

### 3. Start Dashboard

1. **Start a local web server:**
   ```bash
   cd "Front end"
   python3 -m http.server 8000
   ```

2. **Open in Chrome or Edge browser:**
   ```
   http://localhost:8000/Dashboard.HTML
   ```
   
   ⚠️ **Important:** Web Serial API only works in Chrome/Edge, not Firefox/Safari

3. **Connect Arduino:**
   - Click **"🔌 Connect Arduino"** button in the dashboard header
   - Browser will show a port selection dialog
   - Select your Arduino's COM port (e.g., "COM3" or "/dev/ttyUSB0")
   - Click "Connect"

4. **Done!** 🎉
   - Press buttons to change scenarios
   - Move slider to change years
   - Status shows "Connected" when working

## Usage

### Button Controls
- **Button 1 (D2):** Switch to Current scenario
- **Button 2 (D3):** Switch to Overgrowth scenario
- **Button 3 (D4):** Switch to Degrowth scenario
- **Button 4 (D5):** Switch to Continuity scenario

### Slider Control
- **Potentiometer (A1):** Adjusts year selection
  - Current scenario: 2014-2024 range
  - Future scenarios: 2024-2034 range

## Features

- ✅ **Real-time control:** Physical buttons and slider directly control dashboard
- ✅ **No server needed:** Direct USB connection, no Python server required
- ✅ **Low latency:** Fast response time (~10-20ms)
- ✅ **Visual feedback:** LED blinks to show Arduino is active
- ✅ **Status indicator:** Dashboard shows connection status
- ✅ **Works offline:** No network connection required
- ✅ **Easy debugging:** Can use Arduino Serial Monitor

## Troubleshooting

### "Web Serial API not supported"
- **Solution:** Use Chrome or Edge browser (not Firefox/Safari)

### "No port selected"
- **Solution:** 
  - Make sure Arduino is connected via USB
  - Check Device Manager (Windows) or `ls /dev/tty*` (Mac/Linux)
  - Try unplugging and reconnecting USB

### "Failed to connect"
- **Solution:**
  - Close Arduino Serial Monitor if open (only one program can use the port)
  - Try disconnecting and reconnecting USB
  - Check if another program is using the port
  - Restart browser

### Buttons/Slider not working
- **Solution:**
  - Check browser console (F12) for messages
  - Verify Arduino is sending JSON messages (check Serial Monitor)
  - Ensure baud rate is 115200
  - Check button/slider wiring

### Messages not parsing
- **Solution:** Arduino should send JSON like:
  ```json
  {"type":"scenario_change","scenario":0,"name":"Current"}
  {"type":"year_change","year":2024}
  ```
  - Check Serial Monitor shows these messages
  - Ensure messages end with newline (`\n`)

## Customization

### Change Scenario Mapping
Edit the `SCENARIOS` array in `ScenarioSlider_Serial.ino`:
```cpp
const int SCENARIOS[] = {0, 1, 2, 3}; // Current, Overgrowth, Degrowth, Continuity
```

### Adjust Update Rate
Modify the `UPDATE_INTERVAL` in `ScenarioSlider_Serial.ino`:
```cpp
const unsigned long UPDATE_INTERVAL = 50; // Update every 50ms
```

### Change Button Pins
Edit the `BUTTON_PINS` array:
```cpp
const int BUTTON_PINS[] = {2, 3, 4, 5}; // Change to your preferred pins
```

### Change Slider Pin
Edit `SLIDER_PIN`:
```cpp
const int SLIDER_PIN = A1; // Change to your preferred analog pin
```

## File Structure

```
Arduino/
├── ScenarioSlider_Serial.ino    # Arduino code (Serial version)
├── WEBSERIAL_SETUP.md            # Quick setup guide
├── WEBSERIAL_VS_WEBSOCKET.md     # Comparison document
└── README.md                      # This file
```

## Technical Details

- **Communication:** USB Serial (Web Serial API)
- **Data format:** JSON messages
- **Baud rate:** 115200
- **Update rate:** 50ms (configurable)
- **Analog resolution:** 10-bit (0-1023)
- **Scenario mapping:** 4 scenarios (0-3)
- **Year ranges:** 
  - Current: 2014-2024
  - Future scenarios: 2024-2034

## Message Format

Arduino sends JSON messages over Serial:

**Scenario Change:**
```json
{"type":"scenario_change","scenario":0,"name":"Current"}
```

**Year Change:**
```json
{"type":"year_change","year":2024}
```

## Advantages

✅ **Simpler:** No Python server, no WiFi configuration  
✅ **Faster:** Direct USB connection, lower latency  
✅ **More Reliable:** No network issues, works offline  
✅ **Easier Setup:** Just connect USB and click button  
✅ **Better Debugging:** Can use Serial Monitor  

## Browser Compatibility

- ✅ **Chrome** (recommended)
- ✅ **Edge** (recommended)
- ❌ **Firefox** (not supported)
- ❌ **Safari** (not supported)

For more details, see `WEBSERIAL_SETUP.md`.
