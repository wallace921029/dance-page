"""把 samples/*.pdf 渲染成 WebP 页面图，用于调整拆页参数（长边、质量）时对比效果。

用法（在 backend/ 下）：
    uv run scripts/render_samples.py [--long-edge 2048] [--quality 80] [--no-trim]

输出：
    samples/rendered/index.json            所有绘本的清单
    samples/rendered/{book_id}/0000.webp   页面大图
    samples/rendered/{book_id}/cover.webp  书架小封面
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.books.render import (  # noqa: E402
    PAGE_LONG_EDGE,
    WEBP_QUALITY,
    make_cover,
    page_file_name,
    render_pdf,
)

ROOT = BACKEND_DIR.parent
SAMPLES_DIR = ROOT / "samples"
OUTPUT_DIR = SAMPLES_DIR / "rendered"


def book_id_for(pdf_path: Path) -> str:
    return hashlib.sha1(pdf_path.name.encode()).hexdigest()[:8]


def title_for(pdf_path: Path) -> str:
    # 网上下载的文件名常带 "(作者) (来源站点)" 之类的后缀，由内向外去掉括号部分
    title = pdf_path.stem
    while (stripped := re.sub(r"\s*[(（][^()（）]*[)）]", "", title)) != title:
        title = stripped
    return title.strip() or pdf_path.stem


def render_book(pdf_path: Path, long_edge: int, quality: int, trim: bool) -> dict:
    book_id = book_id_for(pdf_path)
    out_dir = OUTPUT_DIR / book_id
    if out_dir.exists():
        shutil.rmtree(out_dir)

    started = time.perf_counter()
    result = render_pdf(pdf_path, out_dir, long_edge=long_edge, quality=quality, trim=trim)
    assert result is not None
    make_cover(out_dir / page_file_name(0), out_dir / "cover.webp")
    elapsed = time.perf_counter() - started

    sizes = [(out_dir / page_file_name(i)).stat().st_size for i in range(len(result.pages))]
    total_bytes = sum(sizes)
    first = result.pages[0]
    print(f"《{title_for(pdf_path)}》 → {out_dir.relative_to(ROOT)}")
    print(
        f"  页数 {len(result.pages)}，版式 {result.orientation}，"
        f"页面尺寸 {first.width}×{first.height}"
    )
    print("  裁白边（左上右下）" + " / ".join(f"{r:.1%}" for r in result.trim))
    spread = result.spread_start_page
    print(f"  跨页配对 {f'从第 {spread} 页开始' if spread else '无法判断'}")
    print(
        f"  PDF {pdf_path.stat().st_size / 1e6:.1f}MB → 图片合计 {total_bytes / 1e6:.1f}MB，"
        f"单页平均 {total_bytes / len(sizes) / 1e3:.0f}KB，最大 {max(sizes) / 1e3:.0f}KB"
    )
    print(f"  渲染耗时 {elapsed:.1f}s（平均 {elapsed / len(sizes):.2f}s / 页）")

    return {
        "id": book_id,
        "title": title_for(pdf_path),
        "orientation": result.orientation,
        "spreadStartPage": spread,
        "pages": [
            {"file": page_file_name(i), "width": p.width, "height": p.height}
            for i, p in enumerate(result.pages)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--long-edge", type=int, default=PAGE_LONG_EDGE)
    parser.add_argument("--quality", type=int, default=WEBP_QUALITY)
    parser.add_argument("--no-trim", action="store_true", help="不裁白边")
    args = parser.parse_args()

    pdf_paths = sorted(SAMPLES_DIR.glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"{SAMPLES_DIR} 下没有 PDF")

    trim = "否" if args.no_trim else "是"
    print(f"参数：长边 {args.long_edge}px，WebP 质量 {args.quality}，裁白边 {trim}\n")
    books = [render_book(p, args.long_edge, args.quality, not args.no_trim) for p in pdf_paths]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "index.json").write_text(
        json.dumps({"books": books}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n清单已写入 {(OUTPUT_DIR / 'index.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
