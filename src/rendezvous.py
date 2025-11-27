import asyncio
import json
from peerTable import PeerTable
from p2pClient import P2PClient
from config import MY_PEER_ID, RDV_IP, RDV_PORT, MY_NAME, MY_NAMESPACE, MY_LISTEN_PORT, DISCOVERY_INTERVAL
from protocolEncoder import ProtocolEncoder

class Rendezvous:
    def __init__(self, peer_table: PeerTable, p2p_client: P2PClient):
        self.peer_table = peer_table
        self.p2p_client = p2p_client
        self.running = True

    async def send_command(self, command: str, **kwargs: any):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(RDV_IP, RDV_PORT)
                timeout=5
            )
            message = ProtocolEncoder.encode(
                command,
                MY_PEER_ID,
                name=MY_NAME,
                namespace=MY_NAMESPACE,
                port=MY_LISTEN_PORT,
                **kwargs
            )
            writer.write(message)
            await writer.drain()

            response = await asyncio.wait_for(reader.readuntil('\n'), timeout=5).decode('utf-8').strip()
            
            writer.close()
            await writer.wait_closed()

            if response:
                return json.loads(response)
            return None

        except Exception as e:
            return None
    
    async def register(self):
        response = await self.send_command("REGISTER")
        if response and response.get("status") == "OK":
            print(f"[Rendezvous] Peer {MY_PEER_ID} registrado.")

    async def discover(self):
        response = await self.send_command("DISCOVER")
        if isinstance(response, list):
            await self.peer_table.update_known_peers(response)
        elif response and response.get("error"):
            print(f"[Rendezvous] Falha no discover: {response.get('error')}")

    async def reconnection(self):
        stale_peers = await self.peer_table.get_stale_peers()
        if stale_peers:
            print(f"[Router] Tentando reconexão com {len(stale_peers)} peers stale")
            for peer_id, ip, port in stale_peers:
                asyncio.create_task(self.chat_client.connect_to_peer(ip, port, peer_id))
        
    async def loop(self):
        await asyncio.sleep(1)
        while self.running:
            try:
                await self.register()
                await self.discover()
                await self.reconnection()
                await asyncio.sleep(DISCOVERY_INTERVAL)
            except Exception as e:
                await asyncio.sleep(DISCOVERY_INTERVAL)