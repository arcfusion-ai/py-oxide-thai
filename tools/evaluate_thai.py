"""Compare the fork, upstream, PyMuPDF, and PDFium on an external PDF corpus.

Only hashes, summary metrics, and synthetic strings are written to the report.
PDFs and extracted real-world text are never included in the output artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

from thai_fixtures import make_mark_font, make_pdf


# PyMuPDF 2's optional layout model is irrelevant to text-layer evaluation.
sys.modules.setdefault("pymupdf.layout", None)

MARKS = "ัิีึืฺุู็่้๊๋์ํ๎"
ORPHAN = re.compile(rf"(?:^|\s)[{MARKS}]", re.M)
NAMES = re.compile(r"(?:นางสาว|นาย|นาง)[^\n]{4,100}")


def fixtures(directory: Path) -> dict[Path, str]:
    cases = {
        "raised_vowel_tone": (
            [("ก", 72, 720), ("ิ", 73, 723), ("่", 72, 726), ("ติ", 81.6, 720)],
            "กิ่ติ",
        ),
        "left_shifted": ([("ก", 72, 720), ("ิ", 70, 720), ("่", 69, 720), ("ติ", 81.6, 720)], "กิ่ติ"),
        "lower_vowel": ([("ศ", 72, 720), ("ุ", 72, 716), ("ภ", 81.6, 720)], "ศุภ"),
        "decomposed_sara_am": (
            [("น", 72, 720), ("้", 72, 724), ("ํ", 72, 727), ("า", 81.6, 720)],
            "น้ํา",
        ),
        "inside_body_run": ([("กต", 72, 720), ("ิ", 72, 724), ("่", 72, 727)], "กิ่ต"),
        "inline_spaces": ([("กิ่ติ ศุภ", 72, 720)], "กิ่ติ ศุภ"),
    }
    for mark in MARKS:
        cases[f"mark_{ord(mark):04x}"] = (
            [("ก", 72, 720), (mark, 72, 724), ("ต", 81.6, 720)],
            f"ก{mark}ต",
        )
    result = {}
    for name, (runs, expected) in cases.items():
        path = directory / f"{name}.pdf"
        make_pdf(path, runs)
        result[path] = expected
    path = directory / "negative_side_bearing.pdf"
    make_pdf(path, [("กต", 72, 720), ("ิ", 81.6, 724)], make_mark_font())
    result[path] = "กิต"
    for i, name in enumerate(
        [
            "นายกิตติศักดิ์ ชื่นบาน",
            "นางสาวศุภณัฐ พึ่งพร",
            "นายเกรียงศักดิ์ ศรีสุข",
        ]
    ):
        runs = []
        x, base_x = 72.0, 72.0
        for c in name:
            if c in MARKS:
                runs.append((c, base_x, 724 if c not in "ฺุู" else 716))
            else:
                runs.append((c, x, 720))
                base_x = x
                x += 9.6
        path = directory / f"stacked_name_{i}.pdf"
        make_pdf(path, runs)
        result[path] = name
    return result


def read(engine: str, path: Path) -> list[str]:
    if engine in ("pdf_oxide", "py_oxide_thai"):
        module = __import__(engine)
        with module.PdfDocument(str(path)) as doc:
            return [doc.extract_text(i) for i in range(int(doc.page_count()))]
    if engine == "pymupdf":
        import pymupdf

        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                raise ValueError("password required")
            return [page.get_text() for page in doc]
    import pypdfium2

    with pypdfium2.PdfDocument(path) as doc:
        texts = []
        for i in range(len(doc)):
            page = doc[i]
            text_page = page.get_textpage()
            try:
                texts.append(text_page.get_text_bounded())
            finally:
                text_page.close()
                page.close()
        return texts


def extract(engine: str, paths: list[Path]) -> tuple[dict[str, list[str]], dict[str, str]]:
    texts, errors = {}, {}
    for path in paths:
        try:
            texts[path.name] = read(engine, path)
        except Exception as exc:
            errors[path.name] = type(exc).__name__
    return texts, errors


def jaccard(a: str, b: str) -> float:
    left, right = set(a.split()), set(b.split())
    return len(left & right) / len(left | right) if left or right else 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    paths = sorted(args.corpus.glob("*.pdf"))
    if not paths or len({p.name for p in paths}) != len(paths):
        parser.error("corpus must contain PDFs with unique filenames")
    engines = ["pdf_oxide", "py_oxide_thai", "pymupdf", "pypdfium2"]
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "corpus_documents": len(paths),
        "corpus": [
            {"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths
        ],
        "engines": {},
    }
    extracted = {}
    failures = {}
    for engine in engines:
        print(f"Extracting {engine}...", flush=True)
        extracted[engine], failures[engine] = extract(engine, paths)
    shared = set.intersection(*(set(docs) for docs in extracted.values()))
    successful = [p for p in paths if p.name in shared]
    if not successful:
        raise RuntimeError("no documents succeeded in every engine; cannot compare performance")
    with tempfile.TemporaryDirectory(prefix="thai-marks-") as temp:
        synthetic = fixtures(Path(temp))
        for engine in engines:
            print(f"Evaluating {engine}...", flush=True)
            texts, errors = extracted[engine], failures[engine]
            times = []
            # Fresh document objects every repeat; opening is included. Import,
            # fixture creation, and quality analysis are outside the timer.
            for _ in range(args.repeats):
                start = time.perf_counter()
                for path in successful:
                    read(engine, path)
                times.append(time.perf_counter() - start)
            pages = sum(len(v) for v in texts.values())
            timed_pages = sum(len(texts[p.name]) for p in successful)
            all_text = "\n".join(t for ts in texts.values() for t in ts)
            checks = {}
            for path, expected in synthetic.items():
                try:
                    actual = "\n".join(read(engine, path))
                    checks[path.stem] = {
                        "expected": expected,
                        "actual": actual,
                        "passed": expected in actual,
                    }
                except Exception as exc:
                    checks[path.stem] = {
                        "expected": expected,
                        "error": type(exc).__name__,
                        "passed": False,
                    }
            version = importlib.metadata.version(engine.replace("_", "-"))
            report["engines"][engine] = {
                "version": version,
                "documents": len(texts),
                "pages": pages,
                "errors": errors,
                "timed_documents": len(successful),
                "timed_pages": timed_pages,
                "seconds_per_repeat": times,
                "median_ms_per_page": statistics.median(times) * 1000 / timed_pages
                if timed_pages
                else None,
                "empty_pages": sum(not t.strip() for ts in texts.values() for t in ts),
                "thai_characters": sum("\u0e00" <= c <= "\u0e7f" for c in all_text),
                "orphan_marks": len(ORPHAN.findall(all_text)),
                "replacement_characters": all_text.count("\ufffd"),
                "synthetic_passed": sum(c["passed"] for c in checks.values()),
                "synthetic_total": len(checks),
                "synthetic": checks,
            }
    upstream, fork = extracted["pdf_oxide"], extracted["py_oxide_thai"]
    changes, scores = [], []
    for filename in sorted(upstream.keys() & fork.keys()):
        a, b = upstream[filename], fork[filename]
        if len(a) != len(b):
            raise RuntimeError(f"page count changed: {filename}")
        for i, (before, after) in enumerate(zip(a, b)):
            score = jaccard(before, after)
            scores.append(score)
            if before != after:
                changes.append(
                    {
                        "file": filename,
                        "page": i,
                        "word_jaccard": score,
                        "orphan_marks_before": len(ORPHAN.findall(before)),
                        "orphan_marks_after": len(ORPHAN.findall(after)),
                    }
                )
    report["fork_vs_upstream"] = {
        "compared_pages": len(scores),
        "changed_pages": changes,
        "minimum_word_jaccard": min(scores, default=1),
        "new_document_errors": sorted(
            set(report["engines"]["py_oxide_thai"]["errors"])
            - set(report["engines"]["pdf_oxide"]["errors"])
        ),
    }
    for engine, docs in extracted.items():
        matched = total = 0
        for filename in docs.keys() & extracted["pymupdf"].keys():
            for text, reference in zip(docs[filename], extracted["pymupdf"][filename]):
                names = NAMES.findall(reference)
                compact = "".join(text.split())
                total += len(names)
                matched += sum("".join(name.split()) in compact for name in names)
        report["engines"][engine]["pymupdf_name_sequences_matched"] = matched
        report["engines"][engine]["pymupdf_name_sequences_total"] = total
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "fork_vs_upstream": report["fork_vs_upstream"],
                "engines": {
                    e: {k: v for k, v in r.items() if k not in {"synthetic", "errors"}}
                    for e, r in report["engines"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
