import requests
from dataclasses import dataclass
import pynng

@dataclass  
class SessionData:
    success: bool = False
    msg: str = ""
    nng_port: int = -1
    udp_port: int = -1
    udp_secret_key: str = ""
    token: str = ""


class ACRemoteClient:
    """
    This class is intended to act as a abstraction layer to the animacharacter communication channels,
    handling session creation via HTTP requests to the authenticator server, and managing the underlying
    pynng and udp sockets for communication once a session is established.
    
    This class should not be instantiated directly; instead, use the higher-level ACClient class that wraps this one
    """
    def __init__(self, ip: str) -> None:
        self.ip = ip
        self.base_url = f"http://{self.ip}:8000/auth"
        self.session_data: SessionData = SessionData(success=False)

    def attempt_session_http_rqst(self, secret_key: str, timeout: int = 10) -> bool:
        try:
            resp = requests.post(f"http://{self.ip}:8000/auth", json={"apikey": secret_key}, timeout=timeout)
        except requests.exceptions.RequestException as e:
            return False
        
        if resp.status_code != 200:
            return False

        try:
            respjson: dict = resp.json()
        except requests.exceptions.JSONDecodeError:
            return False
        
        session_data = SessionData(
            success=respjson.get("success", False),
            msg=respjson.get("msg", ""),
            nng_port=respjson.get("nng_port", -1),
            udp_port=respjson.get("udp_port", -1),
            udp_secret_key=respjson.get("udp_secret_key", ""),
            token=respjson.get("token", "")
        )
        self.session_data = session_data

        print(self.session_data)
        return self.session_data.success


if __name__ == "__main__":
    client =    ACRemoteClient("127.0.0.1")
    client.attempt_session_http_rqst("supersecret-client-key")

    if not client.session_data.success:
        print("Failed to establish session")
        exit(1)
    
    with pynng.Pair0(dial=f"tcp://127.0.0.1:{client.session_data.nng_port}") as pynng_sock:
        pynng_sock.send(b"Hello from client")
        data = pynng_sock.recv(True)
        print(f"Received from server: {data}")