import socket
import msgpack
import hmac
import hashlib
from functools import lru_cache

import time
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

type SocketAddress = tuple[str, int]

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
    """ Safe UDP Socket implementation providing authenticated and ordered
    datagram delivery over UDP protocol. 
    """
    SIGNATURE_SIZE_BYTES = 8
    SEQ_NUM_SIZE_BYTES = 8
    MAX_RECV_BUFF_SIZE = 4096

    def __init__(self, secret_key: bytes, port: int | None = None) -> None:
        """ Initializes SafeUdpSock with a given secret key for HMAC signing.
        If port is provided, binds the socket to that port immediately.
        """
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.secret = secret_key
        self.options = OptionsFlags()
        self._seq_num_map: dict[SocketAddress, seqNumTracker] = {}
        if port is not None:
            self.bind(port)

        self._latest_sender: SocketAddress | None = None
        self.peer: SocketAddress | None = None

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

    def get_latest_sender_address(self) -> SocketAddress | None:
        """ Returns the address of the latest sender from which a valid packet
        was received. Returns None if no packets have been received yet.
        """
        return self._latest_sender

    def safesend(self, data: bytes | bytearray, to: SocketAddress | None = None) -> int:
        peer = to if to is not None else self.peer
        if peer is None: raise Exception("no peer address set for SafeUdpSock")

        sqnum = self._increment_outbound_seqnum(peer)

        encoded = self._encode_frame(data, sqnum)
        if encoded is None:
            # if somehow packet encoding fails
            logger.error("Failed to encode SafeUDP frame")
            return -1

        return self.udp_sock.sendto(encoded, peer)

    @lru_cache(maxsize=512)
    def _resolve_peer(self, peer: SocketAddress) -> SocketAddress:
        """ Fixes usage of 'localhost' by resolving it to actual IP address"""
        # NOTE that was introduced to fix the usage of localhost for testing
        # on the same machine, but caching this might not be good if we are 
        # using actual hostnames that might change IPs over time
        return socket.gethostbyname(peer[0]), peer[1]
    
    def _populate_seqnum_entry(self, peer: SocketAddress) -> SocketAddress:
        """ Ensures that a seqNumTracker entry exists for the given peer address,
        and returns the resolved peer address
        """
        peer_resolved = self._resolve_peer(peer)

        if not peer_resolved in self._seq_num_map:
            self._seq_num_map[peer_resolved] = seqNumTracker()
        return peer_resolved

    def _increment_outbound_seqnum(self, peer: SocketAddress) -> int:
        """ Increments the outbound sequence number by 1 for a given peer address,
        creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        self._seq_num_map[peer_resolved].outbound += 1
        return self._seq_num_map[peer_resolved].outbound
    
    def _get_outbound_seqnum(self, peer: SocketAddress) -> int:
        """ Returns the current outbound sequence number for a given peer address,
        creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        return self._seq_num_map[peer_resolved].outbound

    def _set_inbound_seqnum(self, peer: SocketAddress, val: int):
        """ Sets the inbound sequence number for a given peer address. 
        Creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        self._seq_num_map[peer_resolved].inbound = val
    
    def _get_inbound_seqnum(self, peer: SocketAddress) -> int:
        """ Returns the current inbound sequence number for a given peer address,
        creates new entry on the map if not present
        """
        peer_resolved = self._populate_seqnum_entry(peer)
        return self._seq_num_map[peer_resolved].inbound

    def _gen_hmac(self, data: bytes) -> bytes:
        # THIS SHOULD BE MADE FASTER
        return hmac.new(self.secret, data, hashlib.blake2s).digest()[:self.SIGNATURE_SIZE_BYTES]

    def _encode_frame(self, payload: bytes, sqnum: int) -> bytes | None:
        """ Package payload data into proper frame format for SafeUDP
        (Using msgpack for now, might be changed to something faster)
        """
        
        # MAYBE USE LOWER LEVEL SERIALIZATION LIBRARIRES
        return msgpack.packb((
            sqnum, 
            self._gen_hmac(payload + sqnum.to_bytes(self.SEQ_NUM_SIZE_BYTES, "big")),
            payload))
        #return self._seq_num.to_bytes(self.SEQ_NUM_SIZE_BYTES, 'big') + self._gen_hmac(payload) + payload

    def _decode_frame(self, data: bytes, peer: SocketAddress) -> bytes | None:
        """ Attempts to decode a safeudp data frame. Extracts sequence number and signatures,
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
        inbound_sqn = self._get_inbound_seqnum(peer)
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
        logger.debug("inbound seq num updated", str(self._seq_num_map))
        return payload

    def saferecv(self, timeout: float | None = None, recv_from: SocketAddress | int = RCV_EVERYONE) -> bytes:
        """ 
        Attempts reception from an authorized socket. Blocks for at most 'timeout' seconds, then
        raises TimeoutError. If timeout is None (default), blocks forever (not recommended). 
        Non-Blocking behaviour can be achieved by setting the underlying socket to blocking(False)

        Data is rejected  if sequence number is not valid, or if signature is wrong. If a recv_from is
        provided, only data coming from that address will be accepted. You can alternatively pass the constants
        RCV_EVERYONE or RECV_OWN_PEER to the recv_from parameter to accept data respectively from every socket, or from the
        address of the set peer. Defaults to RCV_EVERYONE (just trusts signature) 
        """
        from_addr: SocketAddress | None = None
        if isinstance(recv_from, int):
            if recv_from == RCV_EVERYONE:
                from_addr = None    # kinda hacky, we change type to int
            elif recv_from == RCV_OWN_PEER:
                if self.peer is None:
                    raise ValueError("No peer set, cannot use RCV_OWN_PEER")
                from_addr = self.peer
        else:
            # properly resolve hostnames
            from_addr = self._resolve_peer(recv_from)

        start_t = time.time()

        while True:
            if timeout is not None:
                t_elapsed = (time.time() - start_t)
                if (t_elapsed >= timeout): break

                # only set timeout if timeout is given
                self.udp_sock.settimeout(max(0.0, timeout - t_elapsed))

            try:
                data, addr = self.udp_sock.recvfrom(self.MAX_RECV_BUFF_SIZE)
            except socket.timeout:
                # if this triggers, the loop should break on next iteration
                continue
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
            
        # all timeout errors are redirected here
        raise TimeoutError("saferecv timed out waiting for data from authorized sender")
    
    def set_peer(self, peer_addr: SocketAddress | None):
        # NOTE this might raise exception if hostname cannot be resolved
        self.peer = self._resolve_peer(peer_addr) if peer_addr is not None else None
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