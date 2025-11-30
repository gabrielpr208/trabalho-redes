import asyncio
import uuid
import time
from typing import Dict, Any
from protocolEncoder import ProtocolEncoder
from config import MY_PEER_ID, PING_INTERVAL
import logging

log = logging.getLogger("peer connection")


class PeerConnection:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        peer_id: str,
        p2p_client,
    ):
        self.reader = reader
        self.writer = writer
        self.peer_id = peer_id
        self.p2p_client = p2p_client
        self.running = True
        self.reading_task = None
        self.keep_alive_task = None

    async def process_command(self, message: Dict[str, Any]):
        cmd = message.get("type")

        if not cmd:
            return

        if cmd == "PING":
            pong = ProtocolEncoder.encode(
                "PONG", msg_id=message.get("msg_id"), timestamp=time.time()
            )
            self.writer.write(pong)
            await self.writer.drain()
            log.debug(f"Respondeu PONG para {self.peer_id}")

        elif cmd == "PONG":
            sent_time = float(message.get("timestamp", 0))
            rtt_ms = (time.time() - sent_time) * 1000
            await self.p2p_client.peer_table.set_rtt(self.peer_id, rtt_ms)
            log.debug(f"PONG recebido de {self.peer_id}, RTT: {rtt_ms} ms")

        elif cmd == "SEND":
            payload = message.get("payload", "")
            print(f"Recebeu mensagem de {self.peer_id}: {payload}")
            log.debug(f"Recebeu mensagem de {self.peer_id}: {payload}")
            if message.get("require_ack", False):
                ack = ProtocolEncoder.encode(
                    "ACK", msg_id=message.get("msg_id"), timestamp=time.time()
                )
                self.writer.write(ack)
                await self.writer.drain()

        elif cmd == "ACK":
            msg_id = message.get("msg_id", "???")
            log.debug(f"Mensagem {msg_id[:8]}... confirmada por {self.peer_id}")
            await self.p2p_client.peer_table.complete_ack(msg_id)

        elif cmd == "PUB":
            dst = message.get("dst")
            payload = message.get("payload", "")
            print(f"Recebeu mensagem pub para {dst} de {self.peer_id}: {payload}")
            log.debug(f"Recebeu mensagem pub para {dst} de {self.peer_id}: {payload}")

        elif cmd == "BYE":
            log.debug(f"Peer {self.peer_id} solicitou encerramento da conexão")
            bye_ok = ProtocolEncoder.encode(
                "BYE_OK", msg_id=message.get("msg_id"), src=MY_PEER_ID, dst=self.peer_id
            )
            self.writer.write(bye_ok)
            await self.writer.drain()
            await self.stop()

    async def send_ping(self):
        msg_id = str(uuid.uuid4())
        timestamp = time.time()
        ping = ProtocolEncoder.encode("PING", msg_id=msg_id, timestamp=timestamp)
        try:
            self.writer.write(ping)
            await self.writer.drain()
        except:
            await self.stop()

    async def keep_alive_loop(self):
        await asyncio.sleep(PING_INTERVAL)
        while self.running:
            try:
                await self.send_ping()
                await asyncio.sleep(PING_INTERVAL)
            except:
                break

    async def read_loop(self):
        while True:
            try:
                data = await self.reader.readuntil(b"\n")
                if not data:
                    break

                message = ProtocolEncoder.decode(data)

                if message:
                    await self.process_command(message)
            except:
                break
        await self.stop()

    def start(self):
        self.reading_task = asyncio.create_task(self.read_loop())
        self.keep_alive_task = asyncio.create_task(self.keep_alive_loop())

    async def stop(self):
        self.running = False
        if self.reading_task:
            self.reading_task.cancel()
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
        if self.p2p_client:
            await self.p2p_client.peer_table.remove_peer(self.peer_id)
        log.debug(f"Fechando conexão com {self.peer_id}...")
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass
