from prompt_toolkit.patch_stdout import StdoutProxy
import logging
from pathlib import Path


class PromptToolkitHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.proxy = StdoutProxy()

    def emit(self, record):
        msg = self.format(record)
        try:
            self.proxy.write(msg + "\n")
        except Exception:
            pass


def setup_logging(mode: str, logfile: str | None, loglevel=logging.INFO):
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(loglevel)

    fmt = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")

    handlers = []
    if mode in ("console", "both"):
        ch = PromptToolkitHandler()
        ch.setFormatter(fmt)
        handlers.append(ch)

    if mode in ("file", "both"):
        if not logfile:
            logfile = "server.log"
        Path(logfile).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(logfile, mode="a", encoding="utf-8")
        fh.setFormatter(fmt)
        handlers.append(fh)

    for h in handlers:
        root.addHandler(h)
