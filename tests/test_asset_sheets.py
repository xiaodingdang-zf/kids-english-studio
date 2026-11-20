"""Offline sprite sheets and approved generation via a fake codex executable."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from kes import cli
from kes.core.common import dump_json
from kes.core.script_generator import generate
from kes.visual import assets_plan, render
from kes.visual.sheets import slice_sheet


def _sheet(path: Path, rows: int = 2, cols: int = 4) -> Path:
    image = Image.new("RGB", (cols * 60, rows * 70), "#00FF00")
    draw = ImageDraw.Draw(image)
    for i in range(rows * cols):
        x, y = (i % cols) * 60, (i // cols) * 70
        draw.rectangle((x + 12, y + 15 + i, x + 43, y + 55), fill=(180, 40 + i, 30))
    image.save(path)
    return path


def test_slice_action_sheet_aligns_and_keys(tmp_path):
    sheet = _sheet(tmp_path / "sheet.png")
    out = tmp_path / "frames"
    cli.main(["slice", str(sheet), "--grid", "2x4", "--out", str(out)])
    frames = [Image.open(out / f"{i:03d}.png") for i in range(8)]
    assert len(frames) == 8
    assert len({im.size for im in frames}) == 1
    assert all(im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0 for im in frames)
    assert len({im.getchannel("A").getbbox()[3] for im in frames}) == 1
    assert len({im.tobytes() for im in frames}) == 8


def test_closeup_sheet_names(tmp_path):
    sheet = _sheet(tmp_path / "faces.png", cols=2)
    paths = slice_sheet(sheet, "2x2", tmp_path / "faces",
                        ["happy.png", "surprised.png", "curious.png", "proud.png"])
    assert [path.name for path in paths] == ["happy.png", "surprised.png", "curious.png", "proud.png"]


def test_renderer_prefers_sequence_and_closeup(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "ASSETS", tmp_path)
    base = tmp_path / "characters" / "ollie"
    idle = base / "idle.png"
    idle.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (20, 20), "blue").save(idle)
    for i in range(8):
        path = base / "wave" / f"{i:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (20, 20), (i * 20, 30, 40, 255)).save(path)
    closeup = base / "closeup" / "happy.png"
    closeup.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (20, 20), "red").save(closeup)
    ep = generate("颜色 30 秒 3 个词")
    cues = [{"cue_id": c["cue_id"], "start_ms": i * 700, "end_ms": i * 700 + 500}
            for i, c in enumerate(ep["cues"])]
    mf = render.build_manifest(ep, {"total_duration_ms": len(cues) * 700, "cues": cues})
    assert len([a for a in mf["assets"] if a["asset_id"].startswith("character:wave:")]) == 8
    renderer = render.Renderer(ep, mf)
    shot = {"start_frame": 0, "show_card": False, "repeat_prompt": False}
    assert renderer.character_path("wave", shot, 0) == (str(base / "wave" / "000.png"), True)
    assert renderer.character_path("wave", shot, 2) == (str(base / "wave" / "001.png"), True)
    assert renderer.character_path("wave", shot, 16) == (str(base / "wave" / "000.png"), True)
    shot["show_card"] = True
    assert renderer.character_path("wave", shot, 0) == (str(closeup), True)
    shot["show_card"] = False
    assert renderer.character_path("idle", shot, 0) == (str(idle), False)


def test_fill_assets_dry_run_approval_and_fake_codex(tmp_path, monkeypatch, capsys):
    assets = tmp_path / "assets"
    assets.mkdir()
    sheet = _sheet(tmp_path / "fixture.png")
    concept = assets / "ollie" / "concepts" / "ollie_A.png"
    idle = assets / "characters" / "ollie" / "idle.png"
    concept.parent.mkdir(parents=True)
    idle.parent.mkdir(parents=True)
    Image.new("RGB", (10, 10), "red").save(concept)
    Image.new("RGB", (10, 10), "red").save(idle)
    ep_dir = tmp_path / "episode"
    dump_json(ep_dir / "episode.json", generate("颜色 30 秒 3 个词"))
    target = assets / "characters" / "ollie" / "wave_sheet.png"
    item = {"path": str(target), "kind": "action_sheet", "grid": "2x4",
            "frames": [str(assets / "characters" / "ollie" / "wave" / f"{i:03d}.png") for i in range(8)],
            "prompt": "fake action sheet", "post": "slice"}
    monkeypatch.setattr(cli, "ASSETS", assets)
    monkeypatch.setattr(assets_plan, "asset_plan", lambda ep: [item])
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$KES_FAKE_LOG\"\ncp \"$KES_FAKE_IMAGE\" \"$KES_OUTPUT_PATH\"\n")
    fake.chmod(0o755)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("KES_FAKE_LOG", str(log))
    monkeypatch.setenv("KES_FAKE_IMAGE", str(sheet))
    args = argparse.Namespace(episode=str(ep_dir), approve=None)
    cli.cmd_fill_assets(args)
    assert "预计生图 1 张" in capsys.readouterr().out
    assert not log.exists() and not target.exists()
    args.approve = 0
    with pytest.raises(SystemExit, match="小于缺图数"):
        cli.cmd_fill_assets(args)
    assert not log.exists()
    args.approve = 1
    cli.cmd_fill_assets(args)
    assert "-i " + str(concept) in log.read_text()
    assert "-i " + str(idle) in log.read_text()
    assert len(list(target.parent.joinpath("wave").glob("*.png"))) == 8
    sources = json.loads((assets / "ASSET_SOURCES.json").read_text())
    assert sources["characters/ollie/wave/000.png"] == "openai:image_gen"
    cli.cmd_fill_assets(args)
    assert len(log.read_text().splitlines()) == 1


def test_make_live_stops_before_audio_when_assets_missing(tmp_path, monkeypatch):
    ep_path = dump_json(tmp_path / "episode.json", generate("颜色 30 秒 3 个词"))
    monkeypatch.setattr(cli, "cmd_script", lambda args: ep_path)
    monkeypatch.setattr(cli, "cmd_assets", lambda args: [{"path": "missing.png"}])
    monkeypatch.setattr(cli, "cmd_audio", lambda args: pytest.fail("live audio must not run"))
    args = argparse.Namespace(mode="live", allow_paid=False, no_bgm=False, en_voice="a")
    with pytest.raises(SystemExit, match="fill-assets"):
        cli.cmd_make(args)
