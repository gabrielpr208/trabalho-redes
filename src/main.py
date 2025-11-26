import asyncio
from p2pClient import P2PClient
from config import MY_PEER_ID
from config import MY_LISTEN_PORT

try:
    print("------------------------")
    print(f"Peer id: {MY_PEER_ID}")
    print(f"Peer listen port: {MY_LISTEN_PORT}")
    print("------------------------")
    asyncio.run(P2PClient().start())
except KeyboardInterrupt:
    print("Encerrado")
except Exception as e:
    print(f"Erro: {e}")