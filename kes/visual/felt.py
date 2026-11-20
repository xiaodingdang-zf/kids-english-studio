"""离线毛毡占位：在原创程序化形状上叠加确定性的颗粒和短绒毛。"""
from __future__ import annotations

import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from . import clay


def texture(image: Image.Image, seed: int) -> Image.Image:
    rgba = image.convert("RGBA")
    a = np.asarray(rgba).astype(np.int16)
    rng = np.random.default_rng(seed)
    grain = rng.normal(0, 9, a.shape[:2]).astype(np.int16)
    a[:, :, :3] = np.clip(a[:, :, :3] + grain[:, :, None], 0, 255)
    out = Image.fromarray(a.astype(np.uint8), "RGBA")
    fibers = Image.new("RGBA", out.size)
    draw = ImageDraw.Draw(fibers)
    random_fiber = random.Random(seed)
    count = min(2200, out.width * out.height // 450)
    for _ in range(count):
        x = random_fiber.randrange(out.width)
        y = random_fiber.randrange(out.height)
        if a[y, x, 3] < 180:
            continue
        length = random_fiber.randint(2, 7)
        base = tuple(int(v) for v in a[y, x, :3])
        color = tuple(min(255, int(v * 1.12 + 8)) for v in base) + (random_fiber.randint(55, 115),)
        draw.line((x, y, x + random_fiber.randint(-3, 3), y - length), fill=color, width=1)
    out.alpha_composite(fibers)
    out.putalpha(rgba.getchannel("A"))
    return out


@lru_cache(maxsize=256)
def otter_sprite(pose: str, phase: int, variant: int, size: int) -> Image.Image:
    return texture(clay.otter_sprite(pose, phase, variant, size), 101 + phase * 31 + variant * 7)


@lru_cache(maxsize=128)
def object_sprite(theme: str, word: str, hex_color: str | None, count: int | None, variant: int,
                  size: int) -> Image.Image:
    return texture(clay.object_sprite(theme, word, hex_color, count, variant, size), 211 + variant * 13)


@lru_cache(maxsize=4)
def background(w: int, h: int, theme: str) -> Image.Image:
    return texture(clay.background(w, h, theme), 307)
