#!/usr/bin/env python

"""Helper script to insert validated code snippets into README.md."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from shutil import copyfile

IN_STATEMENT_REGEX = re.compile(r"-- in (?P<path>.*?)(?P<loc>\s\[.*\])?\s*$")


def _iter_python_blocks(lines: list[str]) -> Iterable[tuple[int, int]]:
    """Yield ``(start, end)`` indices for Python code blocks within *lines*."""

    block_start = -1
    for index, line in enumerate(lines):
        if "```python" in line:
            block_start = index
        elif "```" in line and block_start != -1:
            yield block_start, index
            block_start = -1


def _extract_localized_lines(include_text: list[str], localization: str | None) -> list[str]:
    """Return the portion of *include_text* referenced by *localization* if present."""

    if localization is None:
        return include_text

    loc_text = localization[2:-1]  # Remove leading " [" and trailing "]"
    start_tag = f"-- Start of {loc_text} --"
    end_tag = f"-- End of {loc_text} --"
    lines_to_plug: list[str] = []
    include_indent = -1
    for line in include_text:
        if start_tag in line:
            include_indent = line.find("#")
            continue
        if end_tag in line:
            include_indent = -1
            continue
        if include_indent >= 0:
            if include_indent >= len(line):
                lines_to_plug.append("")
            else:
                lines_to_plug.append(line[include_indent:])
    return lines_to_plug


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv)
    if len(args) != 2:
        print("Usage: readme_update.py README.md")
        return 1

    filename = Path(args[1])
    print(f'Reading "{filename}"', end="...")
    try:
        readme_md = filename.read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        print("File not found")
        return 1
    except OSError as exc:
        print(f"Error reading file: {exc}")
        return 1
    print(f"{len(readme_md)} lines read")

    for block_start, block_end in _iter_python_blocks(readme_md):
        include_match = None
        for lookahead in (block_end + 1, block_end + 2):
            if lookahead < len(readme_md):
                include_match = IN_STATEMENT_REGEX.search(readme_md[lookahead])
                if include_match:
                    break
        if not include_match:
            continue

        include_relpath = include_match.group("path")
        include_path = Path(os.curdir, include_relpath).resolve()
        include_text = include_path.read_text(encoding="utf-8").splitlines(keepends=False)
        lines_to_plug = _extract_localized_lines(include_text, include_match.group("loc"))

        print(f"Updating code on lines {block_start + 1}:{block_end + 1}")
        existing_lines = block_end - (block_start + 1)
        readme_md[block_start + 1:block_end] = [f"{line}\n" for line in lines_to_plug]
        new_lines = len(lines_to_plug)
        line_delta = new_lines - existing_lines
        block_end += line_delta

    backup_filename = filename.with_suffix(".bak")
    print(f"Creating backup {backup_filename}")
    copyfile(filename, backup_filename)
    print(f"Writing {len(readme_md)} lines to {filename}")
    filename.write_text("".join(readme_md), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
