"""Pipeline tests that run offline (no `say`, no network): fake audio segments → render preview → manifest."""
import json
import wave
from pathlib import Path

import numpy as np

from kes.audio import pipeline
from kes.core.common import dump_json, load_json, validate
from kes.core.script_generator import generate
from kes.visual.render import build_manifest, render_video


def _fake_segments(cues, voices, seg_dir: Path):
    out = {}
    seg_dir.mkdir(parents=True, exist_ok=True)
    for c in cues:
        n = int(48000 * (0.3 + 0.02 * len(c["text"])))
        x = (np.sin(np.arange(n) * 2 * np.pi * 220 / 48000) * 0.3 * 32767).astype(np.int16)
        p = seg_dir / f"{c['cue_id']}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(x.tobytes())
        out[c["cue_id"]] = (p, "mock:macos_say:Fake")
    return out


def _fake_segments_silent(cues, voices, seg_dir: Path):
    """Generate fake audio segments that are too short (<150ms)."""
    out = {}
    seg_dir.mkdir(parents=True, exist_ok=True)
    for c in cues:
        # Generate only 100ms of audio (< 150ms threshold)
        n = int(48000 * 0.1)  # 100ms
        x = np.zeros(n, dtype=np.int16)  # Silent
        p = seg_dir / f"{c['cue_id']}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(x.tobytes())
        out[c["cue_id"]] = (p, "mock:macos_say:Fake")
    return out


def test_audio_render_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "synthesize_mock", _fake_segments)
    ep = generate("颜色 30 秒 3 个词")
    ep_path = dump_json(tmp_path / "episode.json", ep)
    tl_path = pipeline.synthesize_audio(ep_path, tmp_path, "mock")
    tl = load_json(tl_path)
    validate(tl, "audio_timeline")
    assert [c["cue_id"] for c in tl["cues"]] == [c["cue_id"] for c in ep["cues"]]
    starts = [c["start_ms"] for c in tl["cues"]]
    assert starts == sorted(starts)
    assert abs(tl["lufs"] + 16) <= 1.0

    mf = build_manifest(ep, tl)
    validate(mf, "frames_manifest")
    assert mf["shots"][0]["start_frame"] == 0
    assert all(a["end_frame"] == b["start_frame"] for a, b in zip(mf["shots"], mf["shots"][1:]))

    pdir = render_video(ep_path, tmp_path, preview_frames=[0, 50, mf["total_frames"] - 1])
    assert len(list(pdir.glob("*.png"))) == 3


def test_silence_protection(tmp_path, monkeypatch):
    """Test that audio segments shorter than 150ms raise an error."""
    import pytest
    monkeypatch.setattr(pipeline, "synthesize_mock", _fake_segments_silent)
    ep = generate("颜色 30 秒 3 个词")
    ep_path = dump_json(tmp_path / "episode.json", ep)

    with pytest.raises(ValueError, match="静音保护"):
        pipeline.synthesize_audio(ep_path, tmp_path, "mock")


def test_long_silence_protection(tmp_path, monkeypatch):
    import pytest
    def silent_one_second(cues, voices, seg_dir):
        segments = _fake_segments(cues, voices, seg_dir)
        first = next(iter(segments.values()))[0]
        pipeline.write_wav(first, np.zeros(pipeline.SR, dtype=np.float32))
        return segments
    monkeypatch.setattr(pipeline, "synthesize_mock", silent_one_second)
    ep_path = dump_json(tmp_path / "episode.json", generate("动物 30 秒 3 个词"))
    with pytest.raises(ValueError, match="c001.*0ms"):
        pipeline.synthesize_audio(ep_path, tmp_path, "mock")


def test_square_preview_and_qc_resolution(tmp_path, monkeypatch):
    from PIL import Image
    from kes.qc import checker
    monkeypatch.setattr(pipeline, "synthesize_mock", _fake_segments)
    ep = generate("动物 30 秒 3 个词 方形")
    ep_path = dump_json(tmp_path / "episode.json", ep)
    tl = load_json(pipeline.synthesize_audio(ep_path, tmp_path, "mock", bgm=False))
    preview = render_video(ep_path, tmp_path, preview_frames=[0])
    with Image.open(preview / "frame_00000.png") as image:
        assert image.size == (1080, 1080)
    monkeypatch.setattr(checker, "_probe", lambda _: {"streams": [
        {"codec_type": "video", "width": 1080, "height": 1080, "r_frame_rate": "24/1", "duration": str(tl["total_duration_ms"] / 1000)},
        {"codec_type": "audio", "duration": str(tl["total_duration_ms"] / 1000)}],
        "format": {"duration": str(tl["total_duration_ms"] / 1000)}})
    monkeypatch.setattr(checker, "_loudness", lambda _: (-16.0, -2.0))
    monkeypatch.setattr(checker, "_black_segments", lambda _: [])
    report = load_json(checker.run_qc(ep_path, tmp_path))
    assert next(c for c in report["checks"] if c["rule_id"] == "video.resolution")["status"] == "PASS"
    assert all(c["status"] == "PASS" for c in report["checks"] if c["rule_id"].startswith("pedagogy.pause."))


def test_live_blocked_without_approval(tmp_path):
    import pytest
    from kes.audio.tts_adapter import PaidCallBlocked
    ep_path = dump_json(tmp_path / "episode.json", generate("颜色 30 秒 3 个词"))
    with pytest.raises(PaidCallBlocked):
        pipeline.synthesize_audio(ep_path, tmp_path, "live", allow_paid=False)
