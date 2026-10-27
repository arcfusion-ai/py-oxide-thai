"""Print three extractors' actual output for the README's synthetic Thai name."""

import tempfile
from pathlib import Path

from evaluate_thai import fixtures, read


def main() -> None:
    """Generate the measured fixture and compare upstream, the fork, and PyMuPDF."""
    with tempfile.TemporaryDirectory(prefix="thai-name-comparison-") as directory:
        samples = fixtures(Path(directory))
        sample = next(path for path in samples if path.stem == "stacked_name_0")
        print(f"Expected: {samples[sample]!r}")
        for engine in ("pdf_oxide", "py_oxide_thai", "pymupdf"):
            print(f"{engine}: {read(engine, sample)[0].strip()!r}")


if __name__ == "__main__":
    main()
