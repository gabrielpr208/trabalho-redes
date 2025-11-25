import asyncio
from typing import Dict, Any, List

from config import MY_PEER_ID

class PeerTable:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.known_peers: Dict[str, Dict[str, Any]] = {}
        self.active_writers: Dict[str, asyncio.StreamWriter] = {}
    
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
            print(f"[PeerTable] {peer_id} marcado como ATIVO.")
    
    async def remove_peer(self, peer_id):
        async with self._lock:
            if peer_id in self.active_writers:
                del self.active_writers[peer_id]

            if peer_id in self.known_peers:
                self.known_peers[peer_id]['status'] = 'stale'

            print(f"[PeerTable] {peer_id} removido da lista ativa e marcado como STALE.")

    async def get_writer(self, peer_id):
        async with self._lock:
            return self.active_writers.get(peer_id)
        
    async def get_active_peers_ids(self) -> List[str]:
        async with self._lock:
            return list(self.active_writers.keys())