import asyncio
from p2pClient import P2PClient

try:
    asyncio.run(P2PClient().start())
except KeyboardInterrupt:
    print("Encerrado")
except Exception as e:
    print(f"Erro: {e}")