import asyncio
from typing import Dict, Any, List

from config import MY_PEER_ID

class PeerTable:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.known_peers: Dict[str, Dict[str, Any]] = {}
        self.active_writers: Dict[str, asyncio.StreamWriter] = {}
        self.rtt: Dict[str, List[float]] = {}
        self.pending_acks: Dict[str, asyncio.Future] = {}
    
    async def update_known_peers(self, peers_list: List[Dict[str, Any]]):
        async with self._lock:
            for peer in peers_list:
                peer_id = f"{peer['name']}@{peer['namespace']}"
                if peer_id == MY_PEER_ID:
                    continue
                if peer_id not in self.known_peers:
                    self.known_peers[peer_id] = {
                        'ip': peer['ip'],
                        'port': peer['port'],
                        'status': 'stale'
                    }
                    print(f"[PeerTable] Novo peer conhecido: {peer_id} em {peer['ip']}:{peer['port']}")
    
    async def get_stale_peers(self):
        async with self._lock:
            stale_peers= [
                (pid, data['ip'], data['port'])
                for pid, data in self.known_peers.items()
                if data.get('status') == 'stale' and pid not in self.active_writers
            ]
            return stale_peers
        
    async def add_active_peer(self, peer_id, writer):
        async with self._lock:
            if peer_id in self.known_peers:
                self.known_peers[peer_id]['status'] = 'active'
            self.active_writers[peer_id] = writer
            if peer_id not in self.rtt:
                self.rtt[peer_id] = []
            print(f"[PeerTable] {peer_id} marcado como ATIVO.")
    
    async def remove_peer(self, peer_id):
        async with self._lock:
            if peer_id in self.active_writers:
                del self.active_writers[peer_id]

            if peer_id in self.known_peers:
                self.known_peers[peer_id]['status'] = 'stale'
            
            if peer_id in self.rtt:
                del self.rtt[peer_id]

            print(f"[PeerTable] {peer_id} removido da lista ativa e marcado como STALE.")

    async def get_writer(self, peer_id):
        async with self._lock:
            return self.active_writers.get(peer_id)
        
    async def get_active_peers(self) -> List[str]:
        async with self._lock:
            return list(self.active_writers.keys())
        
    async def mean_rtt(self, peer_id: str):
        async with self._lock:
            if peer_id in self.rtt and self.rtt[peer_id]:
                return sum(self.rtt[peer_id]) / len(self.rtt[peer_id])
            return 0.0
        
    async def set_rtt(self, peer_id: str, rtt: float):
        async with self._lock:
            if peer_id not in self.rtt:
                self.rtt[peer_id] = []
            if len(self.rtt[peer_id]) >= 5:
                self.rtt[peer_id].pop(0)
            self.rtt[peer_id].append(rtt)

    async def create_ack(self, msg_id: str):
        async with self._lock:
            future = asyncio.get_running_loop().create_future()
            self.pending_acks[msg_id] = future
            return future
        
    async def complete_ack(self, msg_id: str):
        async with self._lock:
            if msg_id in self.pending_acks:
                future = self.pending_acks.pop(msg_id)
                if not future.done():
                    future.set_result(True)
