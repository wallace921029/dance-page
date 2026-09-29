"""PDF 拆页：渲染为 WebP 页面图，并自动裁白边、判断版式、检测跨页配对。

Worker 和 scripts/render_samples.py 共用。
"""

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

PAGE_LONG_EDGE = 2048
COVER_LONG_EDGE = 480
WEBP_QUALITY = 80

# 裁白边：低分辨率扫描一遍，找出整本书所有页面内容区域的并集，全书统一裁切（D42）
TRIM_SCAN_LONG_EDGE = 800
TRIM_WHITE_THRESHOLD = 240  # 灰度 >= 此值视为白色
TRIM_MIN_FRACTION = 0.01  # 某一边空白不足 1% 就不裁

# 跨页检测：比较相邻两页接缝处的像素（D43）
SEAM_COLUMNS = 3
SEAM_MIN_CONTENT_ROWS = 0.2  # 接缝两侧都几乎是白色的配对不参与判断
SEAM_CONFIDENCE_RATIO = 1.5  # 两种配对方式的接缝色差需相差这么多倍才下结论


class PdfOpenError(Exception):
    """PDF 无法打开，message 为给管理员看的中文原因。"""


@dataclass
class RenderedPage:
    width: int
    height: int


@dataclass
class RenderResult:
    pages: list[RenderedPage]
    orientation: str  # 'portrait' | 'landscape'
    # 跨页大图从第几页（从 1 开始）开始两两配对：2 表示 2+3、4+5…；3 表示 3+4、5+6…；None 为无法判断
    spread_start_page: int | None
    # 裁掉的比例 (left, top, right, bottom)
    trim: tuple[float, float, float, float]


def page_file_name(index: int) -> str:
    return f"{index:04d}.webp"


def open_pdf(pdf_path: Path) -> pdfium.PdfDocument:
    try:
        pdf = pdfium.PdfDocument(pdf_path)
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            raise PdfOpenError("PDF 已加密（需要密码），无法处理") from e
        raise PdfOpenError("PDF 文件已损坏或格式不受支持") from e
    if len(pdf) == 0:
        pdf.close()
        raise PdfOpenError("PDF 中没有页面")
    return pdf


def find_trim(pdf: pdfium.PdfDocument) -> tuple[float, float, float, float]:
    """返回整本书统一的裁切比例 (left, top, right, bottom)，均为占页面宽/高的比例。"""
    left, top, right, bottom = 1.0, 1.0, 0.0, 0.0
    for index in range(len(pdf)):
        page = pdf[index]
        scale = TRIM_SCAN_LONG_EDGE / max(page.get_size())
        gray = np.asarray(page.render(scale=scale, grayscale=True).to_pil().convert("L"))
        page.close()
        rows = np.flatnonzero((gray < TRIM_WHITE_THRESHOLD).any(axis=1))
        cols = np.flatnonzero((gray < TRIM_WHITE_THRESHOLD).any(axis=0))
        if rows.size == 0:  # 空白页
            continue
        # 边界向内取整：宁可裁掉内容边缘的一个扫描像素，也不在满版插画边上留白线
        h, w = gray.shape
        left = min(left, (cols[0] + 1) / w)
        right = max(right, cols[-1] / w)
        top = min(top, (rows[0] + 1) / h)
        bottom = max(bottom, rows[-1] / h)
    if right <= left:
        return 0.0, 0.0, 0.0, 0.0

    def margin(blank: float) -> float:
        return blank if blank >= TRIM_MIN_FRACTION else 0.0

    return margin(left), margin(top), margin(1 - right), margin(1 - bottom)


def _seam_score(right_strip: np.ndarray, left_strip: np.ndarray) -> float | None:
    """两页接缝处的平均色差；越小越像同一幅跨页大图。"""
    if right_strip.shape != left_strip.shape:
        return None
    right, left = right_strip.mean(axis=1), left_strip.mean(axis=1)
    content = (right.min(axis=1) < TRIM_WHITE_THRESHOLD) | (left.min(axis=1) < TRIM_WHITE_THRESHOLD)
    if content.mean() < SEAM_MIN_CONTENT_ROWS:
        return None
    return float(np.abs(right - left).mean(axis=1)[content].mean())


def detect_spread_start_page(strips: list[tuple[np.ndarray, np.ndarray]]) -> int | None:
    """strips 为每页的 (左边缘, 右边缘) 像素条。

    比较每对相邻页的接缝色差，按页码（从 1 开始）分成两组：
    2+3、4+5… 一组，3+4、5+6…（以及 1+2）一组。色差明显更小的一组就是跨页配对方式。
    """
    scores: dict[int, list[float]] = {2: [], 3: []}
    for i in range(len(strips) - 1):
        score = _seam_score(strips[i][1], strips[i + 1][0])
        if score is not None:
            # 从 0 开始的 i 为奇数 → 1 开始的页码 i+1 与 i+2，即 2+3、4+5…
            scores[2 if i % 2 == 1 else 3].append(score)
    if not scores[2] or not scores[3]:
        return None
    medians = {k: statistics.median(v) for k, v in scores.items()}
    low, high = sorted(medians, key=medians.get)
    return low if medians[high] > medians[low] * SEAM_CONFIDENCE_RATIO else None


def render_pdf(
    pdf_path: Path,
    pages_dir: Path,
    *,
    long_edge: int = PAGE_LONG_EDGE,
    quality: int = WEBP_QUALITY,
    trim: bool = True,
    on_progress: Callable[[int, int], bool] | None = None,
) -> RenderResult | None:
    """把 PDF 每页渲染为 pages_dir/NNNN.webp。

    on_progress(已完成页数, 总页数) 在开始时和每页完成后调用，返回 False 则中止并返回 None。
    """
    pdf = open_pdf(pdf_path)
    pages: list[RenderedPage] = []
    strips: list[tuple[np.ndarray, np.ndarray]] = []
    try:
        total = len(pdf)
        if on_progress is not None and on_progress(0, total) is False:
            return None
        trim_ratio = find_trim(pdf) if trim else (0.0, 0.0, 0.0, 0.0)
        pages_dir.mkdir(parents=True, exist_ok=True)
        for index in range(total):
            page = pdf[index]
            width_pt, height_pt = page.get_size()
            t_left, t_top, t_right, t_bottom = trim_ratio
            crop = (width_pt * t_left, height_pt * t_bottom, width_pt * t_right, height_pt * t_top)
            content_w = width_pt - crop[0] - crop[2]
            content_h = height_pt - crop[1] - crop[3]
            scale = long_edge / max(content_w, content_h)
            image = page.render(scale=scale, crop=crop).to_pil()
            page.close()

            rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
            # 必须 copy：切片只是视图，会让整页 float32 数组（约 35MB）一直留在内存里，
            # 整本书累积会撑爆内存
            strips.append((rgb[:, :SEAM_COLUMNS].copy(), rgb[:, -SEAM_COLUMNS:].copy()))
            image.save(pages_dir / page_file_name(index), "WEBP", quality=quality)
            pages.append(RenderedPage(image.width, image.height))

            if on_progress is not None and on_progress(index + 1, total) is False:
                return None
    finally:
        pdf.close()

    # 按多数页面的宽高比判断整本书的版式
    landscape_pages = sum(1 for p in pages if p.width > p.height)
    orientation = "landscape" if landscape_pages > len(pages) / 2 else "portrait"
    return RenderResult(
        pages=pages,
        orientation=orientation,
        spread_start_page=detect_spread_start_page(strips),
        trim=trim_ratio,
    )


def make_cover(page_image: Path, cover_path: Path, quality: int = WEBP_QUALITY) -> None:
    """用某一页的页面图生成书架用的小封面。"""
    with Image.open(page_image) as image:
        cover = image.copy()
    cover.thumbnail((COVER_LONG_EDGE, COVER_LONG_EDGE))
    tmp = cover_path.with_suffix(".tmp.webp")
    cover.save(tmp, "WEBP", quality=quality)
    tmp.replace(cover_path)
