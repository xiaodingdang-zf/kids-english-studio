"""生图素材清单：告诉宿主 agent（Codex/Claude）live 模式需要生成哪些图片、存到哪里、用什么提示词。

提示词为本项目原创模板。KES 本身不调用任何生图 API；由宿主 agent 用它自己的生图能力完成，
生成后在 assets/ASSET_SOURCES.json 里登记来源，QC 才会放行。
"""
from __future__ import annotations

from pathlib import Path

from ..core.common import ASSETS
from ..core.wordbank import CHARACTERS
from . import clay
from .styles import load_style
from .sheets import EXPRESSIONS

CHARACTER_BRIEF = {
    "ollie": ("Ollie, an original little river otter character exactly matching the reference image "
              "assets/ollie/concepts/ollie_A.png: chubby round body, warm reddish-brown fur, big cream belly "
              "and cream muzzle, small round ears, big glossy black eyes with white highlights, dark brown "
              "eyebrows and whiskers, short thick tail, plus a red chunky knitted scarf around the neck "
              "(his signature accessory). Curious and slightly clumsy. Original design, not resembling any "
              "existing cartoon or brand character."),
}

POSE_TEXT = {
    "idle": "standing relaxed, arms down, gentle smile",
    "wave": "waving hello with right paw raised high, mouth open happily",
    "jump": "jumping with joy, both paws up, feet off the ground",
    "clap": "clapping paws together in front of chest, delighted",
    "point": "pointing to the right side with right paw, looking right, curious face",
    "nod": "nodding with eyes half closed, content smile",
    "listen": "cupping right paw behind ear, listening carefully, eyebrows raised",
}


def asset_plan(episode: dict) -> list[dict]:
    style_id = episode.get("style", "clay")
    style = load_style(style_id)
    asset_root = ASSETS if style_id == "clay" else ASSETS / "styles" / style_id
    prompts = style["prompts"]
    char = episode["character"]
    brief = CHARACTER_BRIEF.get(char, CHARACTERS.get(char, {}).get("en", char))
    items = []
    for pose in clay.POSES:
        items.append({
            "path": str(asset_root / "characters" / char / f"{pose}.png"),
            "kind": "character",
            "required": pose == "idle",  # legacy single-frame fallback; idle is the generation reference
            "prompt": (f"{brief} {POSE_TEXT[pose]}. {prompts['character']}. {prompts['common']}. "
                       f"{style['lighting']}. Solid flat background color #00FF00 for easy cut-out."),
            "post": "抠掉 #00FF00 背景，存为透明 PNG；所有姿势保持同一造型（先生成 idle 作为参考图再生成其它姿势）",
        })
    for pose in clay.POSES:
        base = asset_root / "characters" / char
        items.append({
            "path": str(base / f"{pose}_sheet.png"),
            "kind": "action_sheet", "grid": "2x4",
            "frames": [str(base / pose / f"{i:03d}.png") for i in range(8)],
            "prompt": (f"{brief} {POSE_TEXT[pose]}. Eight consecutive frames of ONE {pose} action, "
                       f"reading left-to-right, top-to-bottom in an exact 2-row by 4-column grid; "
                       f"same character, scale and camera in every cell, feet at a consistent baseline, "
                       f"no text or borders. {prompts['character']}. {prompts['common']}. "
                       "Solid flat #00FF00 green background in every cell."),
            "post": "kes slice <sheet.png> --grid 2x4 --out <characters/角色/动作/>；生成 8 张透明对齐帧",
        })
    base = asset_root / "characters" / char
    items.append({
        "path": str(base / "closeup_sheet.png"),
        "kind": "closeup_sheet", "grid": "2x2",
        "frames": [str(base / "closeup" / f"{name}.png") for name in EXPRESSIONS],
        "prompt": (f"{brief} Face and upper-body close-ups in an exact 2-row by 2-column grid, "
                   "left-to-right, top-to-bottom: happy, surprised, curious, proud. "
                   "Same character, scale and camera; no text or borders. "
                   f"{prompts['character']}. {prompts['common']}. "
                   "Solid flat #00FF00 green background in every cell."),
        "post": "kes slice <sheet.png> --grid 2x2 --out <characters/角色/closeup/>；按表情命名",
    })
    for w in episode["words"]:
        if episode["theme"] == "colors":
            subj = f"a single round blob of {w['en']} color with a tiny bump on top"
            key = "#FF00FF" if w["en"] == "green" else "#00FF00"
        elif episode["theme"] == "numbers":
            subj = f"exactly {w.get('count')} small colorful balls arranged neatly"
        else:
            subj = f"a cute {w['en']}, simple and iconic"
        if episode["theme"] != "colors":
            key = "#FF00FF" if w["en"] in ("pear", "watermelon", "lemon") else "#00FF00"
        items.append({
            "path": str(asset_root / "objects" / episode["theme"] / f"{w['en']}.png"),
            "kind": "object",
            "prompt": (f"{subj}, centered, {prompts['object']}. {prompts['common']}. {style['lighting']}. "
                       f"Solid flat background color {key} for easy cut-out."),
            "post": f"kes cutout --key {'magenta' if key == '#FF00FF' else 'green'} 抠图为透明 PNG",
        })
    orient = "vertical 9:16" if episode["aspect"] == "portrait" else "horizontal 16:9"
    items.append({
        "path": str(asset_root / "backgrounds" / f"{episode['theme']}_{episode['aspect']}.png"),
        "kind": "background",
        "prompt": (f"{orient} {prompts['background']}. {style['background']}. "
                   f"{style['lighting']}. {prompts['common']}"),
        "post": "直接存 PNG，不需要抠图",
    })
    return items


def missing_assets(plan: list[dict]) -> list[dict]:
    """One missing sheet counts as one image, not eight/four output frames."""
    return [item for item in plan if item.get("required", True) and
            not (all(Path(p).exists() for p in item["frames"]) if "frames" in item
                 else Path(item["path"]).exists())]
