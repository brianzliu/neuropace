# UNO Q totem — build plan

**Written Sat 19 Sep 2026 (HackMIT). Status: planned, not built.** This is a self-contained handoff:
a new chat pointed at this file plus `AGENTS.md` should be able to execute it without the
conversation that produced it.

## What we are building

```
MindWave ──Bluetooth SPP──▶ UNO Q ──Wi-Fi (laptop hotspot)──▶ Laptop
                            runs mindwave/ pipeline           reflow serve, frontend,
                            + one physical button             Deepgram, OpenAI
```

1. **The headset pairs to the UNO Q, not the laptop.** The Q runs the team's `mindwave/` pipeline
   on-device (filtering, artifact masking, band powers, blink detection, three-anchor
   calibration) and streams one calibrated `FeatureFrame` per second to the laptop. Raw 512 Hz EEG
   never leaves the desk.
2. **A physical button on the Q replaces the `T` key.** Same meaning ("lost me"), same server
   path. `T` stays as the fallback.
3. **The apparatus is the Q + button + power bank in an enclosure. Nothing else.** No LED matrix,
   no haptic, no display. Fully wireless.
4. **The laptop-only build stays the rehearsed default.** `headset: auto` and `T` work exactly as
   today. The Q is swapped in at demo time only if every gate in §7 passed.

**Why:** Arduino "Touch Grass" track (UNO Q required; top 2 win) — the Q is the bridge from a raw
physical signal to a decision, which is the brief — plus PLAN.md Part III's privacy argument made
physically true. It does **not** improve the Education-track demo; treat it as a side quest with a
hard time box.

**Honesty rule (AGENTS.md):** the live view must say where the EEG and the tap actually came from.
A Q that isn't alive is not pretended alive.

---

## 1. Hardware

| Part | Notes |
|---|---|
| Arduino UNO Q | Qualcomm QRB2210 (4× A53 @ 2 GHz, Debian) + STM32U585 MCU (Zephyr). Wi-Fi 5 + BT 5.1. Headless over SSH. Wants **5 V / 3 A**; an under-spec supply shows up as random reboots. |
| NeuroSky MindWave Mobile 2 | Bluetooth **Classic** SPP, PIN `0000`, 57600 baud ThinkGear stream. |
| Button | Momentary switch. One leg to an MCU digital pin (D2), other to GND. `INPUT_PULLUP`. |
| Power bank | 10 000 mAh MagSafe-size, USB-C out. ≈ 30 Wh delivered vs ≈ 5 W draw → hours of runtime; **boot peaks and a 3 A-capable port** are the concern, not capacity. Prefer a USB-A→C cable if one exists (avoids PD negotiation); C-to-C is fine unless the Q won't boot — then swap the cable before suspecting software. Keep the bank outside the enclosure; these throttle when warm. |
| Laptop | Windows 11. Stays on eduroam for internet; hosts a Mobile Hotspot for the Q. |
| Phone | Backup hotspot only. |

**Enclosure:** leave the antenna edge of the board unshielded (no foil, no metal, thin wall there —
both radios go through it); vent the QRB2210; cutouts for USB-C and the button. SSH covers every
other port.

---

## 2. Network

- **Laptop:** Windows 11 *Mobile Hotspot* on (Settings → Network → Mobile hotspot), 2.4 GHz,
  WPA2-PSK. Windows always assigns itself **`192.168.137.1`**. The laptop stays associated to
  eduroam at the same time; if the adapter refuses to do both, use the phone hotspot for both
  devices instead (phone supplies internet; Deepgram streaming is a few MB/min).
- **Why not eduroam for the Q:** it's WPA2-Enterprise (802.1X) — App Lab's onboarding only takes
  SSID + password — and eduroam client isolation would block laptop↔Q traffic even if it joined.
- **Q:** onboard onto the hotspot via App Lab, then pin a static address over SSH so nothing is read
  off a screen at demo time:
  ```
  nmcli con show                       # find the hotspot connection name
  nmcli con mod "<name>" ipv4.method manual ipv4.addresses 192.168.137.50/24 \
        ipv4.gateway 192.168.137.1 ipv4.dns 192.168.137.1
  nmcli con up "<name>"
  ```
- **Laptop firewall:** the hotspot interface must be *Private*; allow inbound TCP 8765 on Private.
- **Reflow:** `uv run reflow serve --host 0.0.0.0` (the default in `reflow/config.py:40` is
  `127.0.0.1`, which the Q can't reach). Or `REFLOW_HOST=0.0.0.0` in `.env`.
- **Fallback (not wireless):** USB-C to laptop, `adb forward tcp:8765 tcp:8765`, and point the
  `remote:` headset at `ws://127.0.0.1:8765`. Then the Q also needs a different port than Reflow —
  use `--ws-port 8766` on the Q and forward that.

---

## 3. Processes on the Q — two, and they never talk to each other

| | **Pipeline** | **Button app** |
|---|---|---|
| Runs as | host Linux, `systemd` unit | App Lab app (Docker container + `arduino-router` Bridge) |
| Does | `run_pipeline.py --port /dev/rfcomm0 --ws-host 0.0.0.0` → serves the pipeline WebSocket; records `sessions/<stamp>/` locally | sketch debounces the button and calls Python over Bridge; Python POSTs a tap to the laptop |
| Laptop side | `RemoteHeadset` (new) connects *to* the Q | existing `POST /api/sessions/{id}/tap` |
| Fallback if dead | `headset: auto` on the laptop | `T` key |

Why split: `/dev/rfcomm0` is not reliably visible inside App Lab's container (forum reports on
Bluetooth from Apps), and the Bridge RPC is only documented inside Apps. Each half has its own
path to the laptop and its own fallback, so neither can take the other down.

---

## 4. Message contracts

Everything below exists today except the two rows marked **new**.

| Direction | Transport | Payload | Where |
|---|---|---|---|
| Q pipeline → laptop | `ws://192.168.137.50:8765` | `FeatureFrame.to_dict()` + `"type":"features"`, 1 Hz; `{"type":"status",…}` on connect and after calibrate; `{"type":"raw",…}` 8 Hz (ignore); `{"type":"blink",…}` | `mindwave/server.py`, `mindwave/pipeline.py:83` |
| laptop → Q pipeline | same socket | `{"type":"calibrate","phase":"eyes_closed"\|"easy"\|"hard"\|"done"\|"reset"}`, `{"type":"status"}`, `{"type":"ping"}` | `mindwave/server.py:104` |
| Q button → laptop | HTTP | `POST http://192.168.137.1:8765/api/sessions/{id}/tap?source=tap` | `reflow/api/routes.py:317` — **`source` query param is new** (today it hard-codes `"key"`) |
| Q button → laptop | HTTP | `GET /api/sessions` → pick the entry with `"running": true`, newest first; poll every 3 s until one exists | `reflow/api/routes.py:216` |
| MCU → Linux (Q) | Bridge RPC | sketch calls `on_tap(millis)`; Python registers it | **new** `firmware/totem-q/` |

`FeatureFrame` fields (all included): `t n quality valid connected log_theta log_alpha log_beta
log_gamma effort engagement effort_ema engagement_ema z_effort z_engagement z_effort_ema
z_engagement_ema alpha_ratio blink_count blink_rate blink_dur_ms artifact_coverage attention
meditation asic_bands calibrated cal_phase calibration_weak` (`mindwave/pipeline.py:52`). Floats
are rounded to 4 dp on the wire; that's fine.

---

## 5. Code changes (laptop repo)

Small and additive. Nothing in `mindwave/features.py` or `calibration.py` is touched.

### 5.1 `run_pipeline.py` — `--ws-host`
`main()` (line ~113): add `ap.add_argument("--ws-host", default="127.0.0.1")` and pass
`pipe.serve(host=args.ws_host, port=args.ws_port)`. `Pipeline.serve(host, port)` already takes it
(`mindwave/pipeline.py:214`). Update the module docstring line 3.

### 5.2 `reflow/signal/headset.py` — `RemoteHeadset`
Mirror `MindwaveHeadset`'s surface so `SessionRuntime` needs no changes:

- `kind = "remote"`, `port = <ws url>`, `state = None`, `frames` counter.
- `start()`: `asyncio.create_task` of a `websockets` client loop with reconnect (2 s backoff,
  forever). On each text message: `json.loads`; if `type == "features"`, drop the `type` key,
  build `mindwave.pipeline.FeatureFrame(**d)`, call `self.on_frame(frame)` (already on the loop —
  no `call_soon_threadsafe` needed); if `type == "status"`, cache it as `self._status`.
- `connected` property: socket open **and** a `features` message in the last 3 s **and** the
  last frame's `connected` was true.
- `calibrate(phase)`: send `{"type":"calibrate","phase":phase}`; raise `ValueError` if not
  connected (the runtime turns that into a notice).
- `status()`: same keys `MindwaveHeadset.status()` returns, read from the cached status message,
  plus `"frames"` and `"url"`.
- `stop()`: cancel the task, close the socket.
- `make_headset()` (line ~233): `if setting.startswith("remote:"): return RemoteHeadset(on_frame,
  url=setting.split(":", 1)[1])`. Update the docstring and the `SessionIn.headset` comment in
  `reflow/api/routes.py:195`.

`SessionRuntime._on_frame` (`reflow/core/session.py:253`) consumes the reconstructed frame
unchanged: `engine.feed_frame(frame.engagement, frame.quality, frame.valid, frame.blink_count, …)`.

### 5.3 Tap source
`reflow/api/routes.py:317`: `def session_tap(session_id, request, source: str = "key")`; accept
only `"key"` or `"tap"`, pass through to `rt.tap(source=source)`. `SessionRuntime.tap` already
distinguishes the two (`reflow/core/session.py:474`); `"tap"` is what the serial totem uses, so the
flag is labelled as a pad press, not a keypress.

### 5.4 Totem kind (so the UI doesn't say "keyboard totem")
`reflow/totem/bridge.py`: `class RemoteTotem(KeyboardTotem)` with `kind = "remote"`,
`port = "uno-q"`, `hint = "UNO Q button over Wi-Fi; T still works"`. `make_totem()` (line 153):
`if port_setting == "remote": return RemoteTotem(on_tap)`. Update `SessionIn.totem` comment.

### 5.5 Frontend
- `frontend/src/lib/types.ts:93`: `HeadsetKind` add `"remote"`.
- `frontend/src/components/SessionInspector.tsx:43`: treat `"remote"` like `"real"` (no warning
  badge); label it **"UNO Q"**.
- `frontend/src/components/Sidebar.tsx:137-138`: green dot for headset kind `real` **or** `remote`;
  totem dot title "UNO Q button" for kind `remote`.
- Wherever the live view exposes the session's `headset` / `totem` settings (Home view start form),
  add `remote:ws://192.168.137.50:8765` and `remote` as options, or just document typing them.

### 5.6 `.env.example`
Add commented `REFLOW_HOST=0.0.0.0`, `REFLOW_HEADSET_PORT=remote:ws://192.168.137.50:8765`,
`REFLOW_TOTEM_PORT=remote`.

### 5.7 Tests
`tests/test_mindwave_bridge.py` pattern: start a real `mindwave.Pipeline(FakeSource())` with
`serve(host="127.0.0.1", port=<free>)`, point `RemoteHeadset` at it, assert frames arrive and
`calibrate("easy")` round-trips into the status. One test for `?source=tap` on the route.

---

## 6. Code on the Q

### 6.1 Host: pipeline service
```
# once, over ssh (user `arduino`)
sudo apt install -y bluez python3-venv          # check whether `rfcomm` is present; if not, see below
python3 -m venv ~/venv && ~/venv/bin/pip install numpy scipy pyserial websockets
git clone <repo> ~/ai-tutor                      # or scp just mindwave/ + run_pipeline.py + requirements.txt
bluetoothctl                                      # power on; scan on; pair <MAC> (PIN 0000); trust <MAC>; quit
sudo rfcomm bind 0 <MAC> 1                        # -> /dev/rfcomm0
~/venv/bin/python ~/ai-tutor/run_pipeline.py --port /dev/rfcomm0 --ws-host 0.0.0.0 --no-log
```
If `rfcomm` is missing from the BlueZ build: install `bluez-tools`, or add a tiny
`mindwave.sources.BtSocketSource` that opens `socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM)`
and hands bytes to `ThinkGearReader` — pyserial is the only thing that cares about the device path.

`/etc/systemd/system/reflow-pipeline.service`:
```
[Unit]
After=bluetooth.target network-online.target
[Service]
User=arduino
ExecStartPre=-/usr/bin/rfcomm release 0
ExecStartPre=/usr/bin/rfcomm bind 0 <MAC> 1
ExecStart=/home/arduino/venv/bin/python /home/arduino/ai-tutor/run_pipeline.py --port /dev/rfcomm0 --ws-host 0.0.0.0 --log-dir /home/arduino/sessions --quiet
Restart=always
RestartSec=2
[Install]
WantedBy=multi-user.target
```
`ThinkGearReader` already reconnects every 2 s if the port drops (`mindwave/thinkgear.py:148`).

### 6.2 App Lab: button app (`firmware/totem-q/`)
Create with `arduino-app-cli app new totem-q` on the Q (or App Lab on the laptop) and check the
generated layout — expect a sketch folder and a Python `main.py`. The R4 `firmware/totem/totem.ino`
is a *protocol* reference only; its `Arduino_CapacitiveTouch` and `ArduinoLEDMatrix` libraries are
Renesas-core and do not exist here.

Sketch:
```cpp
#include <Arduino_RPClite.h>      // name per Arduino's UNO Q Bridge docs — verify in App Lab's examples
const int PIN = 2;
unsigned long lastTap = 0;
void setup() { pinMode(PIN, INPUT_PULLUP); Bridge.begin(); }
void loop() {
  static int prev = HIGH; int now = digitalRead(PIN);
  if (prev == HIGH && now == LOW && millis() - lastTap > 500) {   // 500 ms lockout, as the R4 sketch
    lastTap = millis(); Bridge.call("on_tap", (int)lastTap);
  }
  prev = now; delay(10);                                           // 10 ms poll = debounce
}
```
`main.py`:
```python
import time, requests
from arduino.app_utils import Bridge, App        # module name per UNO Q docs — verify
LAPTOP = "http://192.168.137.1:8765"
session = None
def find_session():
    r = requests.get(f"{LAPTOP}/api/sessions", timeout=2).json()
    live = [s for s in r["sessions"] if s.get("running")]
    return live[0]["id"] if live else None
def on_tap(ms):
    global session
    if session is None: session = find_session()
    if session is None: return
    try: requests.post(f"{LAPTOP}/api/sessions/{session}/tap", params={"source": "tap"}, timeout=2)
    except requests.RequestException: session = None    # re-discover next press
Bridge.provide("on_tap", on_tap)
App.run()
```
Poll `find_session()` every 3 s in the background too, so the first press after a session starts
is not lost to discovery. Check that `requests` is available in the App container (or use `urllib`).

---

## 7. Gates and order

**One owner, in parallel with the laptop demo. Hard stop at 90 min for gates 1–3.** Any failure
means the Q is at most a button, or nothing, and no enclosure gets cut.

| # | Gate | Pass | Fail → |
|---|---|---|---|
| 1 | **Bluetooth SPP** (the only real unknown) | `bluetoothctl` pairs the MindWave; `/dev/rfcomm0` exists; `run_pipeline.py --port /dev/rfcomm0 --no-log` prints frames; **blink ticks with real blinks on a real forehead** | stop; laptop-only |
| 2 | **Hotspot** | Q at `.50`; from the laptop, a `websockets` client (or `example_consumer.py`) on `ws://192.168.137.50:8765` receives `features` | phone hotspot → `adb forward` → stop |
| 3 | **Power** | 15 min on the bank with headset paired + Wi-Fi + pipeline streaming; then a cold boot on the bank | run from laptop USB (not wireless) or stop |
| 4 | §5.1–5.2 + 5.5: live view says **headset: UNO Q**, blinks on the trace, calibration buttons drive the Q | — | `headset: auto` |
| 5 | §6.1 systemd: power-cycle the Q, it comes back streaming without SSH | — | keep an SSH terminal open at the demo |
| 6 | §5.3–5.4 + §6.2: button press → flag appears in the live view labelled as a pad tap | — | `T` |
| 7 | Enclosure | after 1–6 only | — |
| 8 | Rehearse **with** the Q and **without** it | both runs clean | — |

Hour-1 gate from `README.md` still applies through the Q: if blinks don't show on the trace, the
raw stream isn't real — fix pairing before anything else.

---

## 8. Demo-time failure table

| Symptom | Likely cause | Do |
|---|---|---|
| Live view says *headset: simulated*, not *UNO Q* | Q pipeline unreachable | laptop hotspot on? `ping 192.168.137.50`; restart session with `headset: auto` and say "EEG simulated" |
| Frames arrive, `valid=false` forever | electrode contact, or stale rfcomm link | reseat headset; `sudo systemctl restart reflow-pipeline` |
| Q reboots mid-session | power | swap cable/bank; power from laptop |
| Button does nothing | App Lab app / Bridge | press `T`; say so |
| Tap lands on a stale session | `main.py` cached an old id | restart the app; it re-polls |
| Calibration buttons do nothing | WS to Q dropped | `RemoteHeadset` reconnects in 2 s; retry |

---

## 9. Open questions to resolve on the device (not from docs)

- Does the Q's Debian image ship `rfcomm`? (Newer BlueZ packages drop it; §6.1 has the fallback.)
- Exact module names for Bridge in the sketch (`Arduino_RPClite`?) and in Python
  (`arduino.app_utils`?), and the App Lab folder layout — read the generated example first.
- Can the App container reach `192.168.137.1`? (Outbound network from Apps is normal; confirm.)
- Does the laptop's Wi-Fi adapter run a hotspot while associated to eduroam on 5 GHz?
