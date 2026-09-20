"""Fallback for macOS Bluetooth serial devices that open but never deliver bytes.

The small native helper opens the paired device's RFCOMM channel with IOBluetooth;
stdout carries untouched ThinkGear packets to the existing reader/parser. Requires
Apple's Command Line Tools once to compile, then reuses a source-hashed binary.
"""
from __future__ import annotations

import hashlib
import os
import select
import subprocess
import tempfile
from pathlib import Path


def helper_binary() -> Path:
    source = Path(__file__).with_name('macos_rfcomm.swift')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    cache = Path.home() / 'Library' / 'Caches' / 'NeuroPace'
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = cache / f'rfcomm-{digest}'
    if target.exists():
        return target
    fd, temp = tempfile.mkstemp(prefix='rfcomm-', dir=cache)
    os.close(fd)
    try:
        try:
            result = subprocess.run(
                ['/usr/bin/xcrun', 'swiftc', str(source), '-o', temp],
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            raise OSError('Native Bluetooth helper compilation timed out') from exc
        if result.returncode:
            raise OSError('Native Bluetooth helper needs Apple Command Line Tools: ' + result.stderr[-500:])
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)
    return target


class MacRFCOMMTransport:
    def __init__(self, port: str, baud: int = 57600, timeout: float = 1):
        self.timeout = timeout
        self.process = subprocess.Popen(
            [str(helper_binary()), port], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    @property
    def in_waiting(self) -> int:
        return 4096

    def read(self, n: int) -> bytes:
        assert self.process.stdout is not None
        if not select.select([self.process.stdout], [], [], self.timeout)[0]:
            return b''
        data = os.read(self.process.stdout.fileno(), n)
        if not data:
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired as exc:
                raise OSError('Native Bluetooth stream closed without exiting') from exc
            error = self.process.stderr.read().decode(errors='replace') if self.process.stderr else ''
            raise OSError(error.strip() or 'Native Bluetooth stream closed')
        return data

    def cancel_read(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cancel_read()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        for pipe in (self.process.stdout, self.process.stderr):
            if pipe:
                pipe.close()
