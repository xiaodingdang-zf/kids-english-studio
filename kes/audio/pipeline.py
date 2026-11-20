"""音频引擎：episode.json → master.wav + audio_timeline.json（唯一实测时长源）。"""
from __future__ import annotations

import re
import wave
from pathlib import Path

import numpy as np

from ..core.common import dump_json, load_json, run, validate
from . import foley, music
from .tts_adapter import synthesize_live, synthesize_mock

SR = 48000
HEAD_MS, TAIL_MS, GAP_MS = 500, 900, 250
TARGET_LUFS, TARGET_TP = -16.0, -1.5
VOICES = Path(__file__).with_name("voices.json")


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SR or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError(f"需要 48kHz/单声道/16bit：{path}")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def write_wav(path: Path, x: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def ms(n_samples: int) -> int:
    return int(round(n_samples * 1000 / SR))


def measure_loudness(path: Path) -> tuple[float | None, float | None]:
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
               "-f", "null", "-"]).stderr
    summary = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return (float(i.group(1)) if i else None, float(p.group(1)) if p else None)


def _trim(x: np.ndarray, thresh: float = 0.01, pad_ms: int = 40) -> np.ndarray:
    """去掉句首句尾静音（保留 40ms）。"""
    idx = np.flatnonzero(np.abs(x) > thresh)
    if idx.size == 0:
        return x
    pad = int(pad_ms * SR / 1000)
    return x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]


def _duck_envelope(voice: np.ndarray, floor: float = 0.35) -> np.ndarray:
    """人声出现时把 BGM 压到 floor 倍（简易 sidechain）。"""
    def moving_average(x: np.ndarray, width: int) -> np.ndarray:
        cumulative = np.pad(np.cumsum(x, dtype=np.float64), (1, 0))
        half = width // 2
        left = np.maximum(0, np.arange(len(x)) - half)
        right = np.minimum(len(x), np.arange(len(x)) + width - half)
        return (cumulative[right] - cumulative[left]) / np.maximum(1, right - left)

    energy = moving_average(np.abs(voice), int(0.05 * SR))
    active = (energy > 0.01).astype(np.float32)
    active = moving_average(active, int(0.25 * SR))
    return 1.0 - (1.0 - floor) * np.clip(active * 1.5, 0, 1)


def synthesize_audio(episode_path: Path, out_dir: Path, mode: str = "mock", allow_paid: bool = False,
                     bgm: bool = True, en_voice: str | None = None) -> Path:
    episode = load_json(episode_path)
    validate(episode, "episode")
    voices = load_json(VOICES)
    en_voice = en_voice or episode.get("options", {}).get("en_voice", "a")
    seg_dir = out_dir / "audio" / f"segments_{mode}"
    cues = episode["cues"]
    if mode == "mock":
        segs = synthesize_mock(cues, voices, seg_dir)
    elif mode == "live":
        segs = synthesize_live(cues, voices, out_dir / "audio", allow_paid, en_voice)
    else:
        raise ValueError(f"未知模式：{mode}")

    parts: list[np.ndarray] = [np.zeros(int(HEAD_MS * SR / 1000), np.float32)]
    cursor = len(parts[0])
    timeline, sfx_events = [], []
    prev_card_word = None
    for c in cues:
        wav_path, voice_id = segs[c["cue_id"]]
        audio = _trim(read_wav(Path(wav_path)))
        active = np.flatnonzero(np.abs(audio) > 0.01)
        audio_ms = ms(int(active[-1] - active[0] + 1)) if active.size else 0
        if audio_ms < 150:
            raise ValueError(f"⚠️  静音保护：{c['cue_id']}（{c['text'][:20]}）的有效时长仅 {audio_ms}ms，小于 150ms 下限。这可能是沙盒配音失败或无声。请检查该句话的配音。")
        start = cursor
        if c["show_card"] and c["word_index"] != prev_card_word:
            sfx_events.append(("pop", start))
        action_kind = foley.ACTION_SOUNDS.get(c["action"])
        if action_kind:
            sfx_events.append((action_kind, start))
        prev_card_word = c["word_index"] if c["show_card"] else None
        parts.append(audio)
        cursor += len(audio)
        end = cursor
        if c["repeat_prompt"]:
            sfx_events.append(("chime", end + int(0.08 * SR)))
        gap = int((GAP_MS + c["pause_after_ms"]) * SR / 1000)
        parts.append(np.zeros(gap, np.float32))
        cursor += gap
        timeline.append({
            "cue_id": c["cue_id"], "lang": c["lang"], "voice_id": voice_id,
            "start_ms": ms(start), "end_ms": ms(end), "pause_after_ms": c["pause_after_ms"],
            "asset_source": voice_id.split(":")[0] + ":" + voice_id.split(":")[1],
        })
    parts.append(np.zeros(int(TAIL_MS * SR / 1000), np.float32))
    voice = np.concatenate(parts)
    total = len(voice)

    mix = voice.copy()
    sfx_list = []
    for kind, pos in sfx_events:
        s = foley.sound(kind)
        e = min(total, pos + len(s))
        mix[pos:e] += s[: e - pos] * 0.5
        sfx_list.append({"kind": kind, "at_ms": ms(pos), "asset_source": "kes:foley"})
    bgm_info = None
    if bgm:
        bed, bgm_info = music.render(total / SR, episode.get("style", "clay"))
        bed = bed[:total] * _duck_envelope(voice) * 0.5
        fade = min(len(bed), int(1.5 * SR))
        bed[-fade:] *= np.linspace(1, 0, fade)
        mix[: len(bed)] += bed

    adir = out_dir / "audio"
    voice_path = write_wav(adir / f"voice_{mode}.wav", voice * 0.9)
    raw = write_wav(adir / f"premaster_{mode}.wav", mix * 0.6)
    master = adir / f"master_{mode}.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
         f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP - 0.5}:LRA=11,aresample={SR}",
         "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(master)])
    lufs, peak = measure_loudness(master)

    tl = {
        "schema_version": "1.0",
        "episode_id": episode["episode_id"],
        "mode": mode,
        "sample_rate": SR,
        "total_duration_ms": ms(total),
        "master": str(master.relative_to(out_dir)),
        "voice_only": str(voice_path.relative_to(out_dir)),
        "lufs": lufs,
        "peak_db": peak,
        "bgm": bgm_info,
        "sfx": sfx_list,
        "cues": timeline,
    }
    validate(tl, "audio_timeline")
    return dump_json(out_dir / "audio_timeline.json", tl)
