#!/usr/bin/env python
from __future__ import annotations

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        asc_to_qsch.py
# Purpose:     Convert an ASC file to a QSCH schematic
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     16-02-2024
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
import argparse
import logging
import os
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

from kupicelib.editor.asc_editor import AscEditor
from kupicelib.editor.asy_reader import AsyReader
from kupicelib.editor.base_schematic import BaseSchematic, ERotation
from kupicelib.editor.qsch_editor import QschEditor, QschTag
from kupicelib.utils.file_search import find_file_in_directory

_logger = logging.getLogger("kupicelib.AscToQsch")

SymbolStock = dict[str, QschTag]


def main() -> None:
    """Parse command line arguments and run the converter."""

    parser = argparse.ArgumentParser(
        description=(
            "Convert an LTspice ASC schematic to a QSPICE QSCH schematic while "
            "optionally providing additional symbol search paths."
        )
    )
    parser.add_argument("asc_file", type=Path, help="Path to the source ASC schematic")
    parser.add_argument(
        "qsch_file",
        nargs="?",
        type=Path,
        help="Optional output QSCH file path. Defaults to the ASC stem.",
    )
    parser.add_argument(
        "-a",
        "--add",
        dest="additional_paths",
        action="append",
        default=[],
        type=str,
        help="Additional directories to search when resolving symbols.",
    )

    args = parser.parse_args()

    asc_file: Path = args.asc_file
    qsch_file: Path = args.qsch_file or asc_file.with_suffix(".qsch")
    search_paths: list[str] = [str(path) for path in args.additional_paths]

    print(f"Using {qsch_file} as output file")
    convert_asc_to_qsch(asc_file, qsch_file, search_paths)


def convert_asc_to_qsch(
    asc_file: str | Path,
    qsch_file: str | Path,
    search_paths: Sequence[str] | None = None,
) -> None:
    """Convert an LTspice ASC schematic into a QSPICE QSCH schematic."""

    asc_path = Path(asc_file)
    qsch_path = Path(qsch_file)
    search_path_list: list[str] = list(search_paths) if search_paths is not None else []

    symbol_stock: SymbolStock = {}
    asc_editor = AscEditor(asc_path)

    # Import the conversion data from xml file located alongside this script
    parent_dir = Path(__file__).resolve().parent
    xml_file = parent_dir / "asc_to_qsch_data.xml"
    conversion_data = ET.parse(xml_file)

    root = conversion_data.getroot()

    offset = root.find("offset")
    if offset is None:
        raise ValueError("Conversion data XML missing <offset> element")
    offset_x_text = offset.get("x")
    offset_y_text = offset.get("y")
    if offset_x_text is None or offset_y_text is None:
        raise ValueError("Offset element must include x and y attributes")
    offset_x = float(offset_x_text)
    offset_y = float(offset_y_text)

    scale = root.find("scaling")
    if scale is None:
        raise ValueError("Conversion data XML missing <scaling> element")
    scale_x_text = scale.get("x")
    scale_y_text = scale.get("y")
    if scale_x_text is None or scale_y_text is None:
        raise ValueError("Scaling element must include x and y attributes")
    scale_x = float(scale_x_text)
    scale_y = float(scale_y_text)

    asc_editor.scale(
        offset_x=offset_x,
        offset_y=offset_y,
        scale_x=scale_x,
        scale_y=scale_y,
    )

    candidate_roots: list[str] = [
        *search_path_list,
        str(asc_path.parent),
        os.path.expanduser("~/AppData/Local/LTspice/lib/sym"),
        os.path.expanduser("~/Documents/LtspiceXVII/lib/sym"),
    ]

    for comp in asc_editor.components.values():
        symbol_key = comp.symbol
        if not symbol_key:
            continue
        symbol_tag: QschTag | None = symbol_stock.get(symbol_key)
        if symbol_tag is None:
            print(f"Searching for symbol {symbol_key}...")
            for sym_root in candidate_roots:
                print(f"   {os.path.abspath(sym_root)}")
                if not os.path.exists(sym_root):
                    continue
                if sym_root.endswith(".zip"):
                    continue
                symbol_asc_file = find_file_in_directory(sym_root, symbol_key + ".asy")
                if symbol_asc_file is None:
                    continue
                print(f"Found {symbol_asc_file}")
                symbol_asc = AsyReader(symbol_asc_file)
                value_attr = comp.attributes.get("Value", "<val>")
                symbol_tag = symbol_asc.to_qsch(
                    comp.reference,
                    str(value_attr),
                )
                symbol_stock[symbol_key] = symbol_tag
                break

        rotation_value = int(comp.rotation) % 360
        if rotation_value == 90:
            comp.rotation = ERotation.R270
        elif rotation_value == 270:
            comp.rotation = ERotation.R90

        if symbol_tag is not None:
            comp.attributes["symbol"] = symbol_tag

    qsch_editor = QschEditor(str(qsch_path), create_blank=True)
    source_schematic: BaseSchematic = asc_editor
    BaseSchematic.copy_from(qsch_editor, source_schematic)
    qsch_editor.save_netlist(qsch_path)

    print(f"File {asc_path} converted to {qsch_path}")


if __name__ == "__main__":
    main()
    exit(0)
