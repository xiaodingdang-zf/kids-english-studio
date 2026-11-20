"""风格包与镜头的离线验证，不依赖 TTS、生图或 ffmpeg。"""
from PIL import ImageChops

from kes.core.common import validate
from kes.core.script_generator import generate, parse_prompt
from kes.visual import clay, felt, render
from kes.visual.assets_plan import asset_plan
from kes.visual.styles import load_style


def test_style_packs_and_default():
    for style_id in ("clay", "felt"):
        style = load_style(style_id)
        assert style["style_id"] == style_id
        assert style["name"]["zh"] and style["name"]["en"]
        assert all(style["prompts"][part] for part in ("common", "character", "object", "background"))
    assert parse_prompt("颜色 3 个词").style == "clay"
    assert parse_prompt("颜色 3 个词，羊毛毡").style == "felt"
    assert parse_prompt("colors 3 words felt").style == "felt"
    ep = generate("做一集 40 秒的颜色，3 个词，羊毛毡")
    validate(ep, "episode")
    assert ep["style"] == "felt"
    plan = asset_plan(ep)
    assert all("assets/styles/felt/" in item["path"] for item in plan)
    assert "wool" in plan[0]["prompt"] and "wool" in plan[-1]["prompt"]
    assert "clay" in asset_plan(generate("颜色 3 个词"))[0]["prompt"]


def test_felt_texture_is_procedural():
    clay_bg = clay.background(180, 260, "colors")
    felt_bg = felt.background(180, 260, "colors")
    assert felt_bg.size == clay_bg.size
    assert ImageChops.difference(clay_bg.convert("RGB"), felt_bg.convert("RGB")).getbbox() is not None
    assert felt.background(180, 260, "colors").tobytes() == felt_bg.tobytes()


def test_camera_render_for_each_mode(monkeypatch):
    layout = {"size": (360, 640), "title": (180, 55), "object": (245, 220, 140),
              "otter": (100, 300, 160), "card": (180, 460, 300, 100),
              "subtitle": (180, 570), "badge": (180, 570)}
    monkeypatch.setitem(render.LAYOUTS, "portrait", layout)
    ep = generate("颜色 3 个词，羊毛毡")
    cues = [{"cue_id": c["cue_id"], "start_ms": i * 700, "end_ms": i * 700 + 450}
            for i, c in enumerate(ep["cues"])]
    timeline = {"total_duration_ms": len(cues) * 700, "cues": cues}
    manifest = render.build_manifest(ep, timeline)
    validate(manifest, "frames_manifest")
    assert {s["camera"] for s in manifest["shots"]} == {"static", "push_in", "pull_out", "pan"}
    renderer = render.Renderer(ep, manifest)
    for camera in ("static", "push_in", "pull_out", "pan"):
        manifest["shots"][0]["camera"] = camera
        assert renderer.frame(0).size == layout["size"]
        assert renderer.frame(2).size == layout["size"]

    shot = manifest["shots"][0]
    shot["camera"] = "push_in"
    base = renderer.bg.copy()
    assert render._camera_frame(base, shot, 0, layout["object"][:2]).tobytes() != (
        render._camera_frame(base, shot, 8, layout["object"][:2]).tobytes())
    assert render._camera_frame(base, shot, 0, layout["object"][:2]).tobytes() == (
        render._camera_frame(base, shot, 1, layout["object"][:2]).tobytes())
