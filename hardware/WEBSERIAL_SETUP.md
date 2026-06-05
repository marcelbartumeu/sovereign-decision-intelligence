# Web Serial API Setup Guide (Simplified)

This is the **recommended approach** - simpler, faster, and more reliable than WebSocket!

## Quick Start

### 1. Upload Arduino Code

1. Open `ScenarioSlider_Serial.ino` in Arduino IDE
2. Select your board (Arduino Uno, Nano, ESP32, etc.)
3. Select the correct COM port
4. Click Upload
5. **No WiFi configuration needed!** ✅

### 2. Open Dashboard

1. Start a local server:
   ```bash
   cd "Front end"
   python3 -m http.server 8000
   ```

2. Open in **Chrome or Edge** browser:
   ```
   http://localhost:8000/Dashboard.HTML
   ```
   
   ⚠️ **Important:** Web Serial API only works in Chrome/Edge, not Firefox/Safari

### 3. Connect Arduino

1. Connect Arduino to computer via USB
2. Click **"🔌 Connect Arduino"** button in the dashboard header
3. Browser will show a port selection dialog
4. Select your Arduino's COM port (e.g., "COM3" or "/dev/ttyUSB0")
5. Click "Connect"

### 4. Done! 🎉

- Button presses will change scenarios
- Slider will change years
- Status shows "Connected" when working

---

## Advantages Over WebSocket

✅ **No Python server needed**  
✅ **No WiFi configuration**  
✅ **No IP addresses to manage**  
✅ **Lower latency** (direct USB)  
✅ **More reliable** (no network issues)  
✅ **Works offline**  
✅ **Easier debugging** (Serial Monitor works)  

---

## Troubleshooting

### "Web Serial API not supported"
- **Solution:** Use Chrome or Edge browser (not Firefox/Safari)

### "No port selected"
- **Solution:** Make sure Arduino is connected via USB
- Check Device Manager (Windows) or `ls /dev/tty*` (Mac/Linux)

### "Failed to connect"
- **Solution:** 
  - Close Arduino Serial Monitor if open
  - Try disconnecting and reconnecting USB
  - Check if another program is using the port

### Buttons/Slider not working
- **Solution:**
  - Check browser console (F12) for messages
  - Verify Arduino is sending JSON messages
  - Open Arduino Serial Monitor to see output

### Messages not parsing
- **Solution:** Arduino sends JSON like:
  ```json
  {"type":"scenario_change","scenario":0,"name":"Current"}
  {"type":"year_change","year":2024}
  ```
  - Check Serial Monitor shows these messages
  - Ensure baud rate is 115200

---

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

---

## Hardware Setup

Same as before:
- 4 buttons on pins D2-D5 (to GND)
- Potentiometer on pin A1
- Optional LED on pin 13

---

## Code Files

- **Arduino:** `ScenarioSlider_Serial.ino` (simplified, no WiFi)
- **Dashboard:** `Dashboard.HTML` (Web Serial API integrated)

---

## That's It!

Much simpler than WebSocket - just connect USB and click the button! 🚀

