"""测试用 PDF 生成工具。"""

from pathlib import Path

import numpy as np
from PIL import Image

PAGE_W, PAGE_H = 300, 400  # PDF 页面尺寸（72dpi 下即 pt）
CONTENT_H = 320  # 画面只占页面上方 80%，底部 20% 是白边


def _smooth_picture(seed: int, width: int, height: int) -> Image.Image:
    """平滑的随机彩色画面：同一幅图切开后接缝连续，不同的图之间不连续。"""
    rng = np.random.default_rng(seed)
    small = Image.fromarray(rng.integers(0, 200, (6, 8, 3), dtype=np.uint8))
    return small.resize((width, height), Image.Resampling.BICUBIC)


def _page(picture: Image.Image) -> Image.Image:
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    page.paste(picture, (0, 0))
    return page


def picture_book_pages(spreads: int = 3) -> list[Image.Image]:
    """模拟样本书：封面、封底，之后是跨页大图（按 3+4、5+6… 配对）。"""
    pages = [
        _page(_smooth_picture(1, PAGE_W, CONTENT_H)),
        _page(_smooth_picture(2, PAGE_W, CONTENT_H)),
    ]
    for i in range(spreads):
        wide = _smooth_picture(100 + i, PAGE_W * 2, CONTENT_H)
        pages.append(_page(wide.crop((0, 0, PAGE_W, CONTENT_H))))
        pages.append(_page(wide.crop((PAGE_W, 0, PAGE_W * 2, CONTENT_H))))
    return pages


def write_pdf(path: Path, pages: list[Image.Image]) -> Path:
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=72)
    return path
