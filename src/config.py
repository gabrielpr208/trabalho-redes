import random

RDV_IP = "45.171.101.167" 
RDV_PORT = 8080
PING_INTERVAL = 30
DISCOVERY_INTERVAL = 10 
MAX_RECONNECT_ATTEMPTS = 5    

MY_NAME: str
MY_NAMESPACE: str
MY_PEER_ID = f"{MY_NAME}@{MY_NAMESPACE}"

MY_LISTEN_PORT = 50000 + random.randint(0, 9999)
MY_LISTEN_IP = "127.0.0.1"

def printName():
    print(f"Name: {MY_NAME}")
    print(f"Namespace: {MY_NAMESPACE}")