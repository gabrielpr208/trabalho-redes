import asyncio
import config
import sys
from prompt_toolkit import PromptSession


class Cli:
    def __init__(self, p2p_client):
        self.p2p_client = p2p_client
        self.running = True
        self.loop = None
        self.prompt_session = PromptSession()

    async def run(self):
        print("--- Chat P2P ---")
        self.print_user_info()
        self.print_cli_help()

        while self.running:
            try:
                command = await self.prompt_session.prompt_async("> ")
            except asyncio.CancelledError:
                break

            command = command.strip()
            if command:
                asyncio.create_task(self.process_command(command))

    def stop(self):
        self.running = False
        asyncio.create_task(self.p2p_client.quit())

    def print_user_info(self):
        print(f"ID: {config.MY_PEER_ID}")
        print(f"IP: {config.MY_LISTEN_IP}")
        print(f"Port: {config.MY_LISTEN_PORT}")

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
            if len(command_parts) != 2:
                print("Formato incorreto. Digite: /peers [* | #namespace]")
                return
            await self.p2p_client.rdv_client.discover(command_parts[1])
            await self.p2p_client.print_active_connecions()

        elif cmd == "/conn":
            await self.p2p_client.print_active_connecions()

        elif cmd == "/msg":
            if len(command_parts) == 3:
                await self.p2p_client.send_message(command_parts[1], command_parts[2])
            else:
                print("Formato incorreto. Digite: /msg <peer_id> <mensagem>")

        elif cmd == "/pub":
            if len(command_parts) == 3:
                await self.p2p_client.pub_message(command_parts[1], command_parts[2])
            else:
                print("Formato incorreto. Digite: /pub [* | #namespace] <mensagem>")

        elif cmd == "/rtt":
            await self.p2p_client.print_rtt()

        elif cmd == "/quit":
            await self.p2p_client.rdv_client.unregister()
            self.stop()
        else:
            print(f"Comando {cmd} não é válido")
            self.print_cli_help()
