import json
import wave
from pathlib import Path

import pytest

from kes.audio.tts_adapter import PaidCallBlocked, VolcEnglishAdapter, synthesize_english_b, synthesize_live


def test_volc_english_adapter_body():
    ad = VolcEnglishAdapter()
    body = ad.build_body("Red!", {
        "speaker": "en_test_speaker", "explicit_language": "en", "speech_rate": -15,
    })
    assert body["req_params"]["speaker"] == "en_test_speaker"
    add = json.loads(body["req_params"]["additions"])
    assert add["explicit_language"] == "en"


def test_english_b_blocked_without_paid_flag(tmp_path):
    voices = {
        "live": {"zh": {"resource_id": "seed-tts-2.0", "speaker": "zh_female_xiaohe_uranus_bigtts", "voice_id": "v"}},
        "live_en_b": {"resource_id": "seed-tts-2.0", "speaker": "en_test", "voice_id": "volc:seed-tts-2.0:en_test",
                      "explicit_language": "en", "speech_rate": -20},
    }
    cues = [{"cue_id": "c001", "lang": "en", "text": "Red!"}]
    with pytest.raises(PaidCallBlocked):
        synthesize_english_b(cues, voices, tmp_path, allow_paid=False)
    with pytest.raises(PaidCallBlocked):
        synthesize_live(cues, voices, tmp_path, allow_paid=False, en_voice="b")


def test_english_b_cache_hit(tmp_path):
    voice = {"resource_id": "seed-tts-2.0", "speaker": "en_test", "voice_id": "volc:seed-tts-2.0:en_test",
             "explicit_language": "en", "speech_rate": -20}
    gdir = tmp_path / "live-en-b-20261120-000000"
    seg = gdir / "out" / "segments"
    seg.mkdir(parents=True)
    (gdir / "episode.json").write_text(json.dumps({"voice": voice, "lines": [{"id": 1, "text": "Red!"}]}),
                                       encoding="utf-8")
    wav = seg / "01-attempt1.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(b"\x00\x01" * 4800)
    ad = VolcEnglishAdapter()
    res = ad.synthesize([{"cue_id": "c001", "lang": "en", "text": "Red!"}], voice, tmp_path, allow_paid=True)
    assert res["c001"] == (wav, "volc:seed-tts-2.0:en_test")
