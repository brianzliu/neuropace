"""Blink counter on the raw stream (TDD §3.2). Blinks at Fp1 are large slow deflections."""

from __future__ import annotations

from collections import deque

import numpy as np


class BlinkDetector:
    def __init__(
        self,
        fs: int = 512,
        block_ms: int = 250,
        refractory_ms: int = 300,
        abs_p2p: float = 300.0,
        median_mult: float = 3.0,
        history_blocks: int = 40,
    ) -> None:
        self.fs = fs
        self.block = max(8, int(fs * block_ms / 1000))
        self.refractory_blocks = max(1, int(np.ceil(refractory_ms / block_ms)))
        self.abs_p2p = abs_p2p
        self.median_mult = median_mult
        self._pending = np.zeros(0, dtype=np.float64)
        self._p2p_hist: deque[float] = deque(maxlen=history_blocks)
        self._since_last = self.refractory_blocks
        self.count = 0
        # intervals (sample index in the global stream) of detected blinks, for artifact blanking
        self._sample_pos = 0
        self.recent_blink_positions: deque[int] = deque(maxlen=64)

    def feed(self, samples: np.ndarray) -> int:
        """Returns the number of blinks detected in this chunk."""
        x = np.asarray(samples, dtype=np.float64)
        if x.size == 0:
            return 0
        buf = np.concatenate([self._pending, x]) if self._pending.size else x
        nblocks = buf.size // self.block
        found = 0
        for b in range(nblocks):
            seg = buf[b * self.block : (b + 1) * self.block]
            p2p = float(seg.max() - seg.min())
            med = float(np.median(self._p2p_hist)) if len(self._p2p_hist) >= 4 else 0.0
            thresh = max(self.abs_p2p, self.median_mult * med) if med > 0 else self.abs_p2p
            self._since_last += 1
            if p2p > thresh and self._since_last > self.refractory_blocks:
                self.count += 1
                found += 1
                self._since_last = 0
                self.recent_blink_positions.append(
                    self._sample_pos + b * self.block + int(np.argmax(np.abs(seg - np.median(seg))))
                )
            else:
                self._p2p_hist.append(p2p)
        consumed = nblocks * self.block
        self._pending = buf[consumed:].copy()
        self._sample_pos += consumed
        return found
