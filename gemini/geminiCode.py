import socket
import threading
import json
import time
import sys
import uuid
import random

# --- 1. CONFIGURAÇÕES INICIAIS ---
# Estas configurações podem ser movidas para um config.json ou config.py
# O endereço do servidor Rendezvous fornecido no seu projeto
RDV_IP = "45.171.101.167" 
RDV_PORT = 8080

# Configure seu Peer ID (nome@namespace) e a porta local
MY_NAME = "Aluno" + str(random.randint(100, 999))
MY_NAMESPACE = "UnB_Networks"
MY_PEER_ID = f"{MY_NAME}@{MY_NAMESPACE}"

# Porta local para aceitar conexões de outros peers.
# O Rendezvous Server precisa ser capaz de te alcançar neste IP/Porta.
MY_LISTEN_PORT = 50001
MY_LISTEN_IP = "0.0.0.0"  # Ouve em todas as interfaces

# Frequência de keep-alive e descoberta (em segundos)
PING_INTERVAL = 30
DISCOVERY_INTERVAL = 10 
MAX_RECONNECT_ATTEMPTS = 5

class ProtocolEncoder:
    """
    Classe utilitária para codificar e decodificar mensagens JSON no formato do protocolo.
    As mensagens são formatadas como JSON (UTF-8) e delimitadas por '\n'.
    """
    @staticmethod
    def encode(command_type, **kwargs):
        """Cria e serializa um comando JSON."""
        message = {
            "type": command_type,
            "peer_id": MY_PEER_ID,
            "ttl": 1,
            **kwargs 
        }
        # Adiciona o delimitador de stream TCP
        return (json.dumps(message) + '\n').encode('utf-8')

    @staticmethod
    def decode(data):
        """
        Decodifica bytes brutos de um stream TCP em objetos JSON.
        Lida com múltiplas mensagens em um único buffer, separadas por '\n'.
        """
        messages = []
        # Dividimos o buffer pelos delimitadores de nova linha
        raw_messages = data.decode('utf-8').split('\n')
        
        # A última parte pode ser incompleta, então não a processamos
        for msg_str in raw_messages[:-1]:
            if msg_str.strip():
                try:
                    messages.append(json.loads(msg_str))
                except json.JSONDecodeError as e:
                    print(f"[!] Erro de decodificação JSON: {e} na string: {msg_str.strip()}")
        
        # Retorna as mensagens completas e a parte restante (incompleta) do buffer
        return messages, raw_messages[-1]

class ConnectionHandler(threading.Thread):
    """
    Thread responsável por gerenciar uma única conexão TCP com outro Peer.
    Aqui é onde o PING/PONG e o tratamento de SEND/ACK/PUB acontece.
    """
    def __init__(self, client_socket, address, peer_table):
        super().__init__()
        self.client_socket = client_socket
        self.address = address
        self.peer_table = peer_table
        self.peer_id = None
        self.running = True
        self.buffer = ""
        print(f"[+] Handler iniciado para conexão de {address}")

    def run(self):
        """Loop principal de leitura de dados."""
        self.client_socket.settimeout(60) # Timeout de leitura
        while self.running:
            try:
                data = self.client_socket.recv(4096)
                if not data:
                    print(f"[-] Conexão encerrada por {self.peer_id if self.peer_id else self.address}")
                    break
                
                # Decodifica e processa dados recebidos
                messages, self.buffer = ProtocolEncoder.decode(data.decode('utf-8') + self.buffer)
                
                for msg in messages:
                    self.process_command(msg)

            except socket.timeout:
                # Se ocorrer timeout, o KeepAlive deve enviar PING. Se não houver resposta, fechar.
                # Lógica de Keep-Alive e PING/PONG será adicionada aqui.
                pass 
            except Exception as e:
                print(f"[!] Erro na conexão com {self.peer_id}: {e}")
                break
        
        self.peer_table.remove_peer(self.client_socket)
        self.client_socket.close()

    def process_command(self, msg):
        """Processa o comando recebido e executa a ação apropriada."""
        cmd = msg.get("type")
        src_peer_id = msg.get("peer_id")
        
        if not cmd:
            print(f"[Handler] Comando inválido recebido de {self.address}: {msg}")
            return

        print(f"[Peer:{src_peer_id if src_peer_id else self.address}] Recebido: {cmd}")

        # Handshake inicial: Define o ID do peer e responde
        if cmd == "HELLO":
            self.peer_id = src_peer_id
            self.peer_table.update_connection_status(self.peer_id, self.client_socket, 'active')
            
            response = ProtocolEncoder.encode("HELLO_OK", peer_id=MY_PEER_ID)
            self.client_socket.sendall(response)
        
        # Keep-Alive
        elif cmd == "PING":
            pong = ProtocolEncoder.encode("PONG", msg_id=msg.get("msg_id"), timestamp=time.time())
            self.client_socket.sendall(pong)
        
        # Confirmação de Keep-Alive (PING)
        elif cmd == "PONG":
            # Aqui você registraria o RTT (Round Trip Time)
            sent_time = float(msg.get("timestamp", 0))
            rtt = (time.time() - sent_time) * 1000
            print(f"[KeepAlive] RTT com {self.peer_id}: {rtt:.2f} ms")

        # Mensagem Unicast (Ponto a Ponto)
        elif cmd == "SEND":
            payload = msg.get("payload", "")
            print(f"\n[CHAT - {src_peer_id}] {payload}")
            
            if msg.get("require_ack", False):
                ack = ProtocolEncoder.encode("ACK", msg_id=msg.get("msg_id"), timestamp=time.time())
                self.client_socket.sendall(ack)
        
        # Confirmação de recebimento (ACK)
        elif cmd == "ACK":
            print(f"[Router] Mensagem {msg.get('msg_id')} confirmada por {src_peer_id}.")

        # Mensagem de Broadcast/Namespace
        elif cmd == "PUB":
            dst = msg.get("dst")
            payload = msg.get("payload", "")
            if dst == "*":
                print(f"\n[BROADCAST - {src_peer_id}] {payload}")
            elif dst.startswith('#'):
                print(f"\n[NAMESPACE {dst} - {src_peer_id}] {payload}")
        
        # Encerramento
        elif cmd == "BYE":
            print(f"[Peer:{src_peer_id}] Solicitou encerramento da conexão.")
            bye_ok = ProtocolEncoder.encode("BYE_OK", msg_id=msg.get("msg_id"), src=MY_PEER_ID, dst=src_peer_id)
            self.client_socket.sendall(bye_ok)
            self.running = False

    def send_command(self, cmd_type, **kwargs):
        """Envia um comando para o peer conectado."""
        try:
            message = ProtocolEncoder.encode(cmd_type, **kwargs)
            self.client_socket.sendall(message)
        except Exception as e:
            print(f"[!] Erro ao enviar {cmd_type} para {self.peer_id}: {e}")
            self.running = False # Encerra o handler em caso de falha de envio

class PeerTable:
    """
    Gerencia a lista de peers conhecidos (do Rendezvous) e os ativos (conectados).
    Substitui os módulos peer_table.py e state.py sugeridos.
    """
    def __init__(self):
        # { peer_id: { 'ip': ip, 'port': port, 'status': 'unknown' } }
        self.known_peers = {} 
        # { peer_id: ConnectionHandler instance }
        self.active_peers = {} 
        self.lock = threading.Lock()

    def update_known_peers(self, peers_list):
        """Atualiza a lista de peers conhecidos a partir do Rendezvous."""
        with self.lock:
            for p in peers_list:
                peer_id = f"{p['name']}@{p['namespace']}"
                # Evita adicionar a si mesmo
                if peer_id == MY_PEER_ID:
                    continue 

                if peer_id not in self.known_peers:
                    self.known_peers[peer_id] = {
                        'ip': p['ip'],
                        'port': p['port'],
                        'status': 'stale' # Começa como STALE (conhecido mas não conectado)
                    }
                    print(f"[PeerTable] Novo peer conhecido: {peer_id} em {p['ip']}:{p['port']}")
    
    def get_known_but_stale_peers(self):
        """Retorna peers que conhecemos, mas ainda não estão ativos."""
        with self.lock:
            stale_peers = [
                (peer_id, data['ip'], data['port']) 
                for peer_id, data in self.known_peers.items() 
                if data['status'] == 'stale'
            ]
            return stale_peers

    def update_connection_status(self, peer_id, client_socket, status):
        """Marca o peer como ativo e armazena o handler (ou desativa)."""
        with self.lock:
            if peer_id in self.known_peers:
                self.known_peers[peer_id]['status'] = status
            
            if status == 'active' and peer_id not in self.active_peers:
                 # Cria e armazena um handler para o socket ativo (para conexões inbound)
                handler = ConnectionHandler(client_socket, client_socket.getpeername(), self)
                self.active_peers[peer_id] = handler
                handler.start()

    def remove_peer(self, client_socket):
        """Remove um peer inativo da tabela de ativos e marca como STALE."""
        with self.lock:
            peer_to_remove = None
            # Encontra o peer_id associado ao socket
            for peer_id, handler in list(self.active_peers.items()):
                if handler.client_socket == client_socket:
                    peer_to_remove = peer_id
                    break
            
            if peer_to_remove:
                del self.active_peers[peer_to_remove]
                if peer_to_remove in self.known_peers:
                    self.known_peers[peer_to_remove]['status'] = 'stale'
                print(f"[PeerTable] Peer {peer_to_remove} removido da lista ativa.")

    def get_active_peer_handler(self, peer_id):
        """Retorna o ConnectionHandler de um peer ativo."""
        with self.lock:
            return self.active_peers.get(peer_id)

    def list_active_connections(self):
        """Lista as conexões ativas para o comando /conn."""
        with self.lock:
            return [(pid, data['ip'], data['port']) 
                    for pid, data in self.known_peers.items() 
                    if data['status'] == 'active']
        
class RendezvousClient(threading.Thread):
    """
    Thread em background para manter a comunicação com o servidor Rendezvous.
    Executa REGISTER e DISCOVER em loop.
    """
    def __init__(self, peer_table):
        super().__init__()
        self.peer_table = peer_table
        self.running = True
        self.connect_attempts = 0
        self.rdv_sock = None
        self.daemon = True # Garante que o thread morra quando o principal sair

    def connect_rdv(self):
        """Tenta conectar ao servidor Rendezvous."""
        try:
            self.rdv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.rdv_sock.settimeout(5)
            self.rdv_sock.connect((RDV_IP, RDV_PORT))
            print(f"[Rendezvous] Conectado a {RDV_IP}:{RDV_PORT}")
            self.connect_attempts = 0
            return True
        except Exception as e:
            print(f"[Rendezvous] Falha na conexão: {e}")
            self.rdv_sock = None
            self.connect_attempts += 1
            return False

    def send_rdv_command(self, command_type, **kwargs):
        """Envia um comando para o Rendezvous e espera a resposta."""
        if not self.rdv_sock:
            if not self.connect_rdv():
                return None

        try:
            message = ProtocolEncoder.encode(command_type, **kwargs)
            self.rdv_sock.sendall(message)
            
            # O Rendezvous Server deve responder com uma lista de peers (se for DISCOVER)
            response_data = self.rdv_sock.recv(4096)
            if not response_data:
                raise ConnectionResetError("Rendezvous fechou a conexão.")

            # Assume que a resposta é um JSON único contendo os peers
            response_str = response_data.decode('utf-8').strip()
            if response_str:
                return json.loads(response_str)
            return None

        except Exception as e:
            print(f"[Rendezvous] Erro de comunicação/resposta: {e}. Tentando reconectar...")
            self.rdv_sock.close()
            self.rdv_sock = None
            return None

    def register(self):
        """Envia o comando REGISTER ao Rendezvous Server."""
        print(f"[Rendezvous] Tentando REGISTER: {MY_PEER_ID}")
        # Simulamos a mensagem REGISTER (assumindo a IP é o host de conexão, mas enviamos a porta de escuta)
        response = self.send_rdv_command(
            "REGISTER",
            name=MY_NAME,
            namespace=MY_NAMESPACE,
            port=MY_LISTEN_PORT # Porta que outros peers usarão para conectar a mim
        )
        if response and response.get("status") == "OK":
             print(f"[Rendezvous] Registro de {MY_PEER_ID} concluído com sucesso.")
        elif response:
             print(f"[Rendezvous] Falha no registro: {response.get('error', 'Desconhecido')}")


    def discover(self):
        """Envia o comando DISCOVER para obter a lista de peers."""
        # Se o servidor não for implementado para usar o mesmo protocolo, 
        # este comando deve ser ajustado para o protocolo HTTP/API real do Rendezvous.
        
        response = self.send_rdv_command("DISCOVER")
        
        if response and isinstance(response, list):
            print(f"[Rendezvous] Descobertos {len(response)} peers.")
            self.peer_table.update_known_peers(response)
        elif response and response.get("error"):
            print(f"[Rendezvous] Erro na descoberta: {response.get('error')}")

    def run(self):
        """Loop principal do thread Rendezvous."""
        time.sleep(1) # Aguarda o PeerServer iniciar
        while self.running:
            if self.connect_attempts < MAX_RECONNECT_ATTEMPTS:
                if self.rdv_sock is None:
                    self.connect_rdv()
                
                if self.rdv_sock:
                    # 1. Registrar-se
                    self.register()
                    # 2. Descobrir peers e atualizar a tabela
                    self.discover()
                    self.rdv_sock.close() # Fecha a conexão após DISCOVER (se o servidor for stateless)
                    self.rdv_sock = None
                
            else:
                print(f"[Rendezvous] Limite de {MAX_RECONNECT_ATTEMPTS} tentativas de conexão excedido. Suspender.")
                
            time.sleep(DISCOVERY_INTERVAL)
            
class P2PChatClient:
    """
    Classe principal que orquestra os componentes (Peer Server, Rendezvous Client, CLI).
    Corresponde ao módulo p2p_client.py sugerido.
    """
    def __init__(self):
        self.peer_table = PeerTable()
        self.running = False
        self.server_sock = None
        self.rdv_client = RendezvousClient(self.peer_table)
        
    def start(self):
        """Inicia o servidor de escuta e o thread Rendezvous."""
        print("--- Chat P2P ---")
        print(f"Peer ID: {MY_PEER_ID}")
        print(f"Ouvindo em: {MY_LISTEN_PORT}")
        
        # 1. Inicia o servidor de escuta (Peer Server)
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_sock.bind((MY_LISTEN_IP, MY_LISTEN_PORT))
            self.server_sock.listen(5)
            
            listen_thread = threading.Thread(target=self.listen_for_peers, daemon=True)
            listen_thread.start()
            print("[PeerServer] Escutando por conexões de outros Peers...")

        except Exception as e:
            print(f"[FATAL] Falha ao iniciar servidor local: {e}")
            sys.exit(1)
            
        # 2. Inicia o cliente Rendezvous para descoberta e registro
        self.rdv_client.start()
        
        # 3. Inicia o loop principal de CLI e tentativa de conexão
        self.running = True
        self.main_loop()

    def listen_for_peers(self):
        """Aceita conexões de entrada e inicia um ConnectionHandler para cada uma."""
        while self.running:
            try:
                client_sock, addr = self.server_sock.accept()
                print(f"\n[PeerServer] Conexão de entrada aceita de: {addr}")
                # O ConnectionHandler irá processar o HELLO e adicionar à PeerTable
                # Não é necessário self.peer_table.update_connection_status aqui, pois 
                # o Handler o fará após receber o HELLO.
                handler = ConnectionHandler(client_sock, addr, self.peer_table)
                handler.start() 

            except Exception as e:
                # Ocorre quando o socket é fechado em self.quit()
                if self.running:
                    print(f"[PeerServer] Erro no listen: {e}")
                break

    def connect_to_peer(self, target_ip, target_port):
        """Inicia uma conexão de saída com um peer e envia HELLO."""
        try:
            new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_sock.settimeout(5)
            new_sock.connect((target_ip, target_port))
            
            # 1. Envia o HELLO
            hello_msg = ProtocolEncoder.encode("HELLO", version="1.0", features=["ack", "metrics"])
            new_sock.sendall(hello_msg)
            
            # 2. Aguarda HELLO_OK para confirmar
            # Na prática, o ConnectionHandler deve lidar com a resposta, mas para o handshake:
            response_data = new_sock.recv(4096)
            if not response_data:
                raise ConnectionResetError("Conexão fechada durante handshake.")
            
            messages, _ = ProtocolEncoder.decode(response_data)
            if not messages or messages[0].get("type") != "HELLO_OK":
                raise ValueError("Resposta HELLO_OK inválida ou ausente.")

            # Se o handshake for bem-sucedido, inicia o Handler
            peer_id = messages[0].get('peer_id')
            
            # Usa o ConnectionHandler para gerenciar a nova conexão de saída (outbound)
            handler = ConnectionHandler(new_sock, (target_ip, target_port), self.peer_table)
            self.peer_table.active_peers[peer_id] = handler 
            self.peer_table.known_peers[peer_id]['status'] = 'active'
            handler.peer_id = peer_id # Define o ID para o handler Outbound
            handler.start()
            
            print(f"[Router] Conectado e ativo com: {peer_id}")
            return True

        except Exception as e:
            print(f"[-] Falha ao conectar a {target_ip}:{target_port} (Tentativas: {MAX_RECONNECT_ATTEMPTS}): {e}")
            return False

    def check_and_connect_stale_peers(self):
        """Verifica a tabela de peers e tenta conectar-se aos 'stale' (conhecidos mas inativos)."""
        stale_peers = self.peer_table.get_known_but_stale_peers()
        for peer_id, ip, port in stale_peers:
            if peer_id not in self.peer_table.active_peers:
                print(f"[Router] Tentando conexão de saída com peer 'stale': {peer_id}")
                self.connect_to_peer(ip, port)

    # --- CLI Implementation ---
    def main_loop(self):
        """Loop da interface de linha de comando."""
        while self.running:
            try:
                command = input(f"{MY_NAME}@cli> ").strip()
                if not command:
                    continue
                
                parts = command.split(maxsplit=2)
                cmd = parts[0].lower()

                if cmd == '/peers':
                    # Força a descoberta e a tentativa de conexão
                    print("[CLI] Forçando re-descoberta e reconciliação...")
                    self.rdv_client.discover()
                    self.check_and_connect_stale_peers()
                    self.print_active_peers()

                elif cmd == '/msg':
                    if len(parts) == 3:
                        target_id = parts[1]
                        message = parts[2]
                        self.send_message(target_id, message)
                    else:
                        print("Uso: /msg <peer_id> <mensagem>")

                elif cmd == '/pub':
                    if len(parts) == 3:
                        target_dst = parts[1] # * ou #namespace
                        message = parts[2]
                        self.publish_message(target_dst, message)
                    else:
                        print("Uso: /pub [* | #namespace] <mensagem>")

                elif cmd == '/conn':
                    self.print_active_peers()
                    
                elif cmd == '/quit':
                    self.quit()
                    
                else:
                    print(f"Comando '{cmd}' desconhecido.")
                    
            except EOFError:
                self.quit()
            except Exception as e:
                print(f"[CLI] Erro no loop: {e}")

    def print_active_peers(self):
        """Implementa o comando /conn."""
        active = self.peer_table.list_active_connections()
        print("\n--- Conexões Ativas ---")
        if not active:
            print("Nenhuma conexão ativa no momento.")
            return

        for pid, ip, port in active:
            status = self.peer_table.known_peers.get(pid, {}).get('status', '??')
            print(f"-> {pid} (IP: {ip}:{port}) | Status: {status.upper()}")
        print("------------------------")

    def send_message(self, target_id, message):
        """Implementa o comando /msg (SEND)."""
        handler = self.peer_table.get_active_peer_handler(target_id)
        if handler:
            print(f"[Router] Enviando SEND para {target_id}...")
            handler.send_command(
                "SEND",
                msg_id=str(uuid.uuid4()),
                src=MY_PEER_ID,
                dst=target_id,
                payload=message,
                require_ack=True
            )
        else:
            print(f"[-] Peer {target_id} não está ativo ou desconhecido. Use /peers para atualizar.")

    def publish_message(self, target_dst, message):
        """Implementa o comando /pub (PUB)."""
        if target_dst != "*" and not target_dst.startswith('#'):
            print("Destino inválido para PUB. Use '*' ou '#namespace'.")
            return
            
        print(f"[Router] Publicando PUB para {target_dst}...")
        
        # O PUB deve ser enviado para TODOS os peers ativos
        for peer_id, handler in self.peer_table.active_peers.items():
            handler.send_command(
                "PUB",
                msg_id=str(uuid.uuid4()),
                src=MY_PEER_ID,
                dst=target_dst,
                payload=message,
                require_ack=False
            )
        print(f"[Router] PUB enviado a {len(self.peer_table.active_peers)} peers ativos.")

    def quit(self):
        """Encerra a aplicação de forma limpa (BYE não implementado aqui, será no futuro)."""
        print("\n[Client] Encerrando o chat P2P. Enviando BYE para peers ativos...")
        self.running = False
        self.rdv_client.running = False
        
        # Envia BYE para todos os ativos (Implementação simplificada)
        for peer_id, handler in self.peer_table.active_peers.items():
            handler.send_command(
                "BYE",
                msg_id=str(uuid.uuid4()),
                src=MY_PEER_ID,
                dst=peer_id,
                reason="Encerrando a aplicação"
            )
            handler.running = False # Encerra a thread do handler
            handler.client_socket.close() # Fecha o socket
            
        # Fecha o socket do servidor de escuta
        if self.server_sock:
            # Desliga o socket para liberar a porta e interromper o accept()
            self.server_sock.close() 

        print("[Client] Encerrado com sucesso. Adeus!")
        sys.exit(0)

# --- EXECUÇÃO ---
if __name__ == '__main__':
    client = P2PChatClient()
    client.start()