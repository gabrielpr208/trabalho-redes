import config
import random
import logging
import argparse
from logger import setup_logging
from prompt_toolkit.patch_stdout import patch_stdout

config.MY_NAME = input("Digite seu name: ")
config.MY_NAMESPACE = input("Digite seu namespace: ")
config.MY_PEER_ID = f"{config.MY_NAME}@{config.MY_NAMESPACE}"
config.MY_LISTEN_PORT = 50000 + random.randint(0, 9999)

import asyncio
from p2pClient import P2PClient

parser = argparse.ArgumentParser(description="P2P Chat")

parser.add_argument(
    "--log-mode",
    choices=["console", "file", "both"],
    default="console",
    help="Where to write logs: console, file, or both (default: console).",
)
parser.add_argument(
    "--log-file",
    default="server.log",
    help="Log file path when using modes 'file' or 'both' (default: server.log).",
)

parser.add_argument(
    "--log-level",
    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    default="INFO",
    help="Host/IP for the rendezvous server (default: 0.0.0.0).",
)

args = parser.parse_args()

setup_logging(args.log_mode, args.log_file, args.log_level)

log = logging.getLogger("main")
with patch_stdout():
    try:
        asyncio.run(P2PClient().start())
    except KeyboardInterrupt:
        log.info("Encerrado. Interrupção pelo teclado.")
    except Exception as e:
        log.error(f"Erro: {e}")
