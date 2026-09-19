// UNO Q MCU input for a normally-open momentary switch between D2 and GND.
// Prototype: compile and verify on UNO Q before connecting a printed press surface.
#include <Arduino_RouterBridge.h>

constexpr int BUTTON_PIN = 2;
constexpr unsigned long DEBOUNCE_MS = 35;
volatile unsigned int presses = 0;
bool stable = HIGH;
bool previous = HIGH;
unsigned long changedAt = 0;

unsigned int buttonCount() { return presses; }

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Bridge.begin();
  Bridge.provide("neuropace_button_count", buttonCount);
}

void loop() {
  bool reading = digitalRead(BUTTON_PIN);
  if (reading != previous) changedAt = millis();
  if (millis() - changedAt >= DEBOUNCE_MS && reading != stable) {
    stable = reading;
    if (stable == LOW) presses++;
  }
  previous = reading;
  delay(5);
}
