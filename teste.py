# ... (código anterior igual)

    async def discover(self, namespace_input: str = "*"): # Adicionei o valor padrão * para facilitar
        # Lógica de envio do comando (mantida)
        if namespace_input == "*":
            response = await self.send_command("DISCOVER")
        else:
            response = await self.send_command(
                "DISCOVER",
                namespace=namespace_input
            )
        
        # --- A CORREÇÃO ESTÁ AQUI ---
        
        # 1. Verifica se a resposta é um dicionário e tem a chave "peers"
        if isinstance(response, dict) and "peers" in response:
            peers_list = response["peers"]
            print(f"[Rendezvous] Recebida lista com {len(peers_list)} peers.")
            await self.peer_table.update_known_peers(peers_list)
            
        # 2. Mantém suporte caso o servidor um dia retorne uma lista direta (fallback)
        elif isinstance(response, list):
            await self.peer_table.update_known_peers(response)
            
        # 3. Tratamento de erro
        elif response and isinstance(response, dict) and response.get("error"):
            print(f"[Rendezvous] Falha no discover: {response.get('error')}")
        else:
            # Debug opcional para ver o que chegou se não for nenhum dos acima
            # print(f"[Rendezvous] Resposta em formato inesperado: {type(response)}")
            pass
```

### Por que o `peerTable.py` está correto?

O seu `peerTable.py` faz:
```python
for peer in peers_list:
    peer_id = f"{peer['name']}@{peer['namespace']}"
    # ...