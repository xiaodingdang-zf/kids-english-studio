"""cue.action 对应拟音，全部由本项目代码合成，无外部音效素材。"""
from __future__ import annotations

import numpy as np

from . import synth

SR = 48000
ACTION_SOUNDS = {
    "wave": "swish", "jump": "jump_land", "clap": "clap",
    "point": "appear", "nod": "tap", "listen": "chime",
}


def _noise(duration: float, seed: int, decay: float) -> np.ndarray:
    t = np.arange(int(duration * SR)) / SR
    x = np.random.default_rng(seed).standard_normal(len(t))
    x = np.convolve(x, np.ones(12) / 12, mode="same")
    return (x * np.exp(-t * decay)).astype(np.float32)


def sound(kind: str) -> np.ndarray:
    if kind in ("pop", "appear"):
        return synth.pop() * (0.7 if kind == "appear" else 1)
    if kind == "chime":
        return synth.chime()
    if kind == "swish":
        return _noise(0.22, 11, 13) * 0.23
    if kind == "clap":
        return _noise(0.18, 12, 24) * 0.65
    if kind == "tap":
        return _noise(0.10, 13, 38) * 0.25
    if kind == "jump_land":
        up = synth.pop() * 0.35
        out = np.zeros(int(0.43 * SR), np.float32)
        out[:len(up)] += up
        land = _noise(0.16, 14, 19) * 0.5
        at = int(0.27 * SR)
        out[at:at + len(land)] += land
        return out
    raise ValueError(f"未知拟音事件：{kind}")
