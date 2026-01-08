import socket
import msgpack
import hmac
import hashlib
from functools import lru_cache

import time
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

### CUSTOM TYPES

type SocketAddress = tuple[str, int]
type bytedata = bytearray | bytes | memoryview

INVALID_ADDRESS: SocketAddress = ('__invalid__', 0)

### EXCEPTIONS

class SafeudpNullPeer(Exception):
    pass

class PacketEncodingFailed(Exception):
    pass

@dataclass
class OptionsFlags:
    pass

@dataclass
class seqNumTracker:
    outbound: int = 0
    inbound: int = 0


# CONSTANTS FOR saferecv METHOD
RCV_OWN_PEER = 0
RCV_EVERYONE = 1


class SafeUdpSock:
    """ 
    Wraps UDP sockets implementing an authenticated and ordered
    datagram delivery over UDP protocol. Does not provide confidentiality,
    but integrity and protection against replay attacks.
    """
    SIGNATURE_SIZE_BYTES = 8
    SEQ_NUM_SIZE_BYTES = 8
    MAX_RECV_BUFF_SIZE = 4096

    def __init__(self, secret_key: bytes, port: int | None = None) -> None:
        """ 
        Initializes SafeUdpSock with a given secret key for HMAC signing.
        If port is provided, binds the socket to that port immediately.
        """
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.secret = secret_key
        self.options = OptionsFlags()
        self._seq_num_map: dict[SocketAddress, seqNumTracker] = {}
        if port is not None:
            self.bind(port)

        self._latest_sender: SocketAddress = INVALID_ADDRESS
        self.peer: SocketAddress = INVALID_ADDRESS

    def close(self):
        """ Closes the underlying UDP socket """
        self.udp_sock.close()

    def bind(self, port: int = 0, ip: str = "0.0.0.0") -> int:
        """ 
        binds socket to ip and port. Default ip is '0.0.0.0'. If no port is
        provided, a random one will be assigned and returned by this method.
        """
        self.udp_sock.bind((ip, port))
        self.udp_sock.setblocking(True)

        assigned_port = self.udp_sock.getsockname()[1]
        logger.info(f"SafeUdpSock bound to {ip}:{assigned_port}")
        return assigned_port

    def get_latest_sender_address(self) -> SocketAddress:
        """ 
        Returns the address of the latest sender from which a valid packet
        was received. Returns an INVALID_ADDRESS if no packets have been received.
        """
        return self._latest_sender

    def send(self, data: bytedata, to: SocketAddress | None = None) -> int:
        """
        Send secured packet to peer. The packet is HMAC signed,
        this ensures knowledge of both ends of a pre-shared secret and
        avoids replay attacks. NOTE that payload data is not encoded,
        so information is not confidential.
        
        :param data: Data to be sent, either bytes, bytearray or memoryview
        :type data: bytedata
        :param to: IPv4 address, optional, if given overrides set peer.
        :type to: SocketAddress | None
        :return: Amount of bytes returned by socket.sendto(...)
        :rtype: int
        """
        peer = self.peer if self.peer[0] != INVALID_ADDRESS[0] else to
        if not peer: raise SafeudpNullPeer("Attempted 'send' without specifying a peer.")
        sqnum = self._increment_outbound_seqnum(peer)
        encoded = self._encode_frame(data, sqnum)
        if encoded is None:
            # if somehow packet encoding fails
            logger.error("Failed to encode SafeUDP frame")
            raise PacketEncodingFailed("Packet encoding unexpectedly failed during 'send'.")

        return self.udp_sock.sendto(encoded, peer)

    @lru_cache(maxsize=512)
    def _resolve_peer(self, peer: SocketAddress) -> SocketAddress:
        """
        Fixes usage of 'localhost' by resolving it to actual IP address
        """
        # NOTE that was introduced to fix the usage of localhost for testing
        # on the same machine, but caching this might not be good if we are 
        # using actual hostnames that might change IPs over time
        return socket.gethostbyname(peer[0]), peer[1]
    
    def _populate_seqnum_entry(self, peer: SocketAddress) -> SocketAddress:
        """ 
        Ensures that a seqNumTracker entry exists for the given peer address,
        and returns the resolved peer address
        """
        peer_resolved = self._resolve_peer(peer)

        if not peer_resolved in self._seq_num_map:
            self._seq_num_map[peer_resolved] = seqNumTracker()
        return peer_resolved

    def _increment_outbound_seqnum(self, peer: SocketAddress) -> int:
        """ 
        Increments the outbound sequence number by 1 for a given peer address,
        creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        self._seq_num_map[peer_resolved].outbound += 1
        return self._seq_num_map[peer_resolved].outbound
    
    def get_outbound_seqnum(self, peer: SocketAddress) -> int:
        """ 
        Returns the current outbound sequence number for a given peer address,
        creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        return self._seq_num_map[peer_resolved].outbound

    def _set_inbound_seqnum(self, peer: SocketAddress, val: int):
        """ 
        Sets the inbound sequence number for a given peer address. 
        Creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        self._seq_num_map[peer_resolved].inbound = val
    
    def get_inbound_seqnum(self, peer: SocketAddress) -> int:
        """ 
        Returns the current inbound sequence number for a given peer address,
        creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        return self._seq_num_map[peer_resolved].inbound

    def _gen_hmac(self, data: bytes) -> bytes:
        # THIS SHOULD BE MADE FASTER
        return hmac.new(self.secret, data, hashlib.blake2s).digest()[:self.SIGNATURE_SIZE_BYTES]

    def _encode_frame(self, payload: bytes, sqnum: int) -> bytes | None:
        """ 
        Package payload data into proper frame format for SafeUDP
        (Using msgpack for now, might be changed to something faster)
        """
        
        # MAYBE USE LOWER LEVEL SERIALIZATION LIBRARIRES
        return msgpack.packb((
            sqnum, 
            self._gen_hmac(payload + sqnum.to_bytes(self.SEQ_NUM_SIZE_BYTES, "big")),
            payload))
        #return self._seq_num.to_bytes(self.SEQ_NUM_SIZE_BYTES, 'big') + self._gen_hmac(payload) + payload

    def _decode_frame(self, data: bytes, peer: SocketAddress) -> bytes | None:
        """ 
        Attempts to decode a safeudp data frame. Extracts sequence number and signatures,
        and validates them. If both are ok, payload is returned, else None is returned
        """
        try:
            seq_num_remote, sig, payload = msgpack.unpackb(data)
        except Exception:
            return None
        logger.debug("unpack ok")
        
        # makes sure types are correct
        if not isinstance(seq_num_remote, int): return None
        if not isinstance(sig, bytes): return None
        if not isinstance(payload, bytes): return None
        logger.debug("types ok")

        # makes sure seq number from remote is higher, reject packets if it is equal or lower
        inbound_sqn = self.get_inbound_seqnum(peer)
        logger.debug("remote seq num: %s, local inbound seq num: %s", seq_num_remote, inbound_sqn)
        if seq_num_remote <= inbound_sqn: return None
        logger.debug("seq num ok")

        # compares signature to ensure authenticity (put sqnum in hmac to counter replay attacks) 
        expc_sig = self._gen_hmac(payload + seq_num_remote.to_bytes(self.SEQ_NUM_SIZE_BYTES, "big")) # <-- THIS CAN RAISE EXCEPTION!!
        valid = hmac.compare_digest(expc_sig, sig)
        if not valid: return None
        logger.debug("signature ok")

        # we update this at the end, only if all checks passed
        self._set_inbound_seqnum(peer, seq_num_remote)
        logger.debug("inbound seq num updated: %s", self._seq_num_map)
        return payload

    def recv(self, timeout: float = 10, recv_from: SocketAddress | int = RCV_OWN_PEER) -> bytes | None:
        """
        Attempts reception from another safeudp socket. Blocks for at most 'timeout' seconds, then
        returns None.
        Non-Blocking behaviour can be achieved by setting the underlying socket to blocking(False)
        Data is rejected if sequence number is not valid, or if signature is wrong, ensuring authenticity of sender
        and preventing replay attacks.
        
        :param timeout: Maximum time this method will block in seconds
        :type timeout: float
        :param recv_from: Address of the safeudp socket from which to receive the data, if provided. Otherwise,
        this can either be set to RCV_EVERYONE to receive from any address (must still be using safeudp),\
            and RCV_OWN_PEER (default), to only receive \
            from the set peer (fallback to RCV_EVERYONE if not peer is not set)
        :type recv_from: SocketAddress | int
        :return: The recevied payload. If timeout occurs, returns None
        :rtype: bytes | None
        """
        
        from_addr: SocketAddress | None = None
        if isinstance(recv_from, int):
            if recv_from == RCV_EVERYONE:
                from_addr = None    # kinda hacky, we change type to int
            elif recv_from == RCV_OWN_PEER:
                from_addr = self.peer
        else:
            # properly resolve hostnames
            from_addr = self._resolve_peer(recv_from)

        start_t = time.perf_counter()
        self.udp_sock.settimeout(timeout)
        while True:
            if timeout is not None:
                t_elapsed = (time.perf_counter() - start_t)
                if (t_elapsed >= timeout): break

                # only set timeout if timeout is given
                self.udp_sock.settimeout(max(0.0, timeout - t_elapsed))

            try:
                data, addr = self.udp_sock.recvfrom(self.MAX_RECV_BUFF_SIZE)
            except socket.timeout:
                break
            except ConnectionResetError:
                # this can happen on Windows if ICMP "Port Unreachable" messages are received
                # for some reason this just occurs once in a row, the next call to recvfrom blocks and times out as expected
                logger.debug("ConnectionResetError caught, ignoring")
                continue
            
            # check if address is valid
            if from_addr in (None, addr):
                payload_data = self._decode_frame(data, addr)
                if payload_data is None:
                    # if payload failed to decode or seq num / signature don't match, reject the packet
                    logger.debug(f"Rejected packet from {addr}")
                    continue

                # otherwise we return the payload data
                self._latest_sender = addr
                return payload_data
    
    def set_peer(self, peer_addr: SocketAddress | None):
        # NOTE this might raise exception if hostname cannot be resolved
        new_peer = self._resolve_peer(peer_addr) if peer_addr is not None else None
        if not new_peer:
            self.peer = INVALID_ADDRESS
        else:
            self.peer = new_peer
        logger.debug(f"New peer is to {self.peer}")

    def getoptions(self) -> OptionsFlags:
        """ Returns options dataclass. You can edit the flags to modify the options """
        return self.options

    def override_outbound_seqnum(self, peer: SocketAddress, val: int):
        """ Overrides the outbound sequence number for a given peer address. Useful when continuing
        a session with a different SafeUdpSock object. 
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        self._seq_num_map[peer_resolved].outbound = val
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()