# Py Oxide Thai

An independent ArcFusion fork of [PDFOxide](https://github.com/yfedoseev/pdf_oxide),
based on upstream **v0.3.78** (`ad49c4cb3638dc950a29350ef882161372fde473`).
This is not the official PDFOxide project and is not endorsed by its maintainer.

The Python distribution is **`py-oxide-thai`**; import **`py_oxide_thai`**.
The Rust engine attaches separately positioned Thai vowel and tone glyphs to
their consonants **before** sorting spans into reading order. This preserves
clusters such as `กิ่ติ`, `ศุภ`, and decomposed `น้ํา` that upstream can reorder
or split onto a separate line. Existing Unicode mappings and explicit spaces
are preserved. No dictionary, OCR service, or PyMuPDF fallback is used.

## Thai extraction: upstream vs this fork vs PyMuPDF

The same generated PDF contains **`นายกิตติศักดิ์ ชื่นบาน`**, with its vowels
and tone marks positioned as separate glyphs. These are actual outputs from
the evaluator, with leading/trailing whitespace removed:

| Library | Extracted Thai name |
| --- | --- |
| Original `pdf_oxide` 0.3.78 | `นายกตตศกด ชนบาน ิิัิ์ื่` |
| **`py_oxide_thai` 0.3.78.post1** | **`นายกิตติศักดิ์ ชื่นบาน`** |
| PyMuPDF 2.0 | `นายกิตติศักดิ์ ชื่นบาน` |

Upstream moves the marks to the end of the name. This fork keeps them with
their consonants, matching PyMuPDF on this case. The PDF is a synthetic
extraction fixture with original rectangular glyphs and Unicode mappings;
it is not a screenshot or a real person's document.

Compare all three readers on your own PDF:

```python
import pdf_oxide
import py_oxide_thai
import pymupdf

path = "thai-name.pdf"

for label, reader in [
    ("Original pdf_oxide", pdf_oxide.PdfDocument),
    ("Py Oxide Thai", py_oxide_thai.PdfDocument),
]:
    with reader(path) as document:
        print(f"{label}: {document.extract_text(0).strip()!r}")

with pymupdf.open(path) as document:
    print(f"PyMuPDF: {document[0].get_text().strip()!r}")
```

To reproduce the exact generated example from this checkout, install the fork
and the comparison tools in an evaluation environment:

```sh
pip install .
pip install 'pdf-oxide==0.3.78' 'pymupdf==2.0' 'fonttools==4.67.0'
python tools/compare_thai.py
```

Across **26 targeted Thai fixtures**, this fork passed **26/26**, upstream
`pdf_oxide` passed **1/26**, and PyMuPDF passed **24/26**. On the separate
125-PDF corpus, both this fork and upstream preserved all 20,670 sampled
name-like sequences. These fixture counts describe the tested defect classes,
not universal PDF extraction accuracy.

Median extraction time on the same timed corpus was **2.33 ms/page** for this
fork, **2.28 ms/page** for upstream, and **1.57 ms/page** for PyMuPDF. PyMuPDF
was faster here; the demonstrated improvement is Thai mark attachment over
upstream. See [the full evaluation](docs/evaluation/REPORT.md).

## Install

From a checkout (requires Rust 1.88+, a C compiler, and Python 3.9+):

```sh
pip install .
```

Or install directly from GitHub:

```sh
pip install 'git+https://github.com/arcfusion-ai/py-oxide-thai.git@v0.3.78.post1'
```

Prebuilt wheels, when available, are attached to the GitHub release.

```python
from py_oxide_thai import PdfDocument

with PdfDocument("thai.pdf") as document:
    text = document.extract_text(0)
    lines = document.extract_text_lines(0)
```

The upstream Python API is retained under the new import name, including the
async wrappers. `__version__` identifies this distribution; `UPSTREAM_VERSION`
identifies the engine baseline. The upstream Rust crate name and other language
bindings are retained as internal source compatibility; this fork distributes
the renamed Python package only.

## Evaluation and limits

See [the evaluation report](docs/evaluation/REPORT.md) for measured quality,
performance, corpus provenance, and validation commands. Regression fixtures
are generated from code; no new third-party PDFs are committed.

This fix targets **horizontal, separately positioned Thai combining glyphs**
with a valid Unicode mapping. It does not reconstruct missing characters from
an incorrect ToUnicode map, recognize scanned pages, repair legacy private-use
glyphs, or change rotated/vertical Thai extraction. PDF reading order and table
layout remain dependent on the source document. Real-corpus agreement with
PyMuPDF is a comparison, not a guarantee of identical output on every PDF.

## Development

```sh
cargo test --test test_thai_mark_attachment
cargo test --lib thai_
cargo fmt --check
maturin build --release
python tools/evaluate_thai.py --corpus /path/to/corpus --output results.json
```

The evaluator requires this wheel plus `pdf-oxide==0.3.78`, `pymupdf`,
`pypdfium2`, and `fonttools` in a separate evaluation environment. They are **not runtime
dependencies** of this package.

## License and provenance

The code retains the upstream **MIT OR Apache-2.0** license, copyright notices,
and vendored component licenses; see [LICENSE-MIT](LICENSE-MIT),
[LICENSE-APACHE](LICENSE-APACHE), and [NOTICE](NOTICE). Original authorship is
preserved in Git history. Upstream branding, documentation, and additional
language bindings remain available in [the archived README](README.upstream.md).

The Thai changes were developed with Codex assistance. Report fork-specific
problems to [this repository](https://github.com/arcfusion-ai/py-oxide-thai/issues).
