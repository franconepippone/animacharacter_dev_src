from collections.abc import Sequence
from typing import Tuple
from dataclasses import dataclass
import requests
import random
import time

from authmsg import PeerTCP, PeerUDP
import threading as th

from commons.network.udp_motionframe_schema import encode_motionframe_packet
from commons.network.packet_schemas import (
    HeartBeatPacket,
    ConfigurationPacket,
    SessionEndRequestPacket,
)




@dataclass  
class SessionData:
    success: bool = False
    msg: str = ""
    nng_port: int = -1
    udp_port: int = -1
    udp_secret_key: str = ""
    token: str = ""

def send_request(url: str, payload: dict, timeout: float) -> dict | None:
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except requests.exceptions.RequestException:
        return 
    
    if resp.status_code != 200:
        return

    try:
        return resp.json()
    except requests.exceptions.JSONDecodeError:
        return

def send_session_request(
        url: str, 
        secret_key: str,
        local_udp_port: int, 
        timeout: int = 10
    ) -> SessionData:
    rqst_payload = {
        "apikey": secret_key,
        "udp_port": local_udp_port
    }
    response = send_request(url, rqst_payload, timeout)

    if not response:
        return SessionData(success=False)
    
    session_data = SessionData(
        success=response.get("success", False),
        msg=response.get("msg", ""),
        nng_port=response.get("nng_port", -1),
        udp_port=response.get("udp_port", -1),
        udp_secret_key=response.get("udp_secret_key", ""),
        token=response.get("token", "")
    )
    return session_data



class AnimacharacterSessionClient:
    """
    This class is intended to act as a abstraction layer to the animacharacter raw communication channels,
    handling session creation via HTTP requests to the authenticator server, and managing the underlying
    pynng and udp sockets for communication once a session is established.
    
    This class should not be instantiated directly; instead, use the higher-level ACClient class that wraps this one
    """
    def __init__(self, auth_key: str, ip: str, port: int = 8000) -> None:
        self.ip = ip
        self.port = port
        self.auth_key = auth_key
        self.url = f"http://{self.ip}:{self.port}/auth"
        self.peertpc = PeerTCP()
        self.peerudp = PeerUDP()
        self._tcp_lock = th.Lock()
        self._heartbeat_thread = th.Thread(target=self.__heartbeat_threaded, daemon=True)
        self.session_data: SessionData = SessionData(success=False)

    def __heartbeat_threaded(self):
        while True:
            time.sleep(5)
            ok = self._send_heartbeat()
            if not ok:
                print("eartbeat could not be sent")

    def _send_heartbeat(self) -> bool:
        """Sends a heathbeat packet. This is called periodically from another thread"""
        nonce = random.randbytes(16)
        msg = HeartBeatPacket.encode(nonce)
        with self._tcp_lock:
            return self.peertpc.send(msg)
        
        # NOTE this does not check for echo package. Eventually it should be checked in a centrailized recv handler
    
    def send_motionframe(self, motionframe: Sequence[Tuple[int, float]]) -> bool:
        encoded = encode_motionframe_packet(motionframe)
        return self.peerudp.send(encoded)

    def initiate_session(self):
        udp_port = self.peerudp.local_address[1]
        self.session_data = send_session_request(
            self.url,
            self.auth_key,
            udp_port
        )

        if not self.session_data.success:
            print("Failed to initiate session")
            return

        self.peertpc.set_psk(self.session_data.token)
        self.peerudp.set_psk(self.session_data.token)

        self.peertpc.dial(self.ip, self.session_data.nng_port)
        self.peerudp.dial(self.ip, self.session_data.udp_port)

        self._heartbeat_thread.start()





if __name__ == "__main__":
    import time
    
    client = AnimacharacterSessionClient('supersecret-client-key', "127.0.0.1")
    client.initiate_session()

    for _ in range(10):
        client.send_motionframe([(0, 0.5), (1, 1.5), (2, 2.3)])
        time.sleep(.5)
        client.peertpc.send(ConfigurationPacket.encode({'hello': {'there': {'test': "cfg-msg-test"}}, 'simple': 15.0}))
        time.sleep(1)
    
    client.peertpc.send(SessionEndRequestPacket.encode())
    