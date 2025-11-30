import asyncio
import json
from config import (
    MY_PEER_ID,
    RDV_IP,
    RDV_PORT,
    MY_NAME,
    MY_NAMESPACE,
    MY_LISTEN_PORT,
    DISCOVERY_INTERVAL,
)
from protocolEncoder import ProtocolEncoder
import logging

log = logging.getLogger("rendezvous")


class Rendezvous:
    def __init__(self, peer_table, p2p_client):
        self.peer_table = peer_table
        self.p2p_client = p2p_client
        self.running = True

    async def send_command(self, command: str, **kwargs):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(RDV_IP, RDV_PORT), timeout=5
            )
            message = ProtocolEncoder.encode_rdv(command, **kwargs)
            writer.write(message)
            await writer.drain()

            response_bytes = await asyncio.wait_for(reader.readuntil(b"\n"), timeout=5)
            response = response_bytes.decode("utf-8").strip()

            writer.close()
            await writer.wait_closed()

            if response:
                return json.loads(response)
            return None

        except Exception as e:
            log.error(f"Erro: {e}")
            return None

    async def register(self):
        response = await self.send_command(
            "REGISTER", namespace=MY_NAMESPACE, name=MY_NAME, port=MY_LISTEN_PORT
        )
        if response and response.get("status") == "OK":
            log.debug(f"Peer {MY_PEER_ID} registrado.")
        else:
            log.error(f"Erro ao registrar o peer {MY_PEER_ID}")

    async def unregister(self):
        response = await self.send_command(
            "UNREGISTER", namespace=MY_NAMESPACE, name=MY_NAME
        )

        if response and response.get("status") == "OK":
            log.debug(f"Peer {MY_PEER_ID} removido do rendezvous.")
            self.running = False
        else:
            log.error(f"Erro ao desregistrar o peer {MY_PEER_ID}")

    async def discover(self, namespace_input: str):
        if namespace_input == "*":
            response = await self.send_command("DISCOVER")
        else:
            response = await self.send_command("DISCOVER", namespace=namespace_input)
        if isinstance(response, dict) and "peers" in response:
            peers_list = response["peers"]
            log.debug(f"Recebida lista com {len(peers_list)} peers")
            await self.peer_table.update_known_peers(peers_list)
        elif response and response.get("error") and isinstance(response, dict):
            log.error(f"Falha no discover: {response.get('error')}")

    async def reconnection(self):
        stale_peers = await self.peer_table.get_stale_peers()
        if stale_peers:
            log.debug(f"Tentando reconexão com {len(stale_peers)} peers stale")
            for peer in stale_peers:
                asyncio.create_task(
                    self.p2p_client.connect_to_peer(peer["ip"], peer["port"])
                )

    async def loop(self):
        await self.register()
        while self.running:
            try:
                await self.discover("*")
                await self.reconnection()
                await asyncio.sleep(DISCOVERY_INTERVAL)
            except:
                await asyncio.sleep(DISCOVERY_INTERVAL)

