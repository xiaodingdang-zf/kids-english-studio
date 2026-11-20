"""8 种材质的程序化质感处理（mock 渲染用）。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from . import felt


def apply_material(style_id: str, im: Image.Image, seed: int = 0) -> Image.Image:
    """对 RGBA 图像叠加对应材质纹理，保持透明通道不变。"""
    if style_id == "clay":
        return im
    if style_id == "felt":
        return felt.texture(im, seed)
    arr = np.asarray(im, np.float32)
    h, w = arr.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    if style_id == "papercraft":
        # 细微纸张纤维 + 轻微亮度提升
        delta = np.sin(xx * 0.8 + yy * 0.4) * 2.5 + 4.0
    elif style_id == "tin":
        # 金属高光条带
        diag = (xx + yy) / max(1, w + h)
        delta = (np.exp(-((diag - 0.35) * 9) ** 2) * 26.0 - 4.0)
    elif style_id == "cardboard":
        # 瓦楞纸横纹 + 偏暖牛皮纸调
        delta = np.sin(yy * 0.55) * 8.0
        arr[..., 0] = np.clip(arr[..., 0] * 1.03 + 6, 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] * 0.92, 0, 255)
    elif style_id == "wood":
        # 柔和木纹
        delta = np.sin(yy * 0.18 + np.sin(xx * 0.04) * 2.5) * 9.0
        arr[..., 0] = np.clip(arr[..., 0] * 1.04, 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] * 0.90, 0, 255)
    elif style_id == "crochet":
        # 针织网格颗粒
        delta = (np.sin(xx * 0.6) * np.sin(yy * 0.6)) * 11.0
    elif style_id == "fabric":
        # 平纹棉布经纬线
        delta = (np.sin(xx * 0.9) + np.sin(yy * 0.9)) * 4.5
    else:
        return im
    rgb = np.clip(arr[..., :3] + delta[..., None], 0, 255)
    out = np.dstack([rgb, arr[..., 3]]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")
