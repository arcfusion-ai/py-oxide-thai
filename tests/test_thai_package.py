"""Exercise the installed fork wheel; no reference extractors are required."""

import asyncio
import importlib.metadata

import py_oxide_thai
import pytest

from tools.thai_fixtures import make_mark_font, make_pdf


@pytest.mark.parametrize("mark", list("ัิีึืฺุู็่้๊๋์ํ๎"))
def test_installed_package_preserves_positioned_marks(tmp_path, mark):
    path = tmp_path / "positioned.pdf"
    make_pdf(path, [("ก", 72, 720), (mark, 72, 724), ("ต", 81.6, 720)])
    expected = f"ก{mark}ต"
    with py_oxide_thai.PdfDocument(str(path)) as document:
        assert expected in document.extract_text(0)
        assert expected in document.extract_text(0)  # repeat through the span cache
        assert any(expected in line.text for line in document.extract_text_lines(0))


def test_distribution_has_independent_identity():
    assert py_oxide_thai.__version__ == importlib.metadata.version("py-oxide-thai")
    assert py_oxide_thai.UPSTREAM_VERSION == "0.3.78"
    assert py_oxide_thai.PdfDocument.__module__ == "py_oxide_thai._native"
    requirements = importlib.metadata.requires("py-oxide-thai") or []
    assert not any("pymupdf" in r.lower() or "pdf-oxide" in r.lower() for r in requirements)


def test_installed_package_uses_ink_bounds(tmp_path):
    path = tmp_path / "bearing.pdf"
    make_pdf(path, [("กต", 72, 720), ("ิ", 81.6, 724)], make_mark_font())
    with py_oxide_thai.PdfDocument(str(path)) as document:
        assert "กิต" in document.extract_text(0)


def test_async_wrapper_uses_the_fork(tmp_path):
    path = tmp_path / "async.pdf"
    make_pdf(path, [("ก", 72, 720), ("ิ", 72, 724)])

    async def extract():
        async with await py_oxide_thai.AsyncPdfDocument.open(str(path)) as document:
            return await document.extract_text(0)

    assert "กิ" in asyncio.run(extract())
