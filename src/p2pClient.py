import asyncio
import sys
from typing import Tuple
from peerTable import PeerTable
from config import MY_LISTEN_IP, MY_LISTEN_PORT, MY_PEER_ID
from protocolEncoder import ProtocolEncoder

class P2PClient:
    def __init__(self):
        self.peer_table = PeerTable()
        self.server: asyncio.Server | None = None
        self.running = True
    
    async def start_listening_server(self):
        try:
            self.server = await asyncio.start_server(
                self.handle_connection,
                MY_LISTEN_IP,
                MY_LISTEN_PORT
            )
            listening_address = self.server.sockets[0].getsockname()

            print(f"[PeerServer] Escutando conexões de Peers em {listening_address}")

            await self.server.serve_forever()
        except OSError as e:
            if 'Address already in use' in str(e):
                print(f"[FATAL] A porta {MY_LISTEN_PORT} já está em uso. Tente outra porta.")
            else:
                print(f"[FATAL] Falha ao iniciar servidor local: {e}")
            self.running = False
            sys.exit(1)
        except Exception as e:
             if self.running:
                 print(f"[PeerServer] Erro no servidor de escuta: {e}")

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer_address = writer.get_extra_info('peername')
        if peer_address:
            print(f"[PeerServer] Conexão de entrada de {peer_address}")
            try:
                await self.handle_handshake(reader, writer, peer_address)
            except Exception as e:
                print(f"[-] Handshake falhou com {peer_address}: {e}")
                writer.close()
                await writer.wait_closed()
                return
        
        await self.read_loop(reader, writer)

        writer.close()
        await writer.wait_closed()
        self.peer_table.remove_peer(peer_address)

    async def handle_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer_address: Tuple[str, int]):
        data = await asyncio.wait_for(reader.readuntil(b'\n'), timeout=5)
        message = ProtocolEncoder.decode(data)

        if message.get("type") != "HELLO":
            raise ValueError(f"Comando inválido: {message.get('type')}")
        
        peer_id = message.get("peer_id")

        print(f"[Handshake] Recebido HELLO de {peer_id} em {peer_address}")

        hello_ok = ProtocolEncoder.encode("HELLO_OK", MY_PEER_ID, version="1.0", features=["ack"])
        writer.write(hello_ok)
        await writer.drain()

        await self.peer_table.add_active_peer(peer_id, writer)

    async def connect_to_peer(self, ip: str, port: int):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=5
            )
            print(f"[Router] Enviando HELLO para {ip}:{port}...")
            hello = ProtocolEncoder.encode("HELLO", MY_PEER_ID, version="1.0", features=["ack"])
            writer.write(hello)
            await writer.drain()

            response = await asyncio.wait_for(reader.readuntil(b'\n'), timeout=5)
            message = ProtocolEncoder.decode(response)

            if message.get("type") != "HELLO_OK":
                raise ValueError(f"Resposta HELLO_OK inválida ou ausente: {message.get('type')}")
            
            peer_id = message.get('peer_id')
            await self.peer_table.add_active_peer(peer_id, writer)
            asyncio.create_task(self.read_loop(reader, writer))
            print(f"[Router] Conectado e ativo com: {peer_id}")
            return True
        except asyncio.TimeoutError:
            print(f"[-] Falha de conexão/handshake (Timeout) com {ip}:{port}")
            return False
        except Exception as e:
            print(f"[-] Falha ao conectar: {e}")
            return False
    
    async def start(self):
        self.running = True
        server_task = asyncio.create_task(self.start_listening_server())
        await self.start_background_tasks()
        await server_task

    async def start_background_tasks(self):
        print("[Client] Iniciando tarefas de background (Rendezvous e CLI")
        await asyncio.sleep(2)
        print("\n--- Teste de Conexão (Para rodar 2 clientes localmente) ---")
        await self.connect_to_peer(MY_LISTEN_IP, 50001)
        while self.running:
            await asyncio.sleep(1)
