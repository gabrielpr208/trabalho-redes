import asyncio
import sys
import uuid
from typing import Tuple, Dict
from peerConnection import PeerConnection
from peerTable import PeerTable
from config import MY_LISTEN_IP, MY_LISTEN_PORT, MY_PEER_ID
from protocolEncoder import ProtocolEncoder
from rendezvous import Rendezvous
from cli import Cli

class P2PClient:
    def __init__(self):
        self.peer_table = PeerTable()
        self.rdv_client = Rendezvous(self.peer_table, self)
        self.cli = Cli()
        self.server: asyncio.Server = None
        self.running = True
        self.rdv_task: asyncio.Task = None
        self.cli_task: asyncio.Task = None
        self.connection_handlers: Dict[str, PeerConnection] = {} 

    async def start(self):
        self.running = True
        self.server_task = asyncio.create_task(self.chat_client.start_listening_server())
        self.rdv_task = asyncio.create_task(self.rdv_client.loop())
        self.cli_task = asyncio.create_task(self.cli.run())

        print("[Client] Iniciando Loop Rendezvous e CLI...")
        await asyncio.gather(self.server_task, self.rdv_task, self.cli_task)
    
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

    async def send_message(self, dst_peer_id: str, message: str):
        writer = await self.peer_table.get_writer(dst_peer_id)
        if not writer:
            print(f"Peer {dst_peer_id} não encontrado. Use /peers para atualizar")
            return
        msg_id = str(uuid.uuid4())

        msg = ProtocolEncoder.encode(
            "SEND",
            MY_PEER_ID,
            msg_id=msg_id,
            dst=dst_peer_id,
            payload=message,
            require_ack=True
        )

        ack = await self.peer_table.create_ack(msg_id)

        try:
            writer.write(msg)
            await writer.drain()
            print(f"[Router] Enviando mensagem para {dst_peer_id}. Aguardando ACK...")
        except asyncio.TimeoutError:
            print(f"[-] Timeout: ACK não recebido")
        except Exception as e:
            print(f"Erro no envio de mensagem para {dst_peer_id}: {e}")
            await self.peer_table.remove_peer(dst_peer_id)

    async def pub_message(self, dst: str, message: str):
        active_peers = await self.peer_table.get_active_peers()

        if not active_peers:
            print(f"[Router] Não há peers ativos no momento.")
            return
        
        msg = ProtocolEncoder.encode(
            "PUB",
            MY_PEER_ID,
            msg_id=str(uuid.uuid4()),
            dst=dst,
            payload=message,
            require_ack=False
        )

        for peer_id in active_peers:
            writer = await self.peer_table.get_writer(peer_id)
            if writer:
                try:
                    writer.write(msg)
                    await writer.drain()
                except:
                    await self.peer_table.remove_peer(peer_id)
        
        print(f"[Router] PUB enviado para {dst}")

    async def print_active_connecions(self):
        active_peers = await self.peer_table.get_active_peers()
        print("--- Conexões ativas ---")
        if not active_peers:
            print("Não há conexões ativas no momento")
            return
        
        for pid, ip, port in active_peers:
            print(f"{pid} ({ip}:{port}) | Status: ATIVO")
        print("----------------------")

    async def print_rtt(self):
        active_peers = await self.peer_table.get_active_peers()
        print(f"--- RTT Médio (ms) ---")
        if not active_peers:
            print("Não há conexões ativas no momento")
            return
        
        for pid in active_peers:
            rtt = await self.peer_table.mean_rtt(pid)
            if rtt > 0:
                print(f"{pid}: {rtt:.2f} ms")
            else:
                print(f"{pid}: Sem dados de RTT")
        print("------------------------")
    
    async def quit(self):
        print("[Client] Encerrando chat P2P. Enviando BYE para peers ativos...")
        self.running = False
        self.rdv_client.running = False

        for peer_id, handler in list(self.connection_handlers.items()):
            bye_msg = ProtocolEncoder.encode(
                "BYE",
                MY_PEER_ID,
                msg_id=str(uuid.uuid4()),
                src=MY_PEER_ID,
                dst=peer_id,
                reason="Encerrando sessão"
            )
            
            handler.writer.write(bye_msg)
            await handler.writer.drain()

            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()

            if self.server:
                self.server.close()
            print("[Client] Encerrando...")
