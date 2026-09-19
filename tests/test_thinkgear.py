import numpy as np

from reflow.signal.simulate import SimulatedEEG
from reflow.signal.thinkgear import CODE_RAW, ThinkGearParser, encode_packet, encode_raw, encode_status


def test_raw_roundtrip_and_sign():
    p = ThinkGearParser()
    data = encode_raw(-1234) + encode_raw(2047) + encode_raw(0)
    ev = p.feed(data)
    assert [e.kind for e in ev] == ["raw"] * 3
    assert [e.value for e in ev] == [-1234, 2047, 0]
    assert p.packets == 3 and p.bad_checksums == 0


def test_status_packet_decoding():
    p = ThinkGearParser()
    powers = {
        "delta": 1,
        "theta": 70000,
        "low_alpha": 3,
        "high_alpha": 4,
        "low_beta": 5,
        "high_beta": 6,
        "low_gamma": 7,
        "mid_gamma": 16777215,
    }
    ev = p.feed(encode_status(26, attention=55, meditation=40, eeg_power=powers))
    kinds = {e.kind: e.value for e in ev}
    assert kinds["poor_signal"] == 26 and kinds["attention"] == 55 and kinds["meditation"] == 40
    assert kinds["eeg_power"] == powers


def test_split_chunks_and_resync_after_garbage():
    p = ThinkGearParser()
    stream = b"\x01\x02\xaa" + encode_raw(5) + b"\xff\xaa\xaa\xff" + encode_raw(6) + encode_raw(7)
    out = []
    for i in range(0, len(stream), 3):  # arbitrary chunking
        out += p.feed(stream[i : i + 3])
    assert [e.value for e in out if e.kind == "raw"] == [5, 6, 7]
    assert p.resyncs >= 1


def test_bad_checksum_is_dropped():
    p = ThinkGearParser()
    pkt = bytearray(encode_raw(9))
    pkt[-1] ^= 0xFF
    assert p.feed(bytes(pkt)) == []
    assert p.bad_checksums == 1
    assert [e.value for e in p.feed(encode_raw(10))] == [10]


def test_excode_rows_are_ignored_but_packet_survives():
    payload = [(CODE_RAW, (42).to_bytes(2, "big", signed=True))]
    pkt = encode_packet(payload)
    # hand-build a packet with an EXCODE-prefixed row followed by a normal raw row
    body = b"\x55\x02\x00" + b"\x80\x02" + (42).to_bytes(2, "big", signed=True)
    chk = (~sum(body)) & 0xFF
    raw = b"\xaa\xaa" + bytes([len(body)]) + body + bytes([chk])
    ev = ThinkGearParser().feed(raw + pkt)
    assert [e.value for e in ev] == [42, 42]


def test_simulator_emits_parseable_stream_with_status():
    sim = SimulatedEEG(seed=3)
    p = ThinkGearParser()
    ev = p.feed(sim.next_bytes(512, with_status=True))
    raws = [e.value for e in ev if e.kind == "raw"]
    assert len(raws) == 512
    assert all(-2048 <= v <= 2047 for v in raws)
    assert any(e.kind == "poor_signal" and e.value == 0 for e in ev)
    sim.set_state("poor")
    ev2 = p.feed(sim.next_bytes(512, with_status=True))
    assert any(e.kind == "poor_signal" and e.value == 200 for e in ev2)
    assert np.std([e.value for e in ev2 if e.kind == "raw"]) > np.std(raws) * 5
