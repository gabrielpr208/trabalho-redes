import asyncio
import sys
from rendezvous import Rendezvous
from peerTable import PeerTable
from p2pClient import P2PClient

class Cli:
    def __init__(self):
        self.peer_table = PeerTable()
        self.chat_client = P2PClient()
        self.rdv = Rendezvous(self.peer_table, self)
        self.server: asyncio.Server | None = None
        self.running = True
        self.rdv_task: asyncio.Task | None = None

    async def run(self):
        loop = asyncio.get_event_loop()
        print("--- Chat P2P ---")
        self.print_cli_help()

        while self.running:
            try:
                user_input = await loop.run_in_executor(None, sys.stdin.readline)
                command = user_input.strip()

                if command:
                    await self.process_command(command)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[CLI] Erro no loop de entrada: {e}")

    def print_cli_help(self):
        print("Comandos disponíveis:")
        print("  /peers: Força descoberta e lista peers conhecidos/ativos.")
        print("  /conn: Mostra peers ativos e status da conexão.")
        print("  /rtt: Exibe o RTT médio por peer.")
        print("  /msg <peer_id> <mensagem>: Envia mensagem direta (SEND com ACK).")
        print("  /pub [* | #namespace] <mensagem>: Envia mensagem para todos ativos.")
        print("  /quit: Encerra a aplicação.")

    async def process_command(self, command: str):
        command_parts = command.split(maxsplit=2)
        cmd = command_parts[0].lower()

        if cmd == "/peers":
            await self.rdv.discover()
            await self.chat_client.print_active_connecions()
        elif cmd == "/conn":
            await self.chat_client.print_active_connecions()
        elif cmd == "/msg":
            if len(command_parts) == 3:
                await self.chat_client.send_message(command_parts[1], command_parts[2])
            else:
                print("Formato incorreto. Digite: /msg <peer_id> <mensagem>")
        elif cmd == "/pub":
            if len(command_parts) == 3:
                await self.chat_client.pub_message(command_parts[1], command_parts[2])
            else:
                print("Formato incorreto. Digite: /pub [* | #namespace] <mensagem>")
        elif cmd == "/rtt":
            await self.chat_client.print_rtt()
        elif cmd == "/quit":
            await self.chat_client.quit()
        else:
            print(f"Comando {cmd} não é válido")
            self.print_cli_help()
        
            
        
        