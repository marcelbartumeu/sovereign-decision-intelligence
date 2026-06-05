# Quick Start Guide - Arduino Dashboard Controller

## 🚀 Get Started in 3 Steps

### Step 1: Upload Arduino Code

1. Open `ScenarioSlider.ino` in Arduino IDE
2. Select your board: `Tools → Board → [Your Board]`
3. Select COM port: `Tools → Port → [Your Port]`
4. Click **Upload** button
5. ✅ Done! No WiFi or server configuration needed.

### Step 2: Start Dashboard

```bash
cd "Front end"
python3 -m http.server 8000
```

Open in **Chrome or Edge**: `http://localhost:8000/Dashboard.HTML`

### Step 3: Connect Arduino

1. Connect Arduino to computer via USB
2. Click **"🔌 Connect Arduino"** button in dashboard
3. Select your Arduino's COM port
4. Click "Connect"

**That's it!** Press buttons and move slider to control the dashboard.

---

## 📋 Hardware Setup

**Buttons:**
- Button 1 → Pin D2 → GND (Current scenario)
- Button 2 → Pin D3 → GND (Overgrowth scenario)
- Button 3 → Pin D4 → GND (Degrowth scenario)
- Button 4 → Pin D5 → GND (Continuity scenario)

**Slider:**
- Potentiometer leg 1 → 3.3V/5V
- Potentiometer leg 2 → GND
- Potentiometer wiper → Pin A1

**Optional LED:**
- LED → Pin 13 → Resistor (220Ω) → GND

---

## ⚠️ Important Notes

- **Browser:** Must use Chrome or Edge (Web Serial API requirement)
- **USB:** Arduino must be connected via USB cable
- **Serial Monitor:** Close Serial Monitor before connecting from browser (only one program can use the port)

---

## 🐛 Troubleshooting

**"Web Serial API not supported"**
→ Use Chrome or Edge browser

**"No port selected"**
→ Make sure Arduino is connected via USB

**"Failed to connect"**
→ Close Arduino Serial Monitor and try again

**Buttons/Slider not working**
→ Check browser console (F12) for errors

---

## 📚 More Information

- **Full Setup:** See `README.md`
- **Comparison:** See `WEBSERIAL_VS_WEBSOCKET.md`
- **Detailed Guide:** See `WEBSERIAL_SETUP.md`

---

## ✅ What You Get

- ✅ Physical buttons control scenarios
- ✅ Physical slider controls years
- ✅ Real-time updates
- ✅ No server needed
- ✅ Works offline
- ✅ Simple setup

Enjoy your physical dashboard controller! 🎛️

