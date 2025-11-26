import asyncio
import json
import uuid
import sys
import random
import time
from typing import Dict, Any, List, Tuple, Optional
from peerTable import PeerTable
from p2pClient import P2PClient

class Rendezvous:
    def __init__(self, peer_table: PeerTable, p2p_client: P2PClient):
        self.peer_table = peer_table
        self.p2p_client = p2p_client
        self.running = True