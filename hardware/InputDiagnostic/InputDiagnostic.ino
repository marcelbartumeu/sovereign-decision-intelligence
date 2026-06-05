/*
 * Andorra Dashboard — Input Diagnostic Sketch
 *
 * Upload this instead of ScenarioSlider.ino to verify every input is wired
 * correctly before going live.
 *
 * Open Serial Monitor at 115 200 baud, line ending = Newline.
 *
 * On boot:  prints a full pin map + current state of every input.
 * After that: prints only CHANGES, so any click / turn / flip shows up
 * immediately with a human-readable label and description of what it does.
 *
 * Library required: Encoder (Paul Stoffregen — Arduino Library Manager)
 *
 * ── Toggle polarity ────────────────────────────────────────────────────────
 *   INPUT_PULLUP + toggle switch wired to GND:
 *     HIGH = switch open  = ON  (state sent to dashboard: true)
 *     LOW  = switch closed = OFF (state sent to dashboard: false)
 *
 * ── Push button polarity ───────────────────────────────────────────────────
 *   INPUT_PULLUP + button wired to GND:
 *     FALLING edge (HIGH→LOW) = PRESSED
 */

#include <Encoder.h>

// ── Pin definitions — mirrors ScenarioSlider.ino exactly ────────────────────

#define ENC1_A    2     // interrupt
#define ENC1_B    3     // interrupt
#define ENC1_BTN  50    // push = simulation toggle

#define ENC2_A    18    // interrupt
#define ENC2_B    19    // interrupt
#define ENC2_BTN  52    // push = select agent

#define POT_YEAR  A0    // slide → year 2010-2049
#define POT_ZOOM  A1    // slide → zoom band

#define BTN_MAIN           22
#define BTN_ECONOMIC       24
#define BTN_SOCIAL         26
#define BTN_ENVIRONMENTAL  27
#define BTN_INFRASTRUCTURE 25
#define BTN_AGENTS         23

#define TOG_HISTORICAL  30
#define TOG_OVERGROWTH  32
#define TOG_DEGROWTH    35
#define TOG_CONTINUITY  33
#define TOG_DENSITY     31

// ── Tables ───────────────────────────────────────────────────────────────────

static const uint8_t BTN_COUNT = 6;
static const uint8_t TOG_COUNT = 5;

static const int BTN_PINS[BTN_COUNT] = {
    BTN_MAIN, BTN_ECONOMIC, BTN_SOCIAL,
    BTN_ENVIRONMENTAL, BTN_INFRASTRUCTURE, BTN_AGENTS
};
static const char* BTN_LABELS[BTN_COUNT] = {
    "main", "economic", "social",
    "environmental", "infrastructure", "agents"
};

static const int TOG_PINS[TOG_COUNT] = {
    TOG_HISTORICAL, TOG_OVERGROWTH, TOG_DEGROWTH, TOG_CONTINUITY, TOG_DENSITY
};
static const char* TOG_LABELS[TOG_COUNT] = {
    "historical (idx 0)", "overgrowth (idx 1)", "degrowth (idx 2)",
    "continuity (idx 3)", "density (idx 4)"
};

static const char* ZOOM_LABELS[5] = {
    "Street", "Block", "Parish", "Valley", "Country"
};

// ── Encoders ─────────────────────────────────────────────────────────────────

Encoder enc1(ENC1_A, ENC1_B);
Encoder enc2(ENC2_A, ENC2_B);

// ── State ────────────────────────────────────────────────────────────────────

long enc1LastDetent = 0;
long enc2LastDetent = 0;

bool enc1BtnLast = HIGH;
bool enc2BtnLast = HIGH;

bool btnLast[BTN_COUNT];
bool togLast[TOG_COUNT];

int lastYearRaw = -1;
int lastZoomRaw = -1;

static const int POT_NOISE = 8;   // ADC counts — ignores jitter below this

// ── Setup ────────────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    while (!Serial) { ; }
    delay(200);

    pinMode(ENC1_BTN, INPUT_PULLUP);
    pinMode(ENC2_BTN, INPUT_PULLUP);

    for (uint8_t i = 0; i < BTN_COUNT; i++) {
        pinMode(BTN_PINS[i], INPUT_PULLUP);
        btnLast[i] = digitalRead(BTN_PINS[i]);
    }
    for (uint8_t i = 0; i < TOG_COUNT; i++) {
        pinMode(TOG_PINS[i], INPUT_PULLUP);
        togLast[i] = digitalRead(TOG_PINS[i]);
    }

    enc1BtnLast = digitalRead(ENC1_BTN);
    enc2BtnLast = digitalRead(ENC2_BTN);
    lastYearRaw = analogRead(POT_YEAR);
    lastZoomRaw = analogRead(POT_ZOOM);

    printBanner();
    printInitialState();
    Serial.println(F("\n--- Live changes below (only changes print) ---\n"));
}

// ── Banner ───────────────────────────────────────────────────────────────────

void printBanner() {
    Serial.println(F("===================================================="));
    Serial.println(F("  Andorra Dashboard — Input Diagnostic v1.4"));
    Serial.println(F("===================================================="));
    Serial.println(F("PIN MAP:"));
    Serial.println(F("  ENC1  map layers   A=D2   B=D3   BTN=D50"));
    Serial.println(F("  ENC2  agent hover  A=D18  B=D19  BTN=D52"));
    Serial.println(F("  POT   year=A0   zoom=A1"));
    Serial.println(F("  BTN   D22=main  D24=econ  D26=social"));
    Serial.println(F("        D27=env   D25=infra  D23=agents"));
    Serial.println(F("  TOG   D30=historical  D32=overgrowth  D35=degrowth"));
    Serial.println(F("        D33=continuity  D31=density"));
    Serial.println(F("  Toggle polarity: HIGH=open=ON  LOW=GND=OFF"));
    Serial.println(F("----------------------------------------------------"));
}

// ── Initial state ─────────────────────────────────────────────────────────────

void printInitialState() {
    Serial.println(F("INITIAL STATE:"));

    Serial.print(F("  ENC1_BTN D50 = "));
    Serial.println(enc1BtnLast == LOW ? F("PRESSED  <-- stuck?") : F("released  OK"));

    Serial.print(F("  ENC2_BTN D52 = "));
    Serial.println(enc2BtnLast == LOW ? F("PRESSED  <-- stuck?") : F("released  OK"));

    for (uint8_t i = 0; i < BTN_COUNT; i++) {
        Serial.print(F("  BTN D"));
        Serial.print(BTN_PINS[i]);
        Serial.print(F(" ("));
        Serial.print(BTN_LABELS[i]);
        Serial.print(F(") = "));
        Serial.println(btnLast[i] == LOW ? F("PRESSED  <-- stuck?") : F("released  OK"));
    }

    for (uint8_t i = 0; i < TOG_COUNT; i++) {
        Serial.print(F("  TOG D"));
        Serial.print(TOG_PINS[i]);
        Serial.print(F(" ("));
        Serial.print(TOG_LABELS[i]);
        Serial.print(F(") = "));
        // HIGH = open circuit = ON
        Serial.println(togLast[i] == HIGH ? F("ON") : F("off"));
    }

    Serial.print(F("  POT_YEAR A0  raw="));
    Serial.print(lastYearRaw);
    Serial.print(F("  year="));
    Serial.println(rawToYear(lastYearRaw));

    Serial.print(F("  POT_ZOOM A1  raw="));
    Serial.print(lastZoomRaw);
    Serial.print(F("  zoom="));
    Serial.println(rawToZoom(lastZoomRaw));
}

// ── Loop ─────────────────────────────────────────────────────────────────────

void loop() {
    checkEncoders();
    checkEncoderButtons();
    checkPushButtons();
    checkToggles();
    checkPots();
}

// ── Encoder rotation ──────────────────────────────────────────────────────────

void checkEncoders() {
    long d1 = enc1.read() / 4;
    if (d1 != enc1LastDetent) {
        Serial.print(F("[ENC1 map layer]  "));
        Serial.print(d1 > enc1LastDetent ? F("CW  -> next layer  ") : F("CCW -> prev layer  "));
        Serial.print(F("detent="));
        Serial.println(d1);
        enc1LastDetent = d1;
    }

    long d2 = enc2.read() / 4;
    if (d2 != enc2LastDetent) {
        Serial.print(F("[ENC2 agent]      "));
        Serial.print(d2 > enc2LastDetent ? F("CW  -> next agent  ") : F("CCW -> prev agent  "));
        Serial.print(F("detent="));
        Serial.println(d2);
        enc2LastDetent = d2;
    }
}

// ── Encoder buttons ───────────────────────────────────────────────────────────

void checkEncoderButtons() {
    bool e1 = digitalRead(ENC1_BTN);
    if (e1 != enc1BtnLast) {
        Serial.print(F("[ENC1_BTN D50]  "));
        Serial.println(e1 == LOW ? F("PRESSED -> simulation toggle") : F("released"));
        enc1BtnLast = e1;
    }

    bool e2 = digitalRead(ENC2_BTN);
    if (e2 != enc2BtnLast) {
        Serial.print(F("[ENC2_BTN D52]  "));
        Serial.println(e2 == LOW ? F("PRESSED -> select agent") : F("released"));
        enc2BtnLast = e2;
    }
}

// ── Push buttons ──────────────────────────────────────────────────────────────

void checkPushButtons() {
    for (uint8_t i = 0; i < BTN_COUNT; i++) {
        bool now = digitalRead(BTN_PINS[i]);
        if (now == btnLast[i]) continue;
        btnLast[i] = now;
        Serial.print(F("[BTN D"));
        Serial.print(BTN_PINS[i]);
        Serial.print(F(" "));
        Serial.print(BTN_LABELS[i]);
        Serial.print(F("]  "));
        Serial.println(now == LOW ? F("PRESSED") : F("released"));
    }
}

// ── Toggle switches ───────────────────────────────────────────────────────────
// HIGH = switch open  = ON  (dashboard overlay enabled)
// LOW  = switch closed = OFF (dashboard overlay disabled)

void checkToggles() {
    for (uint8_t i = 0; i < TOG_COUNT; i++) {
        bool now = digitalRead(TOG_PINS[i]);
        if (now == togLast[i]) continue;
        togLast[i] = now;
        Serial.print(F("[TOG D"));
        Serial.print(TOG_PINS[i]);
        Serial.print(F(" "));
        Serial.print(TOG_LABELS[i]);
        Serial.print(F("]  "));
        Serial.println(now == HIGH ? F("ON  (overlay enabled)") : F("off (overlay disabled)"));
    }
}

// ── Potentiometers ────────────────────────────────────────────────────────────

void checkPots() {
    int y = analogRead(POT_YEAR);
    if (abs(y - lastYearRaw) > POT_NOISE) {
        lastYearRaw = y;
        Serial.print(F("[POT_YEAR A0]  raw="));
        Serial.print(y);
        Serial.print(F("  year="));
        Serial.println(rawToYear(y));
    }

    int z = analogRead(POT_ZOOM);
    if (abs(z - lastZoomRaw) > POT_NOISE) {
        lastZoomRaw = z;
        Serial.print(F("[POT_ZOOM A1]  raw="));
        Serial.print(z);
        Serial.print(F("  zoom="));
        Serial.println(rawToZoom(z));
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

int rawToYear(int raw) {
    return constrain(map(raw, 0, 950, 2010, 2049), 2010, 2049);
}

const char* rawToZoom(int raw) {
    int idx = constrain((long)raw * 5 / 1024, 0, 4);
    return ZOOM_LABELS[idx];
}
