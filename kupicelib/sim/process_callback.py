#!/usr/bin/env python

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        process_callback.py
# Purpose:     Being able to execute callback in a separate process
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-04-2023
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""Process-based callback helper."""
from __future__ import annotations

from multiprocessing import Process, Queue
from pathlib import Path


class ProcessCallback(Process):
    """Wrapper for the callback function."""

    def __init__(
        self,
        raw: Path,
        log: Path,
        group: None = None,
        name: str | None = None,
        *,
        daemon: bool | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(group=group, name=name, daemon=daemon)
        self.queue: Queue[object] = Queue()
        self.raw_file: Path = raw
        self.log_file: Path = log
        self.kwargs: dict[str, object] = dict(kwargs)

    def run(self) -> None:
        ret = self.callback(self.raw_file, self.log_file, **self.kwargs)
        if ret is None:
            ret = "Callback doesn't return anything"
        self.queue.put(ret)

    @staticmethod
    def callback(raw_file: Path, log_file: Path, **kwargs: object) -> object:
        """This function needs to be overriden."""
        ...
