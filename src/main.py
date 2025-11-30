import config
import random
import logging
import argparse
from logger import setup_logging
from prompt_toolkit.patch_stdout import patch_stdout
import asyncio


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
    help="Logging level (default: INFO)",
)


def valid_port(value):
    port = int(value)
    if 1 <= port <= 65535:
        return port
    raise argparse.ArgumentTypeError(f"{value} is not a valid port number (1-65535) ")


parser.add_argument(
    "--port",
    type=valid_port,
    default=None,
    help="Port to listen on (1-65535, default: random)",
)

parser.add_argument(
    "--name",
    type=str,
    default=None,
    help="Peer name",
)

parser.add_argument(
    "--namespace",
    type=str,
    default=None,
    help="Peer's namespace",
)

args = parser.parse_args()

config.MY_LISTEN_PORT = args.port or 50000 + random.randint(0, 9999)
config.MY_NAME = args.name or input("Digite seu name: ")
config.MY_NAMESPACE = args.namespace or input("Digite seu namespace: ")
config.MY_PEER_ID = f"{config.MY_NAME}@{config.MY_NAMESPACE}"


setup_logging(args.log_mode, args.log_file, args.log_level)
log = logging.getLogger("main")

from p2pClient import P2PClient

with patch_stdout():
    try:
        asyncio.run(P2PClient().start())
    except KeyboardInterrupt:
        log.info("Encerrado. Interrupção pelo teclado.")
    except Exception as e:
        log.error(f"Erro: {e}")
