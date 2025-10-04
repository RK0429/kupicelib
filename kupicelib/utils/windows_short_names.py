# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        windows_short_names.py
# Purpose:     Functions to get the short path name of a file on Windows
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     28-03-2024
# Licence:     refer to the LICENSE file
#
# -------------------------------------------------------------------------------

from __future__ import annotations

# From
# https://stackoverflow.com/questions/23598289/how-to-get-windows-short-file-name-in-python
import sys
from collections.abc import Callable
from ctypes import create_unicode_buffer, wintypes
from os import PathLike
from typing import cast, overload

_ShortPathFunc = Callable[[str, wintypes.LPWSTR, int], wintypes.DWORD]


if sys.platform == "win32":
    from ctypes import windll

    _GetShortPathNameW: _ShortPathFunc = windll.kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _GetShortPathNameW.restype = wintypes.DWORD
else:  # pragma: no cover - not reachable on target platform

    def _GetShortPathNameW(
        long_name: str, buffer: wintypes.LPWSTR, size: int
    ) -> wintypes.DWORD:
        raise OSError("Windows short paths are only available on Windows platforms")

# GetShortPathName is first called without a destination buffer so it can report
# the required size. Allocate a buffer with that length and call it again. If a
# TOCTTOU race still produces a larger result, increase the buffer size and
# retry until the call succeeds.


@overload
def get_short_path_name(long_name: str) -> str:
    ...


@overload
def get_short_path_name(long_name: PathLike[str]) -> str:
    ...


def get_short_path_name(long_name: str | PathLike[str]) -> str:
    """Return the Windows short (8.3) path for ``long_name``.

    The implementation follows the pattern described in
    http://stackoverflow.com/a/23598461/200291 and repeatedly retries with a buffer of
    sufficient capacity.
    """

    long_name_str = str(long_name)
    output_buffer_size = 0
    while True:
        output_buffer = create_unicode_buffer(output_buffer_size)
        needed = int(
            _GetShortPathNameW(
                long_name_str,
                cast(wintypes.LPWSTR, output_buffer),
                output_buffer_size,
            )
        )
        if output_buffer_size >= needed:
            return output_buffer.value
        output_buffer_size = needed
