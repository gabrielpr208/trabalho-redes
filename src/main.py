import config
import random
config.MY_NAME = input("Digite seu name: ")
config.MY_NAMESPACE = input("Digite seu namespace: ")
config.MY_PEER_ID = f"{config.MY_NAME}@{config.MY_NAMESPACE}"
config.MY_LISTEN_PORT = 50000 + random.randint(0, 9999)

import asyncio
from p2pClient import P2PClient

try:
    asyncio.run(P2PClient().start())
except KeyboardInterrupt:
    print("\nEncerrado")
except Exception as e:
    print(f"Erro: {e}")