/*
 * ButtonTest — no libraries required
 *
 * Wiring: D24 ──┤ button ├── GND
 *
 * Open Serial Monitor at 115200 baud.
 * Press the button — you should see: PRESSED
 * Release it — you should see: RELEASED
 *
 * If you see nothing: wiring problem or wrong baud rate.
 * If sketch won't upload: wrong board selected (needs Mega 2560).
 */

#define BTN_PIN 24

bool lastState = HIGH;

void setup() {
    Serial.begin(115200);
    pinMode(BTN_PIN, INPUT_PULLUP);
    Serial.println("ButtonTest ready — press the button on D24");
}

void loop() {
    bool state = digitalRead(BTN_PIN);
    if (state != lastState) {
        lastState = state;
        Serial.println(state == LOW ? "PRESSED" : "RELEASED");
    }
    delay(10);
}
