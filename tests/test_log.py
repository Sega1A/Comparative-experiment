import logging

from common.log import LOG_FORMAT, setup_logging


def test_setup_logging_uses_standard_format_on_stdout(capsys):
    root = logging.getLogger()
    previous = (root.handlers[:], root.level)
    try:
        setup_logging("DEBUG")
        logging.getLogger("demo").info("hello %s", "world")
        out = capsys.readouterr().out
    finally:
        root.handlers[:] = previous[0]
        root.setLevel(previous[1])

    assert "INFO     demo: hello world" in out
    assert LOG_FORMAT.startswith("%(asctime)s")


def test_setup_logging_respects_level(capsys):
    root = logging.getLogger()
    previous = (root.handlers[:], root.level)
    try:
        setup_logging("WARNING")
        logging.getLogger("demo").info("hidden")
        logging.getLogger("demo").warning("shown")
        out = capsys.readouterr().out
    finally:
        root.handlers[:] = previous[0]
        root.setLevel(previous[1])

    assert "hidden" not in out
    assert "shown" in out
