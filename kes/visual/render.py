"""逐帧合成引擎：episode.json + audio_timeline.json → frames_manifest.json → 定格动画 mp4。

- 输出 24fps，动作按 12fps 采样（每张画面停 2 帧，定格“一顿一顿”的质感），每张画面轻微“抖动”(boil)。
- 画面按实测 audio_timeline 排帧（唯一时长源）。
- 素材优先级：assets/ 下的生图素材（live）> 代码绘制的黏土占位（mock）。
"""
from __future__ import annotations

import bisect
import math
import random
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont

from ..core.common import ASSETS, ROOT, dump_json, load_json, validate
from . import clay, felt, materials
from .styles import load_style
from .sheets import EXPRESSIONS

FPS, ANIM_FPS = 24, 12
HOLD = FPS // ANIM_FPS
LAYOUTS = {
    "portrait": {
        "size": (1080, 1920), "title": (540, 150), "object": (745, 660, 420), "otter": (290, 830, 520),
        "card": (540, 1400, 900, 320), "subtitle": (540, 1650), "badge": (540, 1665),
    },
    "landscape": {
        "size": (1920, 1080), "title": (960, 80), "object": (1250, 380, 400), "otter": (520, 560, 520),
        "card": (1250, 760, 760, 250), "subtitle": (960, 1000), "badge": (960, 990),
    },
    "square": {
        "size": (1080, 1080), "title": (540, 90), "object": (745, 430, 350), "otter": (290, 590, 440),
        "card": (540, 850, 760, 210), "subtitle": (540, 1010), "badge": (540, 1010),
    },
}
FONT_ZH = ["/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"]
FONT_EN = ["/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


@lru_cache(maxsize=32)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    custom_otf = ASSETS / "fonts" / f"{kind}.otf"
    custom_ttf = ASSETS / "fonts" / f"{kind}.ttf"
    for path in ([str(custom_otf), str(custom_ttf)] if (custom_otf.exists() or custom_ttf.exists()) else []) + (FONT_ZH if kind == "zh" else FONT_EN):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
    return ImageFont.load_default(size)


# ------------------------------------------------------------------ manifest
def build_manifest(episode: dict, timeline: dict) -> dict:
    load_style(episode.get("style", "clay"))
    w, h = LAYOUTS[episode["aspect"]]["size"]
    by_id = {c["cue_id"]: c for c in timeline["cues"]}
    total_frames = math.ceil(timeline["total_duration_ms"] * FPS / 1000)
    shots = []
    for i, cue in enumerate(episode["cues"]):
        t = by_id.get(cue["cue_id"])
        if t is None:
            raise ValueError(f"audio_timeline 缺少 {cue['cue_id']}，请重新运行 kes audio")
        start = 0 if i == 0 else round(t["start_ms"] * FPS / 1000)
        shots.append({
            "cue_id": cue["cue_id"], "start_frame": start, "end_frame": total_frames,
            "speech_end_frame": round(t["end_ms"] * FPS / 1000),
            "camera": _camera_for(cue, i),
            "action": cue["action"], "word_index": cue["word_index"], "show_card": cue["show_card"],
            "repeat_prompt": cue["repeat_prompt"], "subtitle": cue["text"], "lang": cue["lang"],
        })
    for a, b in zip(shots, shots[1:]):
        if b["start_frame"] < a["start_frame"]:
            raise ValueError(f"时轴冲突：{b['cue_id']} 早于 {a['cue_id']}")
        a["end_frame"] = b["start_frame"]
    assets = _resolve_assets(episode)
    manifest = {
        "schema_version": "1.0", "episode_id": episode["episode_id"], "width": w, "height": h,
        "fps": FPS, "anim_fps": ANIM_FPS, "total_frames": total_frames, "shots": shots,
        "assets": [{"asset_id": k, "path": v[0], "asset_source": v[1]} for k, v in assets.items()],
    }
    validate(manifest, "frames_manifest")
    return manifest


def _camera_for(cue: dict, index: int) -> str:
    if cue["section"] == "outro":
        return "pull_out"
    if cue["show_card"]:
        return "push_in" if cue["section"] == "word" else "pan"
    if cue["word_index"] is not None:
        return "pan"
    return "static" if index == 0 else "push_in"


def _registered_source(path: Path) -> str:
    reg = ASSETS / "ASSET_SOURCES.json"
    if reg.exists():
        data = load_json(reg)
        rel = str(path.relative_to(ASSETS))
        if rel in data:
            return data[rel]
    return "image:unregistered"


def _resolve_assets(episode: dict) -> dict[str, tuple[str | None, str]]:
    out: dict[str, tuple[str | None, str]] = {}
    style_id = episode.get("style", "clay")
    asset_root = ASSETS if style_id == "clay" else ASSETS / "styles" / style_id
    char_dir = asset_root / "characters" / episode["character"]
    for pose in clay.POSES:
        p = char_dir / f"{pose}.png"
        if not p.exists():
            p = char_dir / "idle.png"
        out[f"character:{pose}"] = (str(p), _registered_source(p)) if p.exists() else (None, "kes:procedural")
        frames = [char_dir / pose / f"{i:03d}.png" for i in range(8)]
        if all(frame.exists() for frame in frames):
            for i, frame in enumerate(frames):
                out[f"character:{pose}:{i:03d}"] = (str(frame), _registered_source(frame))
    for expression in EXPRESSIONS:
        p = char_dir / "closeup" / f"{expression}.png"
        if p.exists():
            out[f"closeup:{expression}"] = (str(p), _registered_source(p))
    for w in episode["words"]:
        p = asset_root / "objects" / episode["theme"] / f"{w['en']}.png"
        out[f"object:{w['en']}"] = (str(p), _registered_source(p)) if p.exists() else (None, "kes:procedural")
    p = asset_root / "backgrounds" / f"{episode['theme']}_{episode['aspect']}.png"
    out["background"] = (str(p), _registered_source(p)) if p.exists() else (None, "kes:procedural")

    # 字体来源优先级：自定义 OFL 字体 > 系统字体
    zh_custom = ASSETS / "fonts" / "zh.otf"
    if zh_custom.exists():
        out["font:zh"] = (None, "font:ofl:source-han-sans-sc")
    else:
        out["font:zh"] = (None, "font:system:" + Path(font("zh", 10).path).name)

    en_custom = ASSETS / "fonts" / "en.ttf"
    if en_custom.exists():
        out["font:en"] = (None, "font:ofl:nunito")
    else:
        out["font:en"] = (None, "font:system:" + Path(font("en", 10).path).name)

    return out


# ------------------------------------------------------------------ drawing
@lru_cache(maxsize=64)
def _load_rgba(path: str, size: int) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    im.thumbnail((size, int(size * 1.2)), Image.LANCZOS)
    return im


def _boil(im: Image.Image, variant: int) -> Image.Image:
    rng = random.Random(variant)
    return im.rotate(rng.uniform(-1.2, 1.2), resample=Image.BICUBIC, expand=False)


def _paste_center(base: Image.Image, im: Image.Image, cx: float, cy: float) -> None:
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


@lru_cache(maxsize=64)
def _card(en: str, zh: str, hex_color: str | None, w: int, h: int, scale_q: int) -> Image.Image:
    s = scale_q / 100
    W, H = max(1, int(w * s)), max(1, int(h * s))
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, W - 1, H - 1], radius=int(60 * s), fill=255)
    card = clay.clay_fill(m, (255, 249, 236), 9)
    d = ImageDraw.Draw(card)
    color = clay.hex_rgb(hex_color) if hex_color else (230, 90, 60)
    if sum(color) > 600 or (color[0] > 230 and color[1] > 180):  # 白/黄等浅色字加深描边
        stroke = (90, 60, 40)
    else:
        stroke = (255, 255, 255)
    f_en = font("en", int(h * 0.42 * s))
    d.text((W / 2, H * 0.40), en, font=f_en, fill=color, anchor="mm", stroke_width=max(2, int(6 * s)),
           stroke_fill=stroke)
    d.text((W / 2, H * 0.80), zh, font=font("zh", int(h * 0.2 * s)), fill=(110, 75, 50), anchor="mm")
    return card


@lru_cache(maxsize=256)
def _subtitle(text: str, max_w: int) -> Image.Image:
    f = font("zh", 56)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=f)
    tw, th = min(r - l, max_w), b - t
    im = Image.new("RGBA", (tw + 80, th + 50), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=(th + 50) // 2, fill=(60, 40, 28, 170))
    d.text((im.width / 2, im.height / 2), text, font=f, fill=(255, 255, 255), anchor="mm")
    return im


@lru_cache(maxsize=16)
def _badge(filled: int) -> Image.Image:
    im = Image.new("RGBA", (560, 150), (0, 0, 0, 0))
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, 559, 149], radius=75, fill=255)
    im.alpha_composite(clay.clay_fill(m, (255, 214, 102), 11))
    d = ImageDraw.Draw(im)
    d.text((280, 52), "跟我念 · Your turn!", font=font("zh", 46), fill=(110, 60, 20), anchor="mm")
    for i in range(3):
        x = 230 + i * 50
        d.ellipse([x - 13, 100, x + 13, 126], fill=(226, 90, 50) if i < filled else (255, 245, 220))
    return im


@lru_cache(maxsize=4)
def _title(text: str) -> Image.Image:
    f = font("zh", 64)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=f)
    im = Image.new("RGBA", (r - l + 100, b - t + 60), (0, 0, 0, 0))
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=im.height // 2, fill=255)
    im.alpha_composite(clay.clay_fill(m, (255, 140, 90), 12))
    ImageDraw.Draw(im).text((im.width / 2, im.height / 2), text, font=f, fill=(255, 255, 255), anchor="mm",
                            stroke_width=3, stroke_fill=(170, 70, 40))
    return im


@lru_cache(maxsize=4)
def _shadow(w: int) -> Image.Image:
    from PIL import ImageFilter
    im = Image.new("RGBA", (w + 40, 80), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([20, 20, w + 20, 60], fill=(60, 40, 10, 110))
    return im.filter(ImageFilter.GaussianBlur(8))


POP = [0.55, 0.95, 1.12, 1.0]  # 12fps 下的弹出缩放序列


def _camera_frame(image: Image.Image, shot: dict, frame: int, object_center: tuple[int, int]) -> Image.Image:
    """只在 12fps 采样点移动整帧；轻微 crop 保证摇镜不露边。"""
    camera = shot.get("camera", "static")
    closeup = bool(shot["show_card"] and shot["word_index"] is not None)
    if camera == "static" and not closeup:
        return image
    steps = max(1, (shot["end_frame"] - shot["start_frame"]) // HOLD)
    progress = min(1.0, max(0.0, (frame // HOLD - shot["start_frame"] // HOLD) / steps))
    zoom = {"static": 1.0, "push_in": 1.02 + 0.06 * progress,
            "pull_out": 1.08 - 0.06 * progress, "pan": 1.06}[camera]
    if closeup:
        zoom += 0.06
    w, h = image.size
    crop_w, crop_h = w / zoom, h / zoom
    cx, cy = w / 2, h / 2
    if closeup:
        cx += (object_center[0] - cx) * 0.22
        cy += (object_center[1] - cy) * 0.12
    if camera == "pan":
        cx += (progress - 0.5) * w * 0.06
    left = max(0, min(w - crop_w, cx - crop_w / 2))
    top = max(0, min(h - crop_h, cy - crop_h / 2))
    box = (round(left), round(top), round(left + crop_w), round(top + crop_h))
    return image.crop(box).resize((w, h), Image.BICUBIC)


@lru_cache(maxsize=8)
def _color_lut(warmth: float, contrast: float) -> tuple[int, ...]:
    x = np.arange(256, dtype=np.float32) / 255
    curve = ((x ** 0.97 - 0.5) * contrast + 0.5) * 255
    return tuple(int(np.clip(v + offset * 255, 0, 255))
                 for offset in (warmth * 0.055, warmth * 0.014, -warmth * 0.07)
                 for v in curve)


@lru_cache(maxsize=8)
def _vignette(w: int, h: int, strength: float) -> Image.Image:
    x = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    y = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    radius = np.sqrt(x * x + y * y)
    mask = Image.fromarray(((1 - strength * np.clip((radius - 0.2) / 1.2, 0, 1) ** 1.5) * 255)
                           .astype(np.uint8), "L")
    return Image.merge("RGB", (mask, mask, mask))


def _grade(image: Image.Image, params: dict) -> Image.Image:
    image = ImageEnhance.Color(image).enhance(params["saturation"])
    image = image.point(_color_lut(params["warmth"], params["contrast"]))
    return ImageChops.multiply(image, _vignette(*image.size, params["vignette"]))


class Renderer:
    def __init__(self, episode: dict, manifest: dict):
        self.ep, self.mf = episode, manifest
        self.style = load_style(episode.get("style", "clay"))
        self.style_id = self.style["style_id"]
        self.procedural = felt if self.style_id == "felt" else clay
        self.L = LAYOUTS[episode["aspect"]]
        self.assets = {a["asset_id"]: a["path"] for a in manifest["assets"]}
        self.starts = [s["start_frame"] for s in manifest["shots"]]
        self.first_card: dict[int, int] = {}
        self.first_obj: dict[int, int] = {}
        for s in manifest["shots"]:
            if s["word_index"] is not None:
                self.first_obj.setdefault(s["word_index"], s["start_frame"])
                if s["show_card"]:
                    self.first_card.setdefault(s["word_index"], s["start_frame"])
        w, h = self.L["size"]
        bg_path = self.assets.get("background")
        if bg_path:
            from PIL import ImageOps
            self.bg = ImageOps.fit(Image.open(bg_path).convert("RGBA"), (w, h), Image.LANCZOS)
        else:
            self.bg = self.procedural.background(w, h, episode["theme"])
            if self.style_id not in ("clay", "felt"):
                self.bg = materials.apply_material(self.style_id, self.bg, 400)
        self.title = _title(f"{clay_name(episode)}学英语 · {episode['theme_en'].capitalize()} {episode['theme_zh']}")
        if self.style_id != "clay":
            self.title = materials.apply_material(self.style_id, self.title, 401)

    def shot_at(self, frame: int) -> dict:
        return self.mf["shots"][bisect.bisect_right(self.starts, frame) - 1]

    def character_path(self, pose: str, shot: dict, frame: int) -> tuple[str | None, bool]:
        """Prefer expression close-ups, then 12fps action frames, then legacy stills."""
        if shot["show_card"] or shot["repeat_prompt"]:
            expression = ("curious" if shot["repeat_prompt"] else
                          {"jump": "surprised", "point": "curious", "clap": "proud"}.get(pose, "happy"))
            closeup = self.assets.get(f"closeup:{expression}")
            if closeup:
                return closeup, True
        index = ((frame - shot["start_frame"]) // HOLD) % 8
        sequence = self.assets.get(f"character:{pose}:{index:03d}")
        if sequence:
            return sequence, True
        return self.assets.get(f"character:{pose}"), False

    def frame(self, f: int) -> Image.Image:
        k = f // HOLD                      # 12fps 画面序号
        variant, phase = k % 3, k % 4
        shot = self.shot_at(f)
        img = self.bg.copy()
        tx, ty = self.L["title"]
        _paste_center(img, self.title, tx, ty)

        wi = shot["word_index"]
        if wi is not None:
            word = self.ep["words"][wi]
            ox, oy, osz = self.L["object"]
            path = self.assets.get(f"object:{word['en']}")
            if path:
                spr = _boil(_load_rgba(path, osz), variant)
            else:
                spr = self.procedural.object_sprite(self.ep["theme"], word["en"], word.get("hex"),
                                                    word.get("count"), variant, osz)
                if self.style_id not in ("clay", "felt"):
                    spr = materials.apply_material(self.style_id, spr, 402 + variant)
            pk = (f - self.first_obj[wi]) // HOLD
            if 0 <= pk < len(POP):
                s = POP[pk]
                spr = spr.resize((max(1, int(spr.width * s)), max(1, int(spr.height * s))), Image.BICUBIC)
            _paste_center(img, spr, ox, oy)

        ax, ay, asz = self.L["otter"]
        pose = shot["action"] if shot["action"] in clay.POSES else "idle"
        if f > shot["speech_end_frame"] + HOLD * 2 and not shot["repeat_prompt"]:
            pose = "idle"
        path, animated = self.character_path(pose, shot, f)
        if path:
            spr = _load_rgba(path, asz) if animated else _boil(_load_rgba(path, asz), variant)
            sh = _shadow(int(spr.width * 0.75))
            _paste_center(img, sh, ax, ay + spr.height / 2 - 10)
            if not animated:
                ay += [0, -4, 0, 4][phase]
        else:
            spr = self.procedural.otter_sprite(pose, phase, variant, asz)
            if self.style_id not in ("clay", "felt"):
                spr = materials.apply_material(self.style_id, spr, 405 + phase)
        _paste_center(img, spr, ax, ay)

        if wi is not None and shot["show_card"]:
            word = self.ep["words"][wi]
            cx, cy, cw, ch = self.L["card"]
            pk = (f - self.first_card[wi]) // HOLD
            s = POP[pk] if 0 <= pk < len(POP) else 1.0
            card = _card(word["en"].capitalize(), word["zh"], word.get("hex"), cw, ch, int(s * 100))
            if self.style_id != "clay":
                card = _styled_card(self.style_id, word["en"].capitalize(), word["zh"], word.get("hex"), cw, ch, int(s * 100))
            _paste_center(img, card, cx, cy)

        if shot["repeat_prompt"] and f > shot["speech_end_frame"] + HOLD * 3:
            span = max(1, shot["end_frame"] - shot["speech_end_frame"])
            filled = min(3, 1 + int(3 * (f - shot["speech_end_frame"]) / span))
            bx, by = self.L["badge"]
            badge = _styled_badge(self.style_id, filled) if self.style_id != "clay" else _badge(filled)
            _paste_center(img, badge, bx, by)

        if f <= shot["speech_end_frame"] + HOLD * 3:
            sx, sy = self.L["subtitle"]
            _paste_center(img, _subtitle(shot["subtitle"], self.L["size"][0] - 120), sx, sy)
        img = _camera_frame(img, shot, f, self.L["object"][:2])
        return _grade(img.convert("RGB"), self.style["color_grade"])


@lru_cache(maxsize=64)
def _styled_card(style_id: str, en: str, zh: str, hex_color: str | None, w: int, h: int, scale_q: int) -> Image.Image:
    return materials.apply_material(style_id, _card(en, zh, hex_color, w, h, scale_q), 409)


@lru_cache(maxsize=32)
def _styled_badge(style_id: str, filled: int) -> Image.Image:
    return materials.apply_material(style_id, _badge(filled), 419 + filled)


def clay_name(ep: dict) -> str:
    from ..core.wordbank import CHARACTERS
    return CHARACTERS.get(ep["character"], {}).get("zh", ep["character"])


def render_video(episode_path: Path, out_dir: Path, preview_frames: list[int] | None = None) -> Path:
    episode = load_json(episode_path)
    timeline = load_json(out_dir / "audio_timeline.json")
    if timeline["episode_id"] != episode["episode_id"]:
        raise ValueError("audio_timeline 与 episode 不匹配")
    manifest = build_manifest(episode, timeline)
    dump_json(out_dir / "frames_manifest.json", manifest)
    r = Renderer(episode, manifest)
    w, h = manifest["width"], manifest["height"]

    if preview_frames is not None:
        pdir = out_dir / "preview"
        pdir.mkdir(parents=True, exist_ok=True)
        for f in preview_frames:
            r.frame(min(f, manifest["total_frames"] - 1)).save(pdir / f"frame_{f:05d}.png")
        return pdir

    master = out_dir / timeline["master"]
    video = out_dir / f"{episode['episode_id']}_{timeline['mode']}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(FPS), "-i", "-", "-i", str(master), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-map", "0:v", "-map", "1:a", str(video)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = manifest["total_frames"]
    try:
        for f in range(0, total, HOLD):
            data = r.frame(f).tobytes()
            for _ in range(min(HOLD, total - f)):
                proc.stdin.write(data)
    finally:
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg 编码失败")
    return video
