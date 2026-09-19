# UNO Q 4 GB relay prototype

This targets the user's UNO Q 4 GB, not the older UNO R4 direct-USB sketch (that path remains a
fallback). The physical button is not built yet — momentary switch under a larger 3D-printed press
surface (planned). Neither this sketch nor Bluetooth relay has been compiled or tested on that
board yet. Software packet parsing has offline tests. Do not describe a detected relay as a tested
button.

## Hardware blockers (all open)

Nothing below has been done. No relay success claim is valid until every box is checked on the
physical board.

- [ ] **Compile:** `sketch/sketch.ino` builds for the Q MCU, and `python/main.py` imports cleanly
      in the App Lab Python environment.
- [ ] **Flash:** the sketch is flashed and `reflow_button_count` increments exactly once per press
      (debounce holds, a held press does not repeat).
- [ ] **Wiring D2/GND:** normally-open momentary switch between D2 and GND, internal pull-up, pin
      labels verified against the Q pinout; never connected to a voltage rail.
- [ ] **Pair:** MindWave Mobile 2 paired to Q Linux BlueZ, SPP endpoint created, correct
      `REFLOW_HEADSET_PORT` set inside App Lab.
- [ ] **BLE permission:** the App Lab Python environment can advertise a GATT peripheral
      (BlueZ/DBus access confirmed).
- [ ] **App Lab compat:** `bless`, `arduino.app_utils`, `mindwave.Pipeline` and this repository all
      run in App Lab on the installed board image.
- [ ] **Encrypted access:** an authenticated, encrypted pairing policy exists and is verified. The
      prototype GATT service has none; do not transmit real participant data without this.
- [ ] **Throughput:** measured BLE notification throughput and dropped-frame rate at the 20-byte
      chunk cadence; the 3 s EEG staleness bound behaves correctly under load.
- [ ] **End-to-end tap:** physical press reaches the laptop as a `tap` event and saves a flag.
- [ ] **End-to-end frame:** live EEG reaches the laptop as one validated `frame` per second, with
      no simulated substitution when hardware drops.

## Connection layout

MindWave Mobile 2 -> Q Linux Bluetooth serial -> existing `mindwave.Pipeline` -> BLE -> laptop.
Momentary switch -> Q MCU -> RouterBridge press count -> same Linux BLE relay -> laptop.
Camera and microphone -> browser in the laptop's session window.

The Q runs the existing EEG feature pipeline unchanged and sends its once-per-second frames.
The laptop still applies Reflow's session baseline and timing rules. There is no eSense-based
decision, and the pipeline's real-headset performance claims have not been revalidated on the Q.

## Bring-up

1. Install/update Arduino App Lab and the UNO Q board software. Copy `sketch/sketch.ino` and
   `python/main.py` into an App Lab application. Make this repository importable in its Python
   environment and install `bless`. The MCU uses `Arduino_RouterBridge`.
2. With board power removed, connect a normally-open momentary switch between D2 and GND.
   Verify the pin labels against the Q pinout. The sketch uses the internal pull-up; do not
   connect the switch to a voltage rail. A printed plate can actuate that switch, with a travel
   stop and return spring. Check one press increments once and a held press does not repeat.
3. Pair the MindWave to the Q's Linux Bluetooth stack following NeuroSky's computer pairing
   instructions. Configure an SPP serial endpoint and set `REFLOW_HEADSET_PORT` to that actual
   path inside the App Lab environment. `/dev/rfcomm0` is an example, not an autodetected fact.
   Serial profile availability, BlueZ permissions, and App Lab device/DBus access require board
   verification. Do not pair the same headset to the laptop concurrently.
4. Run the App Lab application. It advertises the Reflow service as `Reflow UNO Q`. Confirm
   Bluetooth peripheral support and notification reliability on the installed board image.
5. On the laptop run `uv sync --extra bluetooth` and `uv run --extra bluetooth reflow serve`.
   In Session studio choose **Find UNO Q over Bluetooth**, then select the discovered relay.
   This uses the backend's native Bluetooth stack, including in browsers without Web Bluetooth.
6. Verify physical button presses, disconnect/reconnect, feature cadence, bad contact, and
   stale data before using it in a study. Missing relay/headset data is never replaced by
   simulated input in relay mode. A direct computer connection remains an explicit fallback.

Use with consenting adult demo participants only. This prototype GATT service does not implement
application authentication or a verified encrypted pairing policy. Configure and verify paired,
restricted access before transmitting real participant data. It is not deployment-ready.

## Protocol

Service `7d840001-8e6d-4fa5-99c7-7cf726e83b01`; event and command characteristics end in `0002`
and `0003` respectively. Events are newline-delimited UTF-8 JSON, fragmented into 20-byte BLE
notifications, with increasing `seq` values. Types are `frame`, `tap`, and `status`.
The receiver rejects duplicate sequences, malformed frames, nonfinite metrics, and oversized
messages. EEG connection goes stale after three seconds. Calibration commands are written to
the command characteristic. Dropped frames need throughput measurements on real hardware.

## Primary references

- [UNO Q user manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/)
- [MindWave Mobile 2 computer pairing](https://support.neurosky.com/kb/mindwave-mobile-2/cant-pair-mindwave-mobile-2-with-computer-or-mobile-device)
- [Bleak client](https://bleak.readthedocs.io/en/latest/api/client.html)
- [Bless server example](https://github.com/kevincar/bless/blob/master/examples/server.py)
