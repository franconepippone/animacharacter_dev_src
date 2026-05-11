from __future__ import annotations
from dataclasses import dataclass
from packetcodec import BasePacket
import json

@dataclass
class HeartBeatPacket(BasePacket):
    """Implements an echo mechanism. Regularly sent from client to notify the server of its presence.
    Server terminates session if heartbeat is not received within a timeout.
    """
    nonce: bytes

    @staticmethod
    def encode(nonce: bytes): return nonce
    @staticmethod
    def decode(bin: bytes): return HeartBeatPacket(nonce=bin)

@dataclass
class ConfigurationPacket(BasePacket):
    """Use to exchange json-formatted configuration strings"""
    json_str: str
    json_obj: object
    valid: bool

    @staticmethod
    def encode(json_dict: object):
        return json.dumps(json_dict).encode()

    @staticmethod
    def decode(bin: bytes): 
        try:
            json_str = bin.decode()
            json_obj = json.loads(json_str)
            return ConfigurationPacket(json_str, json_obj, True)
        except (json.JSONDecodeError, UnicodeDecodeError): 
            return ConfigurationPacket('', None, False)
    


class SessionEndRequestPacket(BasePacket):
    """Used by a client to request the session runner a clean session termination"""
    @staticmethod
    def encode(): return b""
    @staticmethod
    def decode(bin: bytes): return SessionEndRequestPacket()

# define your own packet scheme
@dataclass
class MyPacket(BasePacket):
    val1: int
    val2: float
    msg: str

    # optionally, encode could be called on the instance itself, but it's preferred to implement static encode in order to avoid an object instantiation
    #def selfencode(self) -> bytes:
    #    return self.encode(self.val1, self.val2, self.msg)

    @staticmethod
    def encode(val1: int, val2: float, msg: str) -> bytes:
        return "-".join([str(val1), str(val2), msg]).encode()
    
    @staticmethod
    def decode(bin: bytes) -> MyPacket:
        val1_str, val2_str, msg = bin.decode().split("-")
        return MyPacket(int(val1_str), int(val2_str), msg)
 
