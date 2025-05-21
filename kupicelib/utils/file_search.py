# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        file_search.py
# Purpose:     Tools for searching files on libraries
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     28-03-2024
# Licence:     refer to the LICENSE file
#
# -------------------------------------------------------------------------------
import logging
import os
import zipfile
from typing import Optional

__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2021, Fribourg Switzerland"

_logger = logging.getLogger("kupicelib.Utils")


def find_file_in_directory(directory: str, filename: str) -> Optional[str]:
    """Searches for a file with the given filename in the specified directory and its
    subdirectories.

    The search is case-insensitive, but the returned path preserves the case from the file system.
    If the filename includes a path component, it will be appended to the directory.

    Args:
        directory: The root directory to start the search from
        filename: The name of the file to search for (can include path components)

    Returns:
        The full path to the found file, or None if the file was not found

    Example:
        >>> find_file_in_directory("/path/to/search", "config.txt")
        '/path/to/search/subfolder/Config.txt'
    """
    # First check whether there is a path tagged to the filename
    path, filename = os.path.split(filename)
    if path != "":
        directory = os.path.join(directory, path)
    for root, dirs, files in os.walk(directory):
        # match case insensitive, but store the file system's file name, as the
        # file system may be case sensitive
        for filefound in files:
            if filename.lower() == filefound.lower():
                return os.path.join(root, filefound)
    return None


def search_file_in_containers(filename: str, *containers: str) -> Optional[str]:
    """Searches for a file with the given filename in the specified containers.

    Containers can be directories or zip files. For zip files, the matching file will be
    extracted to a temporary directory "./spice_lib_temp" and the path to the extracted file
    will be returned.

    The search is case-insensitive, but the returned path preserves the case from the file system.

    Args:
        filename: File name to search (posix string)
        *containers: Variable list of paths to search in (directories or zip files)

    Returns:
        Path to the file if found, or None if not found

    Example:
        >>> search_file_in_containers("model.lib", "/path/to/libs", "/path/to/archive.zip")
        '/path/to/libs/models/Model.lib'
    """
    for container in containers:
        _logger.debug(f"Searching for '{filename}' in '{container}'")
        if os.path.exists(container):  # Skipping invalid paths
            if container.endswith(".zip"):
                # Search in zip files
                with zipfile.ZipFile(container, "r") as zip_ref:
                    files = zip_ref.namelist()
                    for filefound in files:
                        # match case insensitive, but store the file system's file name,
                        # as the file system may be case sensitive
                        if filename.lower() == filefound.lower():
                            temp_dir = os.path.join(".", "spice_lib_temp")
                            if not os.path.exists(temp_dir):
                                os.makedirs(temp_dir)
                            _logger.debug(
                                f"Found. Extracting '{filefound}' from the zip file to '{temp_dir}'"
                            )
                            return zip_ref.extract(filefound, path=temp_dir)
            else:
                filefound_opt: Optional[str] = find_file_in_directory(
                    container, filename
                )
                if filefound_opt is not None:
                    _logger.debug(f"Found '{filefound_opt}'")
                    return filefound_opt
    _logger.debug(f"Searching for '{filename}': NOT Found")
    return None
