import asyncio
import json
import uuid
import sys
import random
import time
from typing import Dict, Any, List, Tuple, Optional
from p2pClient import P2PClient
from protocolEncoder import ProtocolEncoder
from config import MY_LISTEN_IP, MY_PEER_ID, MY_LISTEN_PORT, PING_INTERVAL

class PeerConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, peer_id: str, chat_client: P2PClient):
        self.reader = reader
        self.writer = writer
        self.peer_id = peer_id
        self.chat_client = chat_client
        self.running = True
        self.reading_task = None
        self.keep_alive_task = None

    async def process_command(self, message: Dict[str, Any]):
        cmd = message.get("type")
        source_peer_id = message.get("peer_id")

        if not cmd:
            return
        
        if cmd == "PING":
            pong = ProtocolEncoder.encode(
                "PONG",
                MY_PEER_ID,
                msg_id=message.get("msg_id"),
                timestamp=time.time()
            )
            self.writer.write(pong)
            await self.writer.drain()
            print(f"[{source_peer_id}] Respondeu PONG")

        elif cmd == "PONG":
            sent_time = float(message.get("timestamp", 0))
            rtt_ms = (time.time() - sent_time) * 1000
            await self.chat_client.peer_table.set_rtt(source_peer_id, rtt_ms)
            print(f"[KeepAlive] PONG recebido de {source_peer_id}, RTT: {rtt_ms} ms")

        elif cmd == "SEND":
            payload = message.get("payload", "")
            print(f"[CHAT] {source_peer_id}- payload: {payload}")
            if message.get("require_ack", False):
                ack = ProtocolEncoder.encode(
                    "ACK",
                    MY_PEER_ID,
                    msg_id=message.get("msg_id"),
                    timestamp=time.time()
                )
                self.writer.write(ack)
                await self.writer.drain()

        elif cmd == "ACK":
            msg_id = message.get('msg_id', '???')
            print(f"[Router] Mensagem {msg_id[:8]}... confirmada por {source_peer_id}")
            await self.chat_client.peer_table.complete_ack(msg_id)

        elif cmd == "PUB":
            dst = message.get("dst")
            payload = message.get("payload", "")
            print(f"[PUB] {dst} {source_peer_id}- payload: {payload}")

        elif cmd == "BYE":
            print(f"[Peer {source_peer_id}] Solicitou encerramento da conexão")
            bye_ok = ProtocolEncoder.encode(
                "BYE_OK",
                MY_PEER_ID,
                msg_id=message.get("msg_id"),
                src=MY_PEER_ID,
                dst=source_peer_id
            )
            self.writer.write(bye_ok)
            await self.writer.drain()
            await self.stop()

    async def send_ping(self):
        msg_id = str(uuid.uuid4())
        timestamp = time.time()
        ping = ProtocolEncoder.encode(
            "PING",
            MY_PEER_ID,
            msg_id=msg_id,
            timestamp=timestamp
        )
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
                data = await self.reader.readuntil(b'\n')
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
            