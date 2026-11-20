"""Chroma-key cutout and equal-canvas sprite-sheet slicing."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


EXPRESSIONS = ("happy", "surprised", "curious", "proud")


def cutout(image: Image.Image, key: str = "green", crop: bool = True, pad: int = 12) -> Image.Image:
    pixels = np.asarray(image.convert("RGBA")).astype(np.int16)
    r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    if key == "magenta":
        other = np.maximum(r, b) - g
        keyed = (np.minimum(r, b) > 120) & (np.minimum(r, b) > g * 1.6)
        spill = (np.minimum(r, b) > g) & ~keyed
        pixels[..., 0] = np.where(spill, np.minimum(r, g + other // 3), r)
        pixels[..., 2] = np.where(spill, np.minimum(b, g + other // 3), b)
    else:
        keyed = (g > 100) & (g > r * 1.3) & (g > b * 1.3)
        spill = (g > np.maximum(r, b)) & ~keyed
        pixels[..., 1] = np.where(spill, np.maximum(r, b), g)
    alpha = Image.fromarray(np.where(keyed, 0, 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    pixels[..., 3] = np.asarray(alpha)
    out = Image.fromarray(pixels.clip(0, 255).astype(np.uint8), "RGBA")
    if crop:
        bbox = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
        if bbox:
            out = out.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                            min(out.width, bbox[2] + pad), min(out.height, bbox[3] + pad)))
    return out


def slice_sheet(sheet: Path, grid: str, out_dir: Path, names: list[str] | None = None) -> list[Path]:
    try:
        rows, cols = map(int, grid.lower().split("x"))
    except ValueError as exc:
        raise ValueError("--grid 应为 2x4 或 2x2") from exc
    if (rows, cols) not in ((2, 4), (2, 2)):
        raise ValueError("--grid 只支持 2x4 动作表或 2x2 近景表")
    if names is not None and len(names) != rows * cols:
        raise ValueError("文件名数量与网格格数不符")
    with Image.open(sheet) as source:
        image = source.convert("RGBA")
    if image.width % cols or image.height % rows:
        raise ValueError("动作表尺寸必须能被网格整除")
    cw, ch = image.width // cols, image.height // rows
    sprites = [cutout(image.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)), pad=0)
               for r in range(rows) for c in range(cols)]
    if any(sprite.getchannel("A").getbbox() is None for sprite in sprites):
        raise ValueError("动作表包含空格，请检查绿幕与网格")
    width = max(sprite.width for sprite in sprites) + 24
    height = max(sprite.height for sprite in sprites) + 24
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, sprite in enumerate(sprites):
        canvas = Image.new("RGBA", (width, height))
        canvas.alpha_composite(sprite, ((width - sprite.width) // 2, height - 12 - sprite.height))
        path = out_dir / (names[i] if names else f"{i:03d}.png")
        canvas.save(path)
        paths.append(path)
    return paths
