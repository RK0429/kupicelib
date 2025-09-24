
# Convenience direct imports
from .editor.asc_editor import AscEditor
from .editor.qsch_editor import QschEditor
from .editor.spice_editor import SpiceCircuit, SpiceComponent, SpiceEditor
from .raw.raw_read import RawRead, SpiceReadException
from .raw.raw_write import RawWrite, Trace
from .sim.sim_runner import SimRunner

# Define public API to avoid unused import errors
__all__ = [
    "AscEditor",
    "QschEditor",
    "RawRead",
    "RawWrite",
    "SimRunner",
    "SpiceCircuit",
    "SpiceComponent",
    "SpiceEditor",
    "SpiceReadException",
    "Trace",
    "add_log_handler",
    "all_loggers",
    "set_log_level",
]


def all_loggers():
    """Returns all the name strings used as logger identifiers.

    :return: A List of strings which contains all the logger's names used in this
        library.
    :rtype: list[str]
    """
    return [
        "kupicelib.AscEditor",
        "kupicelib.AscToQsch",
        "kupicelib.AsyReader",
        "kupicelib.BaseEditor",
        "kupicelib.BaseSchematic",
        "kupicelib.LTSpiceSimulator",
        "kupicelib.LTSteps",
        "kupicelib.NGSpiceSimulator",
        "kupicelib.QschEditor",
        "kupicelib.qspice_log_reader",
        "kupicelib.QSpiceSimulator",
        "kupicelib.RawRead",
        "kupicelib.RunTask",
        "kupicelib.ServerSimRunner",
        "kupicelib.SimAnalysis",
        "kupicelib.SimClient",
        "kupicelib.SimRunner",
        "kupicelib.SimServer",
        "kupicelib.SimStepper",
        "kupicelib.Simulator",
        "kupicelib.SpiceEditor",
        "kupicelib.Utils",
        "kupicelib.XYCESimulator",
    ]


def set_log_level(level):
    """Sets the logging level for all loggers used in the library.

    :param level: The logging level to be used, eg. logging.ERROR, logging.DEBUG, etc.
    :type level: int
    """
    import logging

    for logger in all_loggers():
        logging.getLogger(logger).setLevel(level)


def add_log_handler(handler):
    """Sets the logging handler for all loggers used in the library.

    :param handler: The logging handler to be used, eg. logging.NullHandler
    :type handler: Handler
    """
    import logging

    for logger in all_loggers():
        logging.getLogger(logger).addHandler(handler)
