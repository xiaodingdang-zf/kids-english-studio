"""程序化“黏土”绘制：阴影、高光、指纹噪点，以及奥利（小水獭）占位角色。

mock 模式全部由代码绘制（版权归项目）；live 模式若 assets/ 下有生图素材则优先使用。
"""
from __future__ import annotations

import math
import random
import zlib
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=8)
def _noise(w: int, h: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, (h // 4 + 1, w // 4 + 1)).astype(np.float32)
    img = Image.fromarray(((n * 30) + 128).clip(0, 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    fine = rng.normal(0, 1, (h, w)).astype(np.float32) * 6
    return (np.asarray(img, np.float32) - 128) + fine


def clay_fill(mask: Image.Image, color: tuple[int, int, int], seed: int = 0, light=(-0.35, -0.45)) -> Image.Image:
    """把一个 L 模式遮罩渲染成有体积感的黏土块（RGBA）。"""
    w, h = mask.size
    m = np.asarray(mask, np.float32) / 255
    r = max(4, int(min(w, h) * 0.06))
    soft = np.asarray(mask.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255
    dx, dy = int(light[0] * r * 2), int(light[1] * r * 2)
    shifted = np.asarray(ImageChops.offset(mask, -dx, -dy).filter(ImageFilter.GaussianBlur(r * 1.5)), np.float32) / 255
    shade = 0.72 + 0.28 * soft + 0.22 * (shifted - soft * 0.6)
    rim = np.clip(1 - soft, 0, 1) * m
    shade -= 0.18 * rim
    tex = _noise(w, h, seed % 5) / 255 * 0.55
    base = np.array(color, np.float32)[None, None, :] / 255
    rgb = np.clip(base * shade[..., None] + tex[..., None] * 0.6, 0, 1)
    out = np.dstack([rgb * 255, m * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def ellipse_mask(w: int, h: int, box, angle: float = 0.0) -> Image.Image:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse(box, fill=255)
    if angle:
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        m = m.rotate(angle, resample=Image.BICUBIC, center=(cx, cy))
    return m


def _wobble(rng: random.Random, box, amt: float):
    return [v + rng.uniform(-amt, amt) for v in box]


# ---------------------------------------------------------------- 奥利
OTTER = {
    "fur": (138, 90, 59),
    "fur_dark": (110, 70, 45),
    "belly": (241, 221, 191),
    "nose": (58, 38, 30),
    "cheek": (240, 150, 140),
    "eye": (30, 24, 22),
}

POSES = ("idle", "wave", "jump", "clap", "point", "nod", "listen")


def _arm_angle(pose: str, phase: int, side: str) -> float:
    """返回手臂角度（度，0 = 垂下，正 = 向外抬起）。"""
    osc = [0, 1, 0, -1][phase % 4]
    if side == "left":
        return {"clap": 55 + 12 * osc, "jump": 60}.get(pose, 12)
    return {
        "wave": 150 + 20 * osc,
        "point": 95,
        "clap": 55 - 12 * osc,
        "jump": 60,
        "listen": 150,
    }.get(pose, 12)


@lru_cache(maxsize=256)
def otter_sprite(pose: str, phase: int, variant: int, size: int = 560) -> Image.Image:
    W, H = size, int(size * 1.15)
    rng = random.Random(zlib.crc32(f'{pose}|{phase}|{variant}'.encode()))
    j = size * 0.006  # 定格“抖动”幅度
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cx = W / 2
    lift = {"jump": [0, -0.06, -0.09, -0.04][phase % 4]}.get(pose, 0) * H
    bob = [0, -0.004, 0, 0.004][phase % 4] * H

    def put(mask, color, seed):
        canvas.alpha_composite(clay_fill(mask, color, seed))

    y0 = 0.40 * H + lift + bob
    # 尾巴
    put(ellipse_mask(W, H, _wobble(rng, [cx + 0.05 * W, y0 + 0.36 * H, cx + 0.48 * W, y0 + 0.52 * H], j), -25),
        OTTER["fur_dark"], 1)
    # 脚
    for s in (-1, 1):
        fx = cx + s * 0.13 * W
        put(ellipse_mask(W, H, _wobble(rng, [fx - 0.09 * W, y0 + 0.47 * H - lift, fx + 0.09 * W,
                                             y0 + 0.55 * H - lift], j)), OTTER["fur_dark"], 2)
    # 身体 + 肚子
    put(ellipse_mask(W, H, _wobble(rng, [cx - 0.27 * W, y0, cx + 0.27 * W, y0 + 0.52 * H], j)), OTTER["fur"], 3)
    put(ellipse_mask(W, H, _wobble(rng, [cx - 0.17 * W, y0 + 0.09 * H, cx + 0.17 * W, y0 + 0.47 * H], j)),
        OTTER["belly"], 4)
    # 手臂（以肩为轴旋转）
    for side, s in (("left", -1), ("right", 1)):
        ang = _arm_angle(pose, phase, side)
        sx, sy = cx + s * 0.22 * W, y0 + 0.10 * H
        L, T = 0.24 * H, 0.085 * W
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).rounded_rectangle(_wobble(rng, [sx - T / 2, sy - T * 0.3, sx + T / 2, sy + L], j),
                                            radius=T / 2, fill=255)
        m = m.rotate(s * ang, resample=Image.BICUBIC, center=(sx, sy))
        put(m, OTTER["fur"], 5)
    # 头
    nod = {"nod": [0, 0.02, 0.035, 0.015][phase % 4]}.get(pose, 0) * H
    hy = y0 - 0.25 * H + nod
    for s in (-1, 1):  # 耳朵
        ex = cx + s * 0.2 * W
        put(ellipse_mask(W, H, _wobble(rng, [ex - 0.06 * W, hy + 0.01 * H, ex + 0.06 * W, hy + 0.09 * H], j)),
            OTTER["fur_dark"], 6)
    put(ellipse_mask(W, H, _wobble(rng, [cx - 0.27 * W, hy + 0.02 * H, cx + 0.27 * W, hy + 0.31 * H], j)),
        OTTER["fur"], 7)
    put(ellipse_mask(W, H, _wobble(rng, [cx - 0.14 * W, hy + 0.15 * H, cx + 0.14 * W, hy + 0.29 * H], j)),
        OTTER["belly"], 8)
    put(ellipse_mask(W, H, _wobble(rng, [cx - 0.05 * W, hy + 0.155 * H, cx + 0.05 * W, hy + 0.205 * H], j * 0.5)),
        OTTER["nose"], 9)
    for s in (-1, 1):
        put(ellipse_mask(W, H, [cx + s * 0.19 * W - 0.045 * W, hy + 0.19 * H, cx + s * 0.19 * W + 0.045 * W,
                                hy + 0.23 * H]), OTTER["cheek"], 10)
    d = ImageDraw.Draw(canvas)
    blink = pose == "listen" and phase % 4 == 2
    for s in (-1, 1):
        ex, ey = cx + s * 0.11 * W, hy + 0.12 * H
        r = 0.032 * W
        if blink:
            d.arc([ex - r, ey - r * 0.6, ex + r, ey + r * 0.6], 20, 160, fill=OTTER["eye"], width=int(r * 0.4))
        else:
            d.ellipse([ex - r, ey - r * 1.1, ex + r, ey + r * 1.1], fill=OTTER["eye"])
            d.ellipse([ex - r * 0.2, ey - r * 0.75, ex + r * 0.45, ey - r * 0.1], fill=(255, 255, 255))
    # 嘴
    mouth_open = pose in ("wave", "jump", "clap") and phase % 2 == 1
    my = hy + 0.225 * H
    if mouth_open:
        d.ellipse([cx - 0.035 * W, my - 0.005 * H, cx + 0.035 * W, my + 0.04 * H], fill=(120, 40, 40))
    else:
        d.arc([cx - 0.05 * W, my - 0.03 * H, cx, my + 0.01 * H], 20, 160, fill=OTTER["nose"], width=4)
        d.arc([cx, my - 0.03 * H, cx + 0.05 * W, my + 0.01 * H], 20, 160, fill=OTTER["nose"], width=4)
    # 胡须
    for s in (-1, 1):
        for k in (-1, 0, 1):
            x1 = cx + s * 0.09 * W
            d.line([x1, my - 0.02 * H + k * 0.012 * H, x1 + s * 0.13 * W, my - 0.03 * H + k * 0.025 * H],
                   fill=(90, 60, 45), width=3)
    # 接触阴影
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([cx - 0.3 * W, 0.93 * H, cx + 0.3 * W, 0.99 * H],
                                   fill=(60, 30, 10, int(110 * (1 + lift / H * 4))))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    shadow.alpha_composite(canvas)
    return shadow


# ---------------------------------------------------------------- 物体
@lru_cache(maxsize=128)
def object_sprite(theme: str, word: str, hex_color: str | None, count: int | None, variant: int,
                  size: int = 460) -> Image.Image:
    W = H = size
    rng = random.Random(zlib.crc32(f'{word}|{variant}'.encode()))
    j = size * 0.008
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    color = hex_rgb(hex_color) if hex_color else (230, 120, 80)
    palette = [(224, 65, 47), (47, 111, 224), (244, 197, 49), (63, 163, 77), (240, 138, 36), (138, 79, 196)]
    if theme == "numbers" and count:
        cols = min(count, 5 if count > 4 else count)
        rows = math.ceil(count / cols)
        cell = min(W / cols, H / rows, W * 0.6) * 0.9
        for i in range(count):
            r_, c_ = divmod(i, cols)
            x = W / 2 + (c_ - (cols - 1) / 2) * cell
            y = H / 2 + (r_ - (rows - 1) / 2) * cell
            box = _wobble(rng, [x - cell * 0.42, y - cell * 0.42, x + cell * 0.42, y + cell * 0.42], j)
            canvas.alpha_composite(clay_fill(ellipse_mask(W, H, box), palette[i % len(palette)], i))
        return canvas
    body = ellipse_mask(W, H, _wobble(rng, [W * 0.12, H * 0.14, W * 0.88, H * 0.9], j))
    canvas.alpha_composite(clay_fill(body, color, variant))
    d = ImageDraw.Draw(canvas)
    if theme == "fruits":
        leaf = ellipse_mask(W, H, [W * 0.5, H * 0.02, W * 0.72, H * 0.2], -30)
        canvas.alpha_composite(clay_fill(leaf, (80, 160, 70), 3))
    elif theme == "animals":
        for s in (-1, 1):
            ear = ellipse_mask(W, H, [W * (0.5 + s * 0.27) - W * 0.1, H * 0.06, W * (0.5 + s * 0.27) + W * 0.1,
                                      H * 0.3])
            canvas.alpha_composite(clay_fill(ear, color, 4))
        canvas.alpha_composite(clay_fill(body, color, variant))
        for s in (-1, 1):
            ex = W * (0.5 + s * 0.14)
            d.ellipse([ex - 14, H * 0.45 - 16, ex + 14, H * 0.45 + 16], fill=(30, 24, 22))
        d.ellipse([W * 0.46, H * 0.56, W * 0.54, H * 0.61], fill=(60, 40, 35))
    else:  # colors：顶上一个小“颜料滴”
        drop = ellipse_mask(W, H, _wobble(rng, [W * 0.38, H * 0.0, W * 0.52, H * 0.16], j))
        canvas.alpha_composite(clay_fill(drop, color, 6))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([W * 0.18, H * 0.86, W * 0.82, H * 0.97], fill=(60, 30, 10, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    shadow.alpha_composite(canvas)
    return shadow


# ---------------------------------------------------------------- 背景
@lru_cache(maxsize=4)
def background(w: int, h: int, theme: str) -> Image.Image:
    top = np.array([252, 236, 205], np.float32)
    bot = np.array([246, 214, 170], np.float32)
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    grad = top * (1 - t) + bot * t
    img = np.repeat(grad, w, axis=1)
    img += _noise(w, h, 4)[..., None] * 0.2
    bg = Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    ground_y = int(h * 0.62) if h > w else int(h * 0.72)
    gm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gm).rounded_rectangle([-40, ground_y, w + 40, h + 80], radius=120, fill=255)
    bg.alpha_composite(clay_fill(gm, (196, 222, 160), 2))
    u = min(w, h)
    top = h * 0.13 if h > w else h * 0.03
    sun = ellipse_mask(w, h, [w - u * 0.22, top, w - u * 0.05, top + u * 0.17])
    bg.alpha_composite(clay_fill(sun, (255, 196, 60), 3).point(lambda v: min(255, int(v * 1.15))))
    rng = random.Random(7)
    for k in range(2):
        cx, cy = (w * (0.16 + 0.42 * k), top + u * (0.05 + 0.04 * k)) if h > w else (w * (0.08 + 0.2 * k), top + u * (0.07 + 0.03 * k))
        cm = Image.new("L", (w, h), 0)
        dr = ImageDraw.Draw(cm)
        for i in range(3):
            r = u * rng.uniform(0.045, 0.07)
            ox = cx + (i - 1) * r * 1.2
            dr.ellipse([ox - r, cy - r, ox + r, cy + r], fill=255)
        bg.alpha_composite(clay_fill(cm, (255, 255, 255), 5 + k, light=(-0.2, -0.3)).point(lambda v: min(255, int(v * 1.12))))
    return bg
