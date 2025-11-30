import asyncio
import config
import sys
class Cli:
    def __init__(self, p2p_client):
        self.p2p_client = p2p_client
        self.running = True
        self.loop = None

    async def run(self):
        print("--- Chat P2P ---")
        self.print_user_info()
        self.print_cli_help()
        self.loop = asyncio.get_running_loop()
        self.loop.add_reader(sys.stdin, self.handle_input)

        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if self.loop:
                self.loop.remove_reader(sys.stdin)

    def handle_input(self):
        data = sys.stdin.readline()
        if not data:
            self.stop()
            return

        command = data.strip()
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
            await self.rendezvous.unregister()
            self.stop()
        else:
            print(f"Comando {cmd} não é válido")
            self.print_cli_help()
        
            
        
        