// Reflow totem for Arduino UNO R4 (WiFi or Minima) — direct-USB fallback path; the current target
// is the UNO Q 4 GB BLE relay (firmware/uno_q_relay/, experimental, uncompiled). TDD §4.
//
// Touch pad on D2 (jumper -> foil pad) = "lost me". Sends "TAP <millis>" over USB serial.
// UNO R4 WiFi LED matrix: row 0 = fit meter (FIT 0-8), rows 2-6 = one dot per saved span (DOT n),
// row 7 = 2 s sweep on PULSE ("catch-up ready"). Minima: LED_BUILTIN blinks on PULSE.
//
// Serial protocol, 115200 baud, newline terminated:
//   totem -> laptop:  HELLO totem 1 <board> | TAP <millis> | PONG
//   laptop -> totem:  PING | FIT <0-8> | DOT <n> | PULSE | CLEAR
//
// Set USE_CAPTOUCH to 0 to use a plain pushbutton between D2 and GND instead (INPUT_PULLUP).

#define USE_CAPTOUCH 1
#define TOUCH_PIN 2
#define TOUCH_THRESHOLD 1500   // raise if it triggers on its own, lower if a firm press is missed
#define DEBOUNCE_MS 250

#if USE_CAPTOUCH
#include "Arduino_CapacitiveTouch.h"
CapacitiveTouch pad = CapacitiveTouch(TOUCH_PIN);
#endif

#if defined(ARDUINO_UNOR4_WIFI)
#include "Arduino_LED_Matrix.h"
ArduinoLEDMatrix matrix;
uint8_t frame[8][12];
const char *BOARD = "unor4wifi";
#else
const char *BOARD = "unor4minima";
#endif

unsigned long lastTap = 0;
bool wasTouched = false;
int fitLevel = 0;
int dots = 0;
unsigned long pulseUntil = 0;
String line;

void render() {
#if defined(ARDUINO_UNOR4_WIFI)
  memset(frame, 0, sizeof(frame));
  // fit meter: 0..8 -> 0..12 LEDs
  int lit = (fitLevel * 12) / 8;
  for (int c = 0; c < 12; c++) frame[0][c] = c < lit ? 1 : 0;
  int n = dots > 60 ? 60 : dots;
  for (int i = 0; i < n; i++) frame[2 + i / 12][i % 12] = 1;
  if (millis() < pulseUntil) {
    int pos = (millis() / 60) % 12;
    frame[7][pos] = 1;
    frame[7][(pos + 11) % 12] = 1;
  }
  matrix.renderBitmap(frame, 8, 12);
#else
  digitalWrite(LED_BUILTIN, millis() < pulseUntil ? ((millis() / 120) % 2) : LOW);
#endif
}

void handle(const String &cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
    Serial.print("HELLO totem 1 "); Serial.println(BOARD);
  } else if (cmd.startsWith("FIT ")) {
    fitLevel = constrain(cmd.substring(4).toInt(), 0, 8);
  } else if (cmd.startsWith("DOT ")) {
    dots = constrain(cmd.substring(4).toInt(), 0, 60);
  } else if (cmd == "PULSE") {
    pulseUntil = millis() + 2000;
  } else if (cmd == "CLEAR") {
    fitLevel = 0; dots = 0; pulseUntil = 0;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
#if defined(ARDUINO_UNOR4_WIFI)
  matrix.begin();
#endif
#if USE_CAPTOUCH
  if (pad.begin()) {
    pad.setThreshold(TOUCH_THRESHOLD);
  } else {
    // unsupported pin: fall back to a pushbutton so the demo is never blocked
    pinMode(TOUCH_PIN, INPUT_PULLUP);
  }
#else
  pinMode(TOUCH_PIN, INPUT_PULLUP);
#endif
  delay(300);
  Serial.print("HELLO totem 1 "); Serial.println(BOARD);
}

bool readTouched() {
#if USE_CAPTOUCH
  return pad.isTouched();
#else
  return digitalRead(TOUCH_PIN) == LOW;
#endif
}

void loop() {
  bool touched = readTouched();
  unsigned long now = millis();
  if (touched && !wasTouched && (now - lastTap) > DEBOUNCE_MS) {
    lastTap = now;
    Serial.print("TAP "); Serial.println(now);
  }
  wasTouched = touched;

  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      line.trim();
      if (line.length()) handle(line);
      line = "";
    } else if (line.length() < 64) {
      line += c;
    }
  }
  render();
  delay(10);
}
