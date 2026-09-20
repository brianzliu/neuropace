// Bench test for one Qenker-style 30 mm LED arcade button on an Arduino UNO (classic or R4).
//
// Wiring (see docs/TOTEM-Q.md §1, same D2 / INPUT_PULLUP convention as the totem sketches):
//   Brown -> GND
//   Red -> D2 
//   Orange -> 5V
//
// Open Serial Monitor at 115200. Every clean press prints "TAP <n> <millis>" and toggles the
// LED; while the button is held, the on-board LED is lit. If presses double-count, raise
// DEBOUNCE_MS; if the LED is inverted, swap the two LED pins.

constexpr int BUTTON_PIN = 2;
constexpr int LED_PIN = 5;
constexpr unsigned long DEBOUNCE_MS = 35;

bool stable = HIGH;      // debounced state, HIGH = released (pull-up)
bool previous = HIGH;
unsigned long changedAt = 0;
unsigned long presses = 0;
bool ledOn = true;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_PIN, ledOn);
  delay(300);
  Serial.println("button_test ready: press the button");
}

void loop() {
  bool reading = digitalRead(BUTTON_PIN);
  if (reading != previous) changedAt = millis();
  if (millis() - changedAt >= DEBOUNCE_MS && reading != stable) {
    stable = reading;
    if (stable == LOW) {
      presses++;
      ledOn = !ledOn;
      digitalWrite(LED_PIN, ledOn);
      Serial.print("TAP "); Serial.print(presses); Serial.print(' '); Serial.println(millis());
    }
  }
  previous = reading;
  digitalWrite(LED_BUILTIN, stable == LOW);
  delay(2);
}
