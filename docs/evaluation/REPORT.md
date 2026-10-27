# Thai extraction evaluation — 2026-10-27

Py Oxide Thai **0.3.78.post1** fixes separately positioned Thai combining
glyphs in the Rust extraction engine. All **26 synthetic cases passed**,
versus 1/26 for upstream 0.3.78. The fork preserved all **20,670 name-like
Unicode sequences** found by the evaluator in the PyMuPDF reference output.
Upstream already preserved those sequences in this real-document sample too.

The results support this specific fix, not a claim that every Thai PDF is
correctly extracted. **PyMuPDF was faster on this corpus.**

## Corpus and method

- 125 PDFs, 2,485 pages: 60 cached MSBIS parliamentary PDFs, 40 cached LIS
  parliamentary PDFs, and 25 existing upstream fixtures covering other scripts,
  images/scans, rotation, forms, and malformed/encrypted inputs.
- Sources: [MSBIS](https://msbis.parliament.go.th/ewtadmin/ewt/parliament_report/),
  [LIS](https://lis.parliament.go.th/index/), and the upstream repository at
  `ad49c4cb3638dc950a29350ef882161372fde473`.
- The real PDFs remain external to the fork. SHA-256 hashes and filenames are
  recorded in [results.json](results.json); no real extracted text is published.
- 26 small synthetic PDFs are generated in code with original rectangular
  TrueType glyphs, ToUnicode maps, and explicit CID-to-GID maps. Cases cover all
  16 Thai nonspacing marks, raised/lowered/left-shifted glyphs, an interior mark
  in a multi-character run, decomposed sara am, negative side bearings, explicit
  spaces, and three complete synthetic Thai names. These are extraction and
  geometry fixtures, not a visual Thai typography benchmark.
- Performance uses the **same 124 successfully opened documents / 2,484 pages**
  for every engine. One password-protected fixture is excluded from timing
  because PyMuPDF and PDFium refuse it without a password; upstream and the fork
  accept it but cannot extract its encrypted content. This inherited behavior
  was not changed.
- Three timed passes per engine; median wall time divided by timed page count.
  Every document is reopened each pass. Opening and text extraction are included;
  imports, fixture construction, OCR, rendering, and quality analysis are excluded.
- Python 3.13.4 on macOS ARM64; local runs, not an isolated benchmark machine.
  PyMuPDF's optional layout model is disabled. Defaults differ between engines
  in table/layout reconstruction, so timings apply to these specific API calls.

## Results

| Engine | Version | Synthetic cases | Median ms/page |
| --- | --- | ---: | ---: |
| Py Oxide Thai | 0.3.78.post1 | **26/26** | 2.334 |
| pdf_oxide | 0.3.78 | 1/26 | 2.284 |
| PyMuPDF | 2.0 | 24/26 | **1.566** |
| pypdfium2 | 5.14.0 | 1/26 | 3.339 |

The fork's measured overhead versus upstream is about **2.2%**. Do not carry
forward upstream's general speed claims as results for this fork or corpus.
PyMuPDF's two synthetic failures involve a mark inside an already emitted body
run and the negative-side-bearing case; this does not establish superiority on
arbitrary documents.

Across the real corpus, the fork and upstream extracted the same 2,128,421 Thai
characters, with the same 705 empty pages and no new extraction errors. Both
matched 20,670/20,670 name-like sequences from PyMuPDF after whitespace removal.
This is a reference-agreement metric based on a regex, not a human-labelled
name accuracy score; the synthetic name cases supply the targeted regression.

The fork changed 19 pages in four LIS documents. Reviewed examples include
`หนา ๑้` → `หน้า ๑`, a detached tone reunited as `เล่ม`, `ท้องถิน่` →
`ท้องถิ่น`, `สถาบนัวจยิั` → `สถาบันวิจัย`, and `ไปรษณีย` plus a detached mark
→ `ไปรษณีย์`. One affected document already has a corrupted mixed Latin/Thai
mapping; its mark relocation does not repair the underlying mapping.

The whitespace-adjacent orphan-mark count fell from 267 to 263 (PyMuPDF: 4;
PDFium: 502). This detector also counts fragmented watermarks and damaged text
layers, and is not a complete measure of Thai correctness. Residual defects
remain. The fix does not address missing mappings, legacy PUA glyphs, OCR,
general table layout, or rotated/vertical Thai runs.

## Regression evidence

Upstream `main` and the latest release, `v0.3.78`, were the **same commit** at
evaluation time. [Baseline signatures](baseline-signatures.tsv) and
[fork signatures](fork-signatures.tsv) were produced by `corpus_sig` on all 125
documents. The baseline binary was optimized; the fork signature binary used
the debug profile. Performance figures above use the optimized Python wheel.

Only the four intended documents changed their text hashes. Maximum extracted
word length and page rotations were unchanged in every document. Three removed
characters were whitespace separators around relocated marks. Per-page
word-Jaccard scores and orphan-mark deltas are recorded in `results.json`;
changed pages were inspected rather than treating a changed signature as an
automatic regression or improvement.

Local validation:

- 8,687 Rust unit/integration tests passed; 46 inherited tests ignored.
- 142 doctests passed; 222 inherited doctests ignored. Two doctests initially
  encountered a linker collision while different feature builds shared the
  target directory; the isolated sequential doctest rerun passed.
- Eight focused PDF regression tests passed with default features and with
  `rendering`; the original stacking tests and the ink-bound test fail upstream.
- Three scope/mark-set tests cover all 16 marks, font/structure/artifact/color
  separation, and rotated/vertical runs.
- 19 tests passed against the installed Python wheel, including async access,
  package identity, every Thai mark, and negative side bearings.
- A clean environment installed only the fork wheel and extracted Thai;
  PyMuPDF, upstream pdf_oxide, and PDFium were absent.
- Rust formatting, Python lint/format checks, and Clippy passed, with
  `clippy::nonminimal_bool` explicitly allowed. The same single Clippy warning
  was reproduced on unchanged upstream with Rust 1.95; it is unrelated to the
  Thai fix. FIPS/ML-specific suites were not run locally.

## Reproduce

Build and install the fork in an evaluation environment, then install the
reference packages separately:

```sh
python -m pip install .
python -m pip install 'pdf-oxide==0.3.78' 'pymupdf==2.0' 'pypdfium2==5.14.0' 'fonttools==4.67.0'
python tools/evaluate_thai.py --corpus /path/to/flat-pdf-corpus --output results.json
cargo test --test test_thai_mark_attachment
cargo test --lib thai_
cargo test --doc
cargo test --features rendering --test test_thai_mark_attachment
```

Keep Cargo feature builds sequential when sharing a target directory. Supply
the PDFs listed in the manifest and verify their SHA-256 hashes before comparing
results. The reference extractors and fontTools are evaluation dependencies;
the distributed fork has no runtime dependency on them.
