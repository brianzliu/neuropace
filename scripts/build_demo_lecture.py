"""Builds the demo lecture (spec §6 shape: 5 segments, segment 3 deliberately bad) into data/lectures/demo/script.json.

Segment 3 is jargon-heavy with no example on purpose; it is the planted flaw the loss map should find.
Quiz: 15 items, 3 per segment, each anchored to a phrase so its lecture-time span is computed from the script timing.
Run: uv run python scripts/build_demo_lecture.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from reflow.transcribe.scripted import script_from_text

TITLE = "How GPS finds you"
WPM = 150.0
KEYTERMS = [
    "trilateration",
    "pseudorange",
    "ionospheric delay",
    "Kalman filter",
    "dilution of precision",
    "clock bias",
    "time dilation",
]

SEGMENTS = [
    (
        "Satellites that broadcast the time",
        """Let's start with what a GPS satellite actually does, because it is simpler than people think. Every GPS satellite
does one thing all day long. It broadcasts the current time, over and over, along with where it is in its orbit.
That's it. It does not know where you are. It does not track you. It is a very precise clock in space, shouting the time.
There are about thirty of these satellites, arranged so that from any point on Earth you can usually see at least six of them
above the horizon. Each one carries an atomic clock, accurate to a few billionths of a second. Your phone has a cheap
quartz clock, and that difference is going to matter later. So remember the picture: thirty flying clocks, each announcing
the time and its own position, and your phone just listening.""",
    ),
    (
        "Turning a delay into a distance",
        """Now, how does listening to a clock tell you where you are? Radio travels at the speed of light, about three hundred
thousand kilometers per second. When your phone receives a satellite's message, it compares the time stamped inside the
message with the time it was received. The difference is how long the signal was in flight. Multiply that delay by the
speed of light and you get the distance to that satellite. Here's a concrete example. If the signal took seventy
milliseconds to arrive, that is seventy thousandths of a second times three hundred thousand kilometers per second, which
is twenty one thousand kilometers. So the phone now knows: I am twenty one thousand kilometers from that satellite.
One distance puts you somewhere on a sphere around that satellite. Two distances narrow you to a circle where two spheres
meet. Three distances narrow you to two points, and one of them is out in space, so it is thrown away. This method is
called trilateration, and it is the heart of GPS.""",
    ),
    (
        "Error sources (deliberately dense)",
        """The pseudorange observable is corrupted by several additive error terms which must be modeled or differenced out.
The ionospheric delay is dispersive and proportional to total electron content divided by frequency squared, so a
dual-frequency receiver can form an ionosphere-free linear combination, whereas a single-frequency receiver relies on the
Klobuchar model broadcast in the navigation message. Tropospheric delay is non-dispersive and is decomposed into hydrostatic
and wet zenith components mapped through an elevation-dependent mapping function. Multipath introduces a
geometry-dependent bias that is not zero-mean over short intervals. Receiver clock bias is treated as a fourth unknown in
the state vector, and the geometry matrix conditions the covariance through the dilution of precision. A Kalman filter
propagates the state estimate with a process noise model and updates it with the innovation weighted by the Kalman gain,
which is derived from the a priori covariance and the measurement noise covariance. Ephemeris errors and satellite clock
errors are bounded by the user range accuracy index. Together these terms define the error budget.""",
    ),
    (
        "Why you need a fourth satellite",
        """Let's go back to the phone's cheap clock, because it breaks the neat picture from before. Trilateration assumed the
phone knows exactly when the signal arrived. But a quartz clock that is off by one millionth of a second turns into three
hundred meters of distance error, because light travels three hundred meters in a microsecond. So every distance the
phone computes is wrong by the same unknown amount, the phone's clock error. Here's the trick. The phone treats its own
clock error as a fourth unknown, next to latitude, longitude and altitude. Four unknowns need four equations, so the phone
uses a fourth satellite. With four satellites it solves for all four numbers at once. A nice side effect is that your phone
ends up knowing the time as precisely as an atomic clock, for free. That is why the clocks on phones all over the world
agree to within a few nanoseconds: they are all borrowing time from the satellites.""",
    ),
    (
        "Relativity and everyday use",
        """One last thing, and it is my favorite part. The satellite clocks are moving fast and they are far from Earth's
gravity, so relativity changes how fast they tick. Moving fast makes them tick slower by about seven microseconds a day.
Being higher in the gravity well makes them tick faster by about forty five microseconds a day. The net effect is that the
satellite clocks run fast by about thirty eight microseconds a day. That sounds tiny, but remember one microsecond is
three hundred meters. Without the correction, GPS positions would drift by more than ten kilometers every day. So the
satellite clocks are deliberately set to tick slightly slow before launch, so that in orbit they tick at the right rate.
Every time you get directions on your phone, you are using Einstein's equations. Next week we will look at how a phone
combines GPS with WiFi and cell towers to fix a position indoors, where it cannot see the sky at all.""",
    ),
]

# (segment index, anchor phrase, question, options, correct index)
QUIZ = [
    (
        0,
        "broadcasts the current time",
        "What does a GPS satellite broadcast?",
        ["The time and its own position", "Your phone's position", "A map of the area", "Weather data"],
        0,
    ),
    (
        0,
        "atomic clock",
        "What kind of clock does a GPS satellite carry?",
        ["An atomic clock", "A quartz clock", "A pendulum clock", "No clock; it uses the phone's"],
        0,
    ),
    (
        0,
        "at least six",
        "From any point on Earth, about how many GPS satellites are usually visible?",
        ["At least six", "Exactly one", "About thirty", "None during the day"],
        0,
    ),
    (
        1,
        "Multiply that delay",
        "How does the phone turn a signal delay into a distance?",
        [
            "Multiplies the delay by the speed of light",
            "Divides the delay by the satellite's altitude",
            "Looks the delay up in a table",
            "Adds the delays from all satellites",
        ],
        0,
    ),
    (
        1,
        "twenty one thousand kilometers",
        "In the example, a seventy millisecond delay corresponds to what distance?",
        [
            "Twenty one thousand kilometers",
            "Seventy kilometers",
            "Three hundred kilometers",
            "Two hundred ten kilometers",
        ],
        0,
    ),
    (
        1,
        "called trilateration",
        "Three distances narrow your position to two points. What happens to one of them?",
        [
            "It is thrown away because it is out in space",
            "It is averaged with the other",
            "It is stored for later",
            "It becomes the altitude",
        ],
        0,
    ),
    (
        2,
        "ionospheric delay is dispersive",
        "According to the lecture, the ionospheric delay is proportional to what?",
        [
            "Total electron content divided by frequency squared",
            "The satellite's altitude",
            "The receiver's speed",
            "The number of satellites",
        ],
        0,
    ),
    (
        2,
        "Klobuchar model",
        "What does a single-frequency receiver rely on to correct the ionosphere?",
        [
            "The Klobuchar model broadcast in the navigation message",
            "An ionosphere-free linear combination",
            "A second antenna",
            "The Kalman gain",
        ],
        0,
    ),
    (
        2,
        "Kalman gain",
        "In the filter described, the Kalman gain is derived from which two quantities?",
        [
            "The a priori covariance and the measurement noise covariance",
            "The satellite position and the time",
            "The pseudorange and the multipath",
            "The tropospheric and ionospheric delays",
        ],
        0,
    ),
    (
        3,
        "three hundred meters of distance error",
        "A clock error of one microsecond causes roughly how much distance error?",
        ["Three hundred meters", "Three meters", "Thirty kilometers", "One kilometer"],
        0,
    ),
    (
        3,
        "fourth unknown",
        "Why does the phone need a fourth satellite?",
        [
            "To solve for its own clock error as a fourth unknown",
            "To measure altitude directly",
            "Because three satellites are often behind clouds",
            "To double-check the first three",
        ],
        0,
    ),
    (
        3,
        "borrowing time from the satellites",
        "What side effect of the GPS solution did the lecturer mention?",
        [
            "The phone learns the time as precisely as an atomic clock",
            "The phone's battery lasts longer",
            "The phone can see through buildings",
            "The phone stops needing WiFi",
        ],
        0,
    ),
    (
        4,
        "thirty eight microseconds",
        "By about how much per day do satellite clocks run fast, net of both relativistic effects?",
        ["Thirty eight microseconds", "Seven microseconds", "Forty five milliseconds", "Ten seconds"],
        0,
    ),
    (
        4,
        "more than ten kilometers",
        "Without the relativity correction, how far would positions drift each day?",
        ["More than ten kilometers", "About three hundred meters", "About one meter", "They would not drift"],
        0,
    ),
    (
        4,
        "tick slightly slow before launch",
        "How is the relativistic effect handled in practice?",
        [
            "Satellite clocks are set to tick slightly slow before launch",
            "The phone ignores it",
            "The satellites are launched lower",
            "Signals are sent twice",
        ],
        0,
    ),
]


def main() -> None:
    words = []
    segments = []
    t = 0.0
    seg_texts = []
    for i, (title, text) in enumerate(SEGMENTS):
        clean = " ".join(text.split())
        seg_texts.append(clean)
        ws = script_from_text(clean, WPM, start=t)
        segments.append(
            {
                "id": f"seg{i + 1}",
                "title": title,
                "t_start": round(t, 3),
                "t_end": round(ws[-1].end + 1.0, 3),
                "planted_bad": i == 2,
            }
        )
        words.extend(w.to_dict() for w in ws)
        t = ws[-1].end + 1.0  # a one-second breath between segments
    quiz = []
    for n, (seg_i, anchor, q, opts, ci) in enumerate(QUIZ):
        seg_ws = [w for w in words if segments[seg_i]["t_start"] <= w["start"] < segments[seg_i]["t_end"]]
        toks = anchor.split()
        hit = None
        for j in range(len(seg_ws) - len(toks) + 1):
            if all(
                re.sub(r"[^a-z]", "", seg_ws[j + k]["w"].lower()) == re.sub(r"[^a-z]", "", toks[k].lower())
                for k in range(len(toks))
            ):
                hit = (seg_ws[j]["start"], seg_ws[j + len(toks) - 1]["end"])
                break
        assert hit is not None, f"anchor not found: {anchor}"
        quiz.append(
            {
                "id": f"q{n + 1:02d}",
                "segment": segments[seg_i]["id"],
                "question": q,
                "options": opts,
                "correct_index": ci,
                "t_start": round(max(0.0, hit[0] - 12.0), 3),
                "t_end": round(hit[1] + 6.0, 3),
                "anchor": anchor,
            }
        )
    out = {
        "id": "lec_demo0001",
        "title": TITLE,
        "wpm": WPM,
        "keyterms": KEYTERMS,
        "segments": segments,
        "quiz": quiz,
        "words": words,
        "duration": round(words[-1]["end"], 3),
        "text": "\n\n".join(seg_texts),
    }
    dest = Path(__file__).resolve().parents[1] / "data" / "lectures" / "demo" / "script.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {dest}: {len(words)} words, {out['duration']:.0f} s, {len(quiz)} quiz items")
    for s in segments:
        print(
            f"  {s['id']:5s} {s['t_start']:6.1f}-{s['t_end']:6.1f}  {s['title']}{'  (planted bad)' if s['planted_bad'] else ''}"
        )


if __name__ == "__main__":
    main()
