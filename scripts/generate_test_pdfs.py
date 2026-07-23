#!/usr/bin/env python3
"""Generate deterministic, text-only resume PDFs from test_data/sources/*.txt."""

from pathlib import Path
import textwrap

import fitz


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "test_data" / "sources"
OUTPUT_DIR = ROOT / "test_data" / "generated"

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT = 54
TOP = 55
BOTTOM = 55


def line_style(line: str) -> tuple[float, float, str]:
    if line.startswith("# "):
        return 18, 25, line[2:]
    if line.startswith("## "):
        return 12, 19, line[3:].upper()
    if line.startswith("- "):
        return 10, 14, "• " + line[2:]
    return 10, 14, line


def wrapped_lines(text: str, width: int = 92):
    for raw_line in text.splitlines():
        font_size, leading, content = line_style(raw_line)
        if not content:
            yield font_size, leading, ""
            continue
        subsequent = "  " if raw_line.startswith("- ") else ""
        pieces = textwrap.wrap(
            content,
            width=width,
            subsequent_indent=subsequent,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        for piece in pieces:
            yield font_size, leading, piece


def render(source: Path, output: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    y = TOP

    for font_size, leading, line in wrapped_lines(source.read_text(encoding="utf-8")):
        if y + leading > PAGE_HEIGHT - BOTTOM:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            y = TOP
        if line:
            page.insert_text(
                (LEFT, y),
                line,
                fontsize=font_size,
                fontname="helv",
                color=(0, 0, 0),
            )
        y += leading

    document.set_metadata(
        {
            "title": source.stem,
            "author": "Synthetic ASAP project test data",
            "subject": "Synthetic resume for controlled hiring-agent experiments",
        }
    )
    document.save(output, garbage=4, deflate=True)
    document.close()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = sorted(SOURCE_DIR.glob("*.txt"))
    if not sources:
        raise SystemExit(f"No source files found in {SOURCE_DIR}")
    for source in sources:
        output = OUTPUT_DIR / f"{source.stem}.pdf"
        render(source, output)
        print(f"generated {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
