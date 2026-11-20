"""采样配乐、回退、拟音与英文 B 配置的离线测试。"""
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from kes.audio import foley, music
from kes.audio.pipeline import _duck_envelope
from kes.audio.tts_adapter import PaidCallBlocked, synthesize_english_b
from kes.core.common import ROOT


def _wav(path: Path, pitch: int) -> None:
    t = np.arange(48000) / 48000
    x = (np.sin(2 * np.pi * 440 * 2 ** ((pitch - 69) / 12) * t)
         * np.exp(-t * 4) * 0.5 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(48000)
        f.writeframes(x.tobytes())


def test_missing_samples_fall_back(tmp_path):
    bed, info = music.render(2.0, "clay", samples=tmp_path)
    assert len(bed) == 96000
    assert np.max(np.abs(bed)) > 0
    assert info["asset_source"] == "kes:synth"


@pytest.mark.parametrize("style,mode,bpm", [("clay", "C_major", 96), ("felt", "A_minor", 82)])
def test_sampled_original_composition(tmp_path, style, mode, bpm):
    for midi, name in music.SAMPLE_NAMES.items():
        _wav(tmp_path / name, midi)
    bed, info = music.render(2.0, style, samples=tmp_path)
    assert len(bed) == 96000
    assert np.max(np.abs(bed)) > 0
    assert info["asset_source"] == "vsco2-ce:harp"
    assert (info["mode"], info["bpm"]) == (mode, bpm)


def test_foley_action_table():
    for kind in set(foley.ACTION_SOUNDS.values()) | {"pop", "chime"}:
        sound = foley.sound(kind)
        assert sound.dtype == np.float32
        assert len(sound) > 0
        assert np.max(np.abs(sound)) > 0
    np.testing.assert_array_equal(foley.sound("clap"), foley.sound("clap"))


def test_voice_ducks_music():
    voice = np.zeros(2 * music.SR, np.float32)
    voice[music.SR // 2:music.SR + music.SR // 2] = 0.2
    duck = _duck_envelope(voice)
    assert duck[0] == pytest.approx(1.0)
    assert duck[music.SR] == pytest.approx(0.35)
    assert duck[-1] == pytest.approx(1.0)


def test_english_b_requires_configuration_and_paid_gate(tmp_path):
    voices = json.loads((ROOT / "kes/audio/voices.json").read_text())
    cues = [{"cue_id": "c001", "lang": "en", "text": "Hello"}]
    with pytest.raises(ValueError, match="speaker/voice_id"):
        synthesize_english_b(cues, voices, tmp_path, False)
    voices["live_en_b"].update(speaker="ENGLISH_VOICE_ID", voice_id="volc:seed-tts-2.0:ENGLISH_VOICE_ID")
    with pytest.raises(PaidCallBlocked):
        synthesize_english_b(cues, voices, tmp_path, False)
    seen = {}

    class StubAdapter:
        def synthesize(self, c, v, w, a):
            seen["lang"] = v["explicit_language"]
            return {"c001": (tmp_path / "x.wav", v["voice_id"])}

    res = synthesize_english_b(cues, voices, tmp_path, True, adapter=StubAdapter())
    assert seen["lang"] == "en" and res["c001"][1] == "volc:seed-tts-2.0:ENGLISH_VOICE_ID"
