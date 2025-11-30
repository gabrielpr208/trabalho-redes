import json
from typing import Any, Dict

class ProtocolEncoder:
    @staticmethod
    def encode(command_type: str, **kwargs):
        message = {
            "type": command_type,
            "ttl": 1,
        }
        message.update(kwargs)

        return (json.dumps(message) + '\n').encode('utf-8')
    
    @staticmethod
    def encode_rdv(command_type: str, **kwargs):
        message = {
            "type": command_type,
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

