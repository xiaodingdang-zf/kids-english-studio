import pytest

from kes.audio import music
from kes.core.common import dump_json, validate
from kes.core.script_generator import ask_questions, generate, parse_prompt
from kes.visual.render import build_manifest, render_video
from kes.visual.styles import STYLE_ORDER, list_styles, load_style


@pytest.mark.parametrize("style_id", STYLE_ORDER)
def test_all_eight_styles_valid(style_id):
    s = load_style(style_id)
    assert s["style_id"] == style_id
    assert len(list_styles()) >= 8


@pytest.mark.parametrize("prompt,expected", [
    ("做一集黏土颜色", "clay"),
    ("做一集羊毛毡动物", "felt"),
    ("做一集纸艺数字", "papercraft"),
    ("做一集铁皮玩具颜色", "tin"),
    ("做一集纸箱水果", "cardboard"),
    ("做一集木偶动物", "wood"),
    ("做一集钩织数字", "crochet"),
    ("做一集拼布颜色", "fabric"),
])
def test_parse_all_eight_styles(prompt, expected):
    assert parse_prompt(prompt).style == expected


def test_questions_lists_all_eight_styles():
    q = ask_questions("做一集动物")
    style_q = next(x for x in q["questions"] if x["id"] == "style")
    assert len(style_q["options"]) == 8


@pytest.mark.parametrize("style_id", STYLE_ORDER)
def test_render_preview_all_eight_styles(style_id, tmp_path):
    ep = generate("做一集 30 秒的颜色，3 个词", answers={"style": style_id})
    validate(ep, "episode")
    ep_path = dump_json(tmp_path / "episode.json", ep)
    tl = {
        "schema_version": "1.0", "episode_id": ep["episode_id"], "mode": "mock",
        "sample_rate": 48000, "total_duration_ms": len(ep["cues"]) * 500,
        "master": "audio/master_mock.wav", "lufs": -16.0, "peak_db": -2.0,
        "bgm": None, "sfx": [],
        "cues": [{
            "cue_id": c["cue_id"], "lang": c["lang"], "voice_id": "mock:test:1",
            "start_ms": i * 500, "end_ms": i * 500 + 300,
            "pause_after_ms": 200, "asset_source": "mock:macos_say",
        } for i, c in enumerate(ep["cues"])],
    }
    dump_json(tmp_path / "audio_timeline.json", tl)
    build_manifest(ep, tl)
    pdir = render_video(ep_path, tmp_path, preview_frames=[0])
    assert (pdir / "frame_00000.png").is_file()


@pytest.mark.parametrize("style_id", STYLE_ORDER)
def test_music_renders_or_falls_back_for_all_styles(style_id, tmp_path):
    # Without samples in tmp_path, falls back cleanly
    audio, meta = music.render(2.0, style_id=style_id, samples=tmp_path)
    assert len(audio) == 48000 * 2
    assert meta["asset_source"] == "kes:synth"
