/*
 * Andorra Dashboard Physical Controller — Mega 2560
 * Version 1.4
 *
 * Hardware:
 *   - 2× EC11 rotary encoders with push (interrupt pins 2/3 and 18/19)
 *   - 2× 10K linear slide potentiometers (A0, A1)
 *   - 6× STARELO momentary push buttons
 *   - 5× Taiss MTS-101 mini toggle switches
 *
 * Libraries required (install via Arduino Library Manager):
 *   - Encoder     by Paul Stoffregen
 *   - ArduinoJson by Benoit Blanchon v6
 *
 * ── Serial protocol: JSON at 115200 baud, one message per line ───────────────
 *
 *   {"type":"status","value":"ready"}
 *     Sent once at startup and every 5 s as a keep-alive heartbeat.
 *
 *   {"type":"year","value":2027}
 *     Coarse year from slide potentiometer A0 (range 2010–2049).
 *     Sent only when the mapped integer year changes.
 *
 *   {"type":"zoom","value":"Parish"}
 *     Zoom band from slide potentiometer A1.
 *     Bands: Street | Block | Parish | Valley | Country
 *
 *   {"type":"encoder","id":1,"direction":"CW","position":4}
 *     ENC1 rotation — JS interprets as map-layer cycling.
 *     id=1: CW = next layer, CCW = previous layer.
 *     position = absolute detent count (can be negative, JS wraps with modulo).
 *
 *   {"type":"encoder","id":2,"direction":"CW","position":3}
 *     ENC2 rotation — JS interprets as agent hover.
 *     id=2: CW = next agent, CCW = previous agent.
 *     position = absolute detent count (JS wraps modulo agent count).
 *
 *   {"type":"encoder_btn","id":1}
 *     ENC1 button — JS toggles the bus/scenario simulation on/off.
 *
 *   {"type":"encoder_btn","id":2}
 *     ENC2 button — JS confirms selection of the currently hovered agent.
 *
 *   {"type":"tab","value":"social"}
 *     Momentary push button press — switches dashboard tab.
 *     values: main | economic | social | environmental | infrastructure | agents
 *
 *   {"type":"toggle","scenario":"overgrowth","state":true}
 *     Scenario overlay toggle switch changed.
 *     state: true = ON (switch open, pin HIGH), false = OFF (switch closed, pin LOW).
 *     Emitted for all 5 toggles at startup with current positions, then on change.
 *
 * ── Toggle polarity ───────────────────────────────────────────────────────────
 *   All inputs use INPUT_PULLUP.
 *   Toggle switches: open circuit = HIGH = ON (state: true)
 *                    closed to GND = LOW = OFF (state: false)
 *   Push buttons:    pressed = LOW (falling edge triggers message)
 */

#include <Encoder.h>
#include <ArduinoJson.h>

// ── Pin definitions ───────────────────────────────────────────────────────────

// Rotary encoder 1 — map-layer selector (rotation) + simulation toggle (push)
#define ENC1_A    2     // interrupt pin
#define ENC1_B    3     // interrupt pin
#define ENC1_BTN  50

// Rotary encoder 2 — agent hover (rotation) + agent select (push)
#define ENC2_A    18    // interrupt pin
#define ENC2_B    19    // interrupt pin
#define ENC2_BTN  52

// Slide potentiometers
#define POT_YEAR  A0    // Year 2010–2049
#define POT_ZOOM  A1    // Zoom level (Street → Country)

// Momentary push buttons — dashboard tabs
#define BTN_MAIN           22
#define BTN_ECONOMIC       24
#define BTN_SOCIAL         26
#define BTN_ENVIRONMENTAL  27
#define BTN_INFRASTRUCTURE 25
#define BTN_AGENTS         23

// Toggle switches — scenario overlays
#define TOG_HISTORICAL  30
#define TOG_OVERGROWTH  32
#define TOG_DEGROWTH    35
#define TOG_CONTINUITY  33
#define TOG_DENSITY     31

// ── Constants ─────────────────────────────────────────────────────────────────

static const uint8_t  BTN_COUNT    = 6;
static const uint8_t  TOG_COUNT    = 5;
static const uint8_t  POT_SMOOTH   = 5;      // rolling-average samples
static const uint16_t DEBOUNCE_MS  = 50;     // ms
static const uint32_t HEARTBEAT_MS = 5000;   // ms between keep-alive messages

static const int YEAR_MIN = 2010;
static const int YEAR_MAX = 2049;

static const int ZOOM_BAND_COUNT = 5;

// ── Lookup tables ─────────────────────────────────────────────────────────────

static const int BTN_PINS[BTN_COUNT] = {
    BTN_MAIN, BTN_ECONOMIC, BTN_SOCIAL,
    BTN_ENVIRONMENTAL, BTN_INFRASTRUCTURE, BTN_AGENTS
};
static const char* BTN_TABS[BTN_COUNT] = {
    "main", "economic", "social",
    "environmental", "infrastructure", "agents"
};

static const int TOG_PINS[TOG_COUNT] = {
    TOG_HISTORICAL, TOG_OVERGROWTH, TOG_DEGROWTH, TOG_CONTINUITY, TOG_DENSITY
};
static const char* TOG_SCENARIOS[TOG_COUNT] = {
    "historical", "overgrowth", "degrowth", "continuity", "density"
};

static const char* ZOOM_LABELS[ZOOM_BAND_COUNT] = {
    "Street", "Block", "Parish", "Valley", "Country"
};

// ── Encoder instances (must use interrupt pins) ───────────────────────────────

Encoder enc1(ENC1_B, ENC1_A);
Encoder enc2(ENC2_B, ENC2_A);

// ── State ─────────────────────────────────────────────────────────────────────

long enc1RawPos = 0;
long enc2RawPos = 0;

bool     enc1BtnLast = HIGH;
uint32_t enc1BtnTime = 0;
bool     enc2BtnLast = HIGH;
uint32_t enc2BtnTime = 0;

bool     btnLast[BTN_COUNT];
uint32_t btnTime[BTN_COUNT];

bool togLast[TOG_COUNT];

int     yearBuf[POT_SMOOTH];
uint8_t yearBufIdx = 0;
int     zoomBuf[POT_SMOOTH];
uint8_t zoomBufIdx = 0;

int lastYear     = -1;
int lastZoomBand = -1;

uint32_t lastHeartbeat = 0;

// ── Helpers ───────────────────────────────────────────────────────────────────

static int rollingAvg(const int* buf, uint8_t len) {
    long sum = 0;
    for (uint8_t i = 0; i < len; i++) sum += buf[i];
    return (int)(sum / len);
}

static void sendJSON(JsonDocument& doc) {
    serializeJson(doc, Serial);
    Serial.println();
    Serial.flush();
}

static int rawToZoomBand(int raw) {
    int band = (long)raw * ZOOM_BAND_COUNT / 1024;
    if (band < 0) band = 0;
    if (band >= ZOOM_BAND_COUNT) band = ZOOM_BAND_COUNT - 1;
    return band;
}

// ── Setup ─────────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);

    pinMode(ENC1_BTN, INPUT_PULLUP);
    pinMode(ENC2_BTN, INPUT_PULLUP);

    for (uint8_t i = 0; i < BTN_COUNT; i++) {
        pinMode(BTN_PINS[i], INPUT_PULLUP);
        btnLast[i] = HIGH;
        btnTime[i] = 0;
    }

    for (uint8_t i = 0; i < TOG_COUNT; i++) {
        pinMode(TOG_PINS[i], INPUT_PULLUP);
        togLast[i] = digitalRead(TOG_PINS[i]);
    }

    // Pre-fill potentiometer buffers with current readings so first
    // averages are stable immediately on power-up
    for (uint8_t i = 0; i < POT_SMOOTH; i++) {
        yearBuf[i] = analogRead(POT_YEAR);
        zoomBuf[i] = analogRead(POT_ZOOM);
    }

    // Emit initial toggle states so the dashboard knows the starting
    // configuration without the user having to flip each switch once.
    // HIGH = open circuit = ON (state: true)
    for (uint8_t i = 0; i < TOG_COUNT; i++) {
        StaticJsonDocument<64> doc;
        doc["type"]     = "toggle";
        doc["scenario"] = TOG_SCENARIOS[i];
        doc["state"]    = (togLast[i] == HIGH);
        sendJSON(doc);
    }

    Serial.println(F("{\"type\":\"status\",\"value\":\"ready\"}"));
    lastHeartbeat = millis();
}

// ── Main loop ─────────────────────────────────────────────────────────────────

void loop() {
    checkEncoders();
    checkEncoderButtons();
    checkPushButtons();
    checkToggleSwitches();
    checkPotentiometers();
    checkHeartbeat();
}

// ── Encoder rotation ──────────────────────────────────────────────────────────
// EC11 produces 4 raw counts per physical detent.
// ENC1 → JS cycles map layers (base→agents→growth→tourism→accessibility→population)
// ENC2 → JS cycles hovered agent (10 agents total, wraps)

void checkEncoders() {
    long newRaw1 = enc1.read();
    if (newRaw1 != enc1RawPos) {
        long detentNew = newRaw1 / 4;
        long detentOld = enc1RawPos / 4;
        if (detentNew != detentOld) {
            StaticJsonDocument<64> doc;
            doc["type"]      = "encoder";
            doc["id"]        = 2;
            doc["direction"] = (newRaw1 > enc1RawPos) ? "CW" : "CCW";
            doc["position"]  = detentNew;
            sendJSON(doc);
        }
        enc1RawPos = newRaw1;
    }

    long newRaw2 = enc2.read();
    if (newRaw2 != enc2RawPos) {
        long detentNew = newRaw2 / 4;
        long detentOld = enc2RawPos / 4;
        if (detentNew != detentOld) {
            StaticJsonDocument<64> doc;
            doc["type"]      = "encoder";
            doc["id"]        = 1;
            doc["direction"] = (newRaw2 > enc2RawPos) ? "CW" : "CCW";
            doc["position"]  = detentNew;
            sendJSON(doc);
        }
        enc2RawPos = newRaw2;
    }
}

// ── Encoder push buttons ──────────────────────────────────────────────────────
// ENC1 push → JS toggles bus/scenario simulation on/off
// ENC2 push → JS selects the currently hovered agent

void checkEncoderButtons() {
    uint32_t now = millis();

    bool enc1BtnNow = digitalRead(ENC1_BTN);
    if (enc1BtnLast == HIGH && enc1BtnNow == LOW &&
        (now - enc1BtnTime) > DEBOUNCE_MS) {
        enc1BtnTime = now;
        StaticJsonDocument<32> doc;
        doc["type"] = "encoder_btn";
        doc["id"]   = 2;
        sendJSON(doc);
    }
    enc1BtnLast = enc1BtnNow;

    bool enc2BtnNow = digitalRead(ENC2_BTN);
    if (enc2BtnLast == HIGH && enc2BtnNow == LOW &&
        (now - enc2BtnTime) > DEBOUNCE_MS) {
        enc2BtnTime = now;
        StaticJsonDocument<32> doc;
        doc["type"] = "encoder_btn";
        doc["id"]   = 1;
        sendJSON(doc);
    }
    enc2BtnLast = enc2BtnNow;
}

// ── Momentary push buttons — fire on FALLING edge only ───────────────────────

void checkPushButtons() {
    uint32_t now = millis();
    for (uint8_t i = 0; i < BTN_COUNT; i++) {
        bool nowState = digitalRead(BTN_PINS[i]);
        if (btnLast[i] == HIGH && nowState == LOW &&
            (now - btnTime[i]) > DEBOUNCE_MS) {
            btnTime[i] = now;
            StaticJsonDocument<48> doc;
            doc["type"]  = "tab";
            doc["value"] = BTN_TABS[i];
            sendJSON(doc);
        }
        btnLast[i] = nowState;
    }
}

// ── Toggle switches — send on state change only ───────────────────────────────
// HIGH = switch open = ON  (state: true)
// LOW  = switch closed to GND = OFF  (state: false)

void checkToggleSwitches() {
    for (uint8_t i = 0; i < TOG_COUNT; i++) {
        bool nowState = digitalRead(TOG_PINS[i]);
        if (nowState != togLast[i]) {
            togLast[i] = nowState;
            StaticJsonDocument<64> doc;
            doc["type"]     = "toggle";
            doc["scenario"] = TOG_SCENARIOS[i];
            doc["state"]    = (nowState == HIGH);
            sendJSON(doc);
        }
    }
}

// ── Slide potentiometers ──────────────────────────────────────────────────────

void checkPotentiometers() {
    // Year (A0)
    yearBuf[yearBufIdx] = analogRead(POT_YEAR);
    yearBufIdx = (yearBufIdx + 1) % POT_SMOOTH;
    int yearRaw = rollingAvg(yearBuf, POT_SMOOTH);
    int year = map(yearRaw, 950, 0, YEAR_MIN, YEAR_MAX);
    year = constrain(year, YEAR_MIN, YEAR_MAX);
    if (year != lastYear) {
        lastYear = year;
        StaticJsonDocument<48> doc;
        doc["type"]  = "year";
        doc["value"] = year;
        sendJSON(doc);
    }

    // Zoom (A1)
    zoomBuf[zoomBufIdx] = analogRead(POT_ZOOM);
    zoomBufIdx = (zoomBufIdx + 1) % POT_SMOOTH;
    int zoomRaw  = rollingAvg(zoomBuf, POT_SMOOTH);
    int zoomBand = rawToZoomBand(zoomRaw);
    if (zoomBand != lastZoomBand) {
        lastZoomBand = zoomBand;
        StaticJsonDocument<64> doc;
        doc["type"]  = "zoom";
        doc["value"] = ZOOM_LABELS[zoomBand];
        sendJSON(doc);
    }
}

// ── Heartbeat ─────────────────────────────────────────────────────────────────

void checkHeartbeat() {
    uint32_t now = millis();
    if (now - lastHeartbeat < HEARTBEAT_MS) return;
    lastHeartbeat = now;
    Serial.println(F("{\"type\":\"status\",\"value\":\"ready\"}"));
}
