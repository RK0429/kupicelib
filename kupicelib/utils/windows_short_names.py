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

# From
# https://stackoverflow.com/questions/23598289/how-to-get-windows-short-file-name-in-python
import ctypes
from ctypes import wintypes

_GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
_GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
_GetShortPathNameW.restype = wintypes.DWORD

# GetShortPathName is first called without a destination buffer so it can report
# the required size. Allocate a buffer with that length and call it again. If a
# TOCTTOU race still produces a larger result, increase the buffer size and
# retry until the call succeeds.


def get_short_path_name(long_name):
    """Gets the short path name of a given long path.

    http://stackoverflow.com/a/23598461/200291
    """
    output_buf_size = 0
    while True:
        output_buf = ctypes.create_unicode_buffer(output_buf_size)
        needed = _GetShortPathNameW(long_name, output_buf, output_buf_size)
        if output_buf_size >= needed:
            return output_buf.value
        else:
            output_buf_size = needed
