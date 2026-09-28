import pytest
from PIL import Image

from app.books.render import PdfOpenError, make_cover, page_file_name, render_pdf
from tests.pdfs import CONTENT_H, PAGE_W, picture_book_pages, write_pdf


def test_render_trims_white_margin_and_detects_spreads(tmp_path):
    pdf = write_pdf(tmp_path / "book.pdf", picture_book_pages(spreads=3))
    result = render_pdf(pdf, tmp_path / "pages", long_edge=600)

    assert result is not None
    assert len(result.pages) == 8
    # 底部 20% 白边被裁掉，页面比例变成画面本身的比例
    page = result.pages[0]
    assert max(page.width, page.height) == 600
    assert page.width / page.height == pytest.approx(PAGE_W / CONTENT_H, abs=0.02)
    assert result.trim[3] == pytest.approx(0.2, abs=0.01)
    assert result.orientation == "portrait"
    assert result.spread_start_page == 3
    for i in range(8):
        assert (tmp_path / "pages" / page_file_name(i)).is_file()


def test_render_without_trim(tmp_path):
    pdf = write_pdf(tmp_path / "book.pdf", picture_book_pages(spreads=1))
    result = render_pdf(pdf, tmp_path / "pages", long_edge=400, trim=False)
    assert result is not None
    assert (result.pages[0].width, result.pages[0].height) == (300, 400)


def test_landscape_book(tmp_path):
    pages = [Image.new("RGB", (400, 300), color) for color in ("red", "green", "blue")]
    result = render_pdf(write_pdf(tmp_path / "b.pdf", pages), tmp_path / "pages", long_edge=400)
    assert result is not None
    assert result.orientation == "landscape"
    # 纯色页没有可比较的跨页接缝
    assert result.spread_start_page is None


def test_progress_callback_can_abort(tmp_path):
    pdf = write_pdf(tmp_path / "book.pdf", picture_book_pages(spreads=2))
    calls = []

    def on_progress(done, total):
        calls.append((done, total))
        return done < 2

    assert render_pdf(pdf, tmp_path / "pages", long_edge=300, on_progress=on_progress) is None
    assert calls == [(0, 6), (1, 6), (2, 6)]


def test_corrupt_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4\nnot really a pdf")
    with pytest.raises(PdfOpenError, match="损坏"):
        render_pdf(bad, tmp_path / "pages")


def test_make_cover(tmp_path):
    Image.new("RGB", (1000, 2000), "red").save(tmp_path / "page.webp")
    make_cover(tmp_path / "page.webp", tmp_path / "cover.webp")
    with Image.open(tmp_path / "cover.webp") as cover:
        assert cover.size == (240, 480)
