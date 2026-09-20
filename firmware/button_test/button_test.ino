// One Qenker-style 30 mm LED arcade button on an Arduino UNO R4 (Minima or WiFi) as the "lost me" pad.
//
// Wiring (docs/TOTEM-Q.md §1, same D2 / INPUT_PULLUP convention as firmware/totem):
//   Brown  -> GND
//   Red    -> D2
//   Orange -> D5 (button LED, held on) or 5V
//
// The board enumerates as a USB keyboard and every debounced press types one Space. The Live view
// already maps Space to a tap (frontend/src/views/Live.tsx onKey -> doTap), so nothing on the laptop
// has to find the port: the browser tab just has to be focused. Needs the R4's native USB
// (Keyboard.h); a classic UNO cannot do HID.
//
// SERIAL_TAP 1 additionally prints "TAP\n" at 115200 for the pyserial bridge
// (neuropace/totem/bridge.py, SerialTotem). Leave it 0 while the bridge is attached, or each press
// is counted twice (once as a Space "key" flag, once as a serial "tap" flag).
// If presses double-count on their own, raise DEBOUNCE_MS.

#include <Keyboard.h>

#define SERIAL_TAP 0

constexpr int BUTTON_PIN = 2;
constexpr int LED_PIN = 5;
constexpr unsigned long DEBOUNCE_MS = 35;

bool stable = HIGH;  // debounced state, HIGH = released (pull-up)
bool previous = HIGH;
unsigned long changedAt = 0;

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
  Keyboard.begin();
#if SERIAL_TAP
  Serial.begin(115200);
#endif
}

void loop() {
#if SERIAL_TAP
  while (Serial.available()) Serial.read();  // bridge commands: not used here
#endif
  bool reading = digitalRead(BUTTON_PIN);
  if (reading != previous) changedAt = millis();
  if (millis() - changedAt >= DEBOUNCE_MS && reading != stable) {
    stable = reading;
    if (stable == LOW) {
      Keyboard.write(' ');  // press + release
#if SERIAL_TAP
      Serial.println("TAP");
#endif
    }
  }
  previous = reading;
  delay(2);
}
