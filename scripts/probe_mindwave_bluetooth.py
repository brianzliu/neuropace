"""Measure checksum-validated MindWave RFCOMM traffic without changing the headset.

Linux only. Uses the existing ThinkGear parser without importing scientific dependencies.
"""

import argparse
import collections
import json
from pathlib import Path
import runpy
import socket
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("address")
    ap.add_argument("--channel", type=int, default=1)
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--parser", default=str(Path(__file__).resolve().parents[1] / "mindwave/thinkgear.py"))
    args = ap.parse_args()
    parser_module = runpy.run_path(args.parser)
    parser = parser_module["PacketParser"]()
    parse_payload = parser_module["parse_payload"]
    bins = collections.defaultdict(collections.Counter)
    counts = collections.Counter()
    quality = collections.Counter()
    first_raw = last_raw = None
    last_rx = None
    max_gap = 0.0
    with socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM) as sock:
        sock.settimeout(15)
        before = time.monotonic()
        sock.connect((args.address, args.channel))
        start = time.monotonic()
        print(json.dumps({"connected": True, "connect_seconds": start - before}), flush=True)
        sock.settimeout(0.2)
        while time.monotonic() - start < args.seconds:
            try:
                data = sock.recv(16384)
            except socket.timeout:
                continue
            now = time.monotonic() - start
            if not data:
                print(json.dumps({"peer_closed_at": now}), flush=True)
                break
            if last_rx is not None:
                max_gap = max(max_gap, now - last_rx)
            last_rx = now
            bucket = bins[int(now)]
            bucket["bytes"] += len(data)
            counts["bytes"] += len(data)
            for payload in parser.feed(data):
                counts["valid_packets"] += 1
                fields = parse_payload(payload)
                raw = fields.get(0x80)
                if isinstance(raw, bytes) and len(raw) == 2:
                    bucket["raw_samples"] += 1
                    counts["raw_samples"] += 1
                    if first_raw is None:
                        first_raw = now
                    last_raw = now
                if 0x02 in fields:
                    quality[str(fields[0x02])] += 1
                for code in fields:
                    counts[f"code_{code:02x}"] += 1
        elapsed = time.monotonic() - start
    for second in range(int(elapsed)):
        print(json.dumps({"second": second, **bins[second]}), flush=True)
    print(json.dumps({"summary": dict(counts), "quality": dict(quality),
                      "elapsed": elapsed, "first_raw_at": first_raw, "last_raw_at": last_raw,
                      "max_rx_gap": max_gap}), flush=True)


if __name__ == "__main__":
    main()
