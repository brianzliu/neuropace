// Identify the three wires of an unknown pre-wired arcade button using only the UNO.
//
// Hook the three wires to A0, A1, A2 (any order). Nothing else - do NOT connect any of them to
// 5V or GND. The sketch drives one pin LOW at a time and reads the other two through their
// internal pull-ups, so at most ~0.2 mA flows no matter how the button is built.
//
// Serial Monitor at 115200. It asks you to leave the button alone, then to hold it, then prints
// which wire is which and how to move them to GND / D2 / D5 for button_test.ino.
//
// Handles the two common 3-wire variants:
//   A) plain microswitch: COM / NO / NC
//   B) illuminated, shared ground: GND / switch NO / LED+ (LED reads as a ~2-3 V "diode" level)

const int PIN[3] = {A0, A1, A2};
const char *NAME[3] = {"A0", "A1", "A2"};

enum Link { SHORT, DIODE, OPEN };

// value seen at pin `a` when pin `g` is driven LOW, in the released (r) and pressed (p) states
Link r[3][3], p[3][3];

const char *linkName(Link l) { return l == SHORT ? "short" : l == DIODE ? "LED  " : "open "; }

Link classify(int adc) {
  if (adc < 150) return SHORT;   // < ~0.75 V: wire connected straight through the switch
  if (adc > 900) return OPEN;    // > ~4.4 V: nothing connects them
  return DIODE;                  // in between: forward-biased LED (+ its resistor)
}

void measure(Link out[3][3]) {
  for (int g = 0; g < 3; g++) {
    for (int i = 0; i < 3; i++) pinMode(PIN[i], INPUT_PULLUP);
    pinMode(PIN[g], OUTPUT);
    digitalWrite(PIN[g], LOW);
    delay(5);
    for (int a = 0; a < 3; a++) {
      if (a == g) { out[g][a] = OPEN; continue; }
      long sum = 0;
      for (int k = 0; k < 8; k++) sum += analogRead(PIN[a]);
      out[g][a] = classify((int)(sum / 8));
    }
  }
  for (int i = 0; i < 3; i++) pinMode(PIN[i], INPUT_PULLUP);
}

void countdown(const char *msg, int secs) {
  Serial.println(msg);
  for (int s = secs; s > 0; s--) { Serial.print(s); Serial.print("... "); delay(1000); }
  Serial.println();
}

void dump(const char *title, Link m[3][3]) {
  Serial.println(title);
  Serial.println("  drive LOW ->  read A0    read A1    read A2");
  for (int g = 0; g < 3; g++) {
    Serial.print("  "); Serial.print(NAME[g]); Serial.print("         ");
    for (int a = 0; a < 3; a++) { Serial.print("  "); Serial.print(a == g ? "  -  " : linkName(m[g][a])); Serial.print("   "); }
    Serial.println();
  }
}

// symmetric view: are wires a and b connected (either drive direction)?
bool linked(Link m[3][3], int a, int b, Link how) { return m[a][b] == how || m[b][a] == how; }

void verdict() {
  // 1. find the pair that is open when released and shorted when pressed: {switch, common}
  int sw = -1, com = -1, third = -1;
  for (int a = 0; a < 3 && sw < 0; a++)
    for (int b = a + 1; b < 3; b++)
      if (linked(r, a, b, OPEN) && !linked(r, a, b, SHORT) && linked(p, a, b, SHORT)) {
        sw = a; com = b; third = 3 - a - b; break;
      }
  if (sw < 0) {
    Serial.println("Could not find a pair that closes when pressed. Check the wires are seated in A0-A2");
    Serial.println("and that you really held the button during step 2. Raw tables above.");
    return;
  }

  bool ledSeen = false;
  for (int g = 0; g < 3; g++) for (int a = 0; a < 3; a++) if (r[g][a] == DIODE || p[g][a] == DIODE) ledSeen = true;

  if (ledSeen) {
    // Case B: the LED's cathode shares a wire with the switch. Driving the shared GND low lights
    // the LED, so the wire that shows the LED level when driven low is GND.
    int gnd = (r[sw][third] == DIODE) ? sw : com;
    int no = 3 - gnd - third;
    Serial.println("=> Illuminated button, shared ground (case B):");
    Serial.print("   "); Serial.print(NAME[gnd]);   Serial.println("  = shared GND      -> move to UNO GND");
    Serial.print("   "); Serial.print(NAME[no]);    Serial.println("  = switch (NO)     -> move to UNO D2");
    Serial.print("   "); Serial.print(NAME[third]); Serial.println("  = LED +           -> move to UNO D5 (or 5V for always-on)");
    return;
  }

  // Case A: plain COM/NO/NC. The third wire is shorted to COM while released, open while pressed.
  for (int c = 0; c < 2; c++) {
    int cand = c == 0 ? sw : com;
    int other = c == 0 ? com : sw;
    if (linked(r, cand, third, SHORT) && linked(p, cand, third, OPEN)) {
      Serial.println("=> Plain microswitch, no LED (case A):");
      Serial.print("   "); Serial.print(NAME[cand]);  Serial.println("  = COM             -> move to UNO GND");
      Serial.print("   "); Serial.print(NAME[other]); Serial.println("  = NO              -> move to UNO D2");
      Serial.print("   "); Serial.print(NAME[third]); Serial.println("  = NC              -> leave unconnected");
      return;
    }
  }
  Serial.println("=> Found the switch pair but the third wire fits neither pattern:");
  Serial.print("   switch pair is "); Serial.print(NAME[sw]); Serial.print(" and "); Serial.println(NAME[com]);
  Serial.print("   "); Serial.print(NAME[third]); Serial.println(" never connects to anything - possibly a broken wire or an LED whose polarity is reversed.");
  Serial.println("   Try: one of the pair to GND, the other to D2, run button_test.ino; if it taps, swap the pair if the LED then lights.");
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) pinMode(PIN[i], INPUT_PULLUP);
  delay(1500);
  Serial.println();
  Serial.println("button_identify: wires on A0, A1, A2 only. Nothing on 5V or GND.");
  countdown("Step 1 - do NOT touch the button.", 3);
  measure(r);
  countdown("Step 2 - press and HOLD the button until the result prints.", 3);
  measure(p);
  Serial.println("You can let go.");
  Serial.println();
  dump("Released:", r);
  dump("Pressed:", p);
  Serial.println();
  verdict();
  Serial.println();
  Serial.println("Press the board's RESET button to run again.");
}

void loop() {}
