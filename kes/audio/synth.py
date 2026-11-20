"""程序化原创配乐与音效（代码现场生成 → 版权归项目所有，可商用）。"""
from __future__ import annotations

import numpy as np

SR = 48000

# C 大调 I–V–vi–IV：C G Am F
CHORDS = [
    [60, 64, 67],
    [55, 59, 62],
    [57, 60, 64],
    [53, 57, 60],
]


def midi_hz(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def pluck(freq: float, dur: float, sr: int = SR) -> np.ndarray:
    t = np.arange(int(dur * sr)) / sr
    env = np.exp(-t * 5.5) * np.minimum(1, t * 400)
    tone = (np.sin(2 * np.pi * freq * t)
            + 0.45 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t * 3)
            + 0.18 * np.sin(2 * np.pi * 3 * freq * t) * np.exp(-t * 6))
    return (tone * env).astype(np.float32)


def bgm(total_s: float, bpm: int = 96, sr: int = SR) -> np.ndarray:
    """轻快的拨弦琶音 + 低音，循环到 total_s。"""
    n = int(total_s * sr) + sr
    out = np.zeros(n, dtype=np.float32)
    beat = 60.0 / bpm
    step = beat / 2  # 八分音符
    pattern = [0, 1, 2, 1, 0, 1, 2, 1]
    t = 0.0
    bar = 0
    while t < total_s:
        chord = CHORDS[bar % len(CHORDS)]
        for k, idx in enumerate(pattern):
            start = int((t + k * step) * sr)
            if start >= n:
                break
            note = pluck(midi_hz(chord[idx] + 12), 0.9) * 0.22
            end = min(n, start + len(note))
            out[start:end] += note[: end - start]
        bass = pluck(midi_hz(chord[0] - 12), beat * 4) * 0.30
        s = int(t * sr)
        e = min(n, s + len(bass))
        out[s:e] += bass[: e - s]
        t += beat * 4
        bar += 1
    return out[: int(total_s * sr)]


def pop(sr: int = SR) -> np.ndarray:
    """卡片弹出的“啵”。"""
    t = np.arange(int(0.12 * sr)) / sr
    f = 900 * np.exp(-t * 18) + 300
    phase = 2 * np.pi * np.cumsum(f) / sr
    return (np.sin(phase) * np.exp(-t * 30) * 0.6).astype(np.float32)


def chime(sr: int = SR) -> np.ndarray:
    """跟读提示音：两声上行。"""
    a = pluck(midi_hz(84), 0.35) * 0.35
    b = pluck(midi_hz(88), 0.5) * 0.35
    out = np.zeros(int(0.12 * sr) + len(b), dtype=np.float32)
    out[: len(a)] += a
    out[int(0.12 * sr):] += b
    return out
