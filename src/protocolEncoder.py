import json
from typing import Any, Dict

class ProtocolEncoder:
    @staticmethod
    def encode(command_type: str, sender_id: str, **kwargs: any):
        message = {
            "type": command_type,
            "peer_id": sender_id,
            "ttl": 1,
            **kwargs
        }

        return (json.dumps(message) + '\n').encode('utf-8')
    
    @staticmethod
    def decode(data: bytes) -> Dict[str, Any]:
        try:
            message = data.decode('utf-8').strip()
            if not message:
                return {}
            return json.loads(message)
        except json.JSONDecodeError as e:
            print(f"[!] Erro de decodificação JSON: {e} na string: {message}")
            return {}

