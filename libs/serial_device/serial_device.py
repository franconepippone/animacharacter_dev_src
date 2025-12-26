from __future__ import annotations
from typing import Dict, Callable, Any, Tuple
from time import sleep, perf_counter_ns
from dataclasses import dataclass
import logging
from enum import Enum
import json

from utils import poll, Timer
from pySerialTransfer import pySerialTransfer as txfer
from pySerialTransfer.pySerialTransfer import Status, SerializableObj, BYTE_FORMATS, State


# -------------------- CONFIG CONSTANTS

LARGERX_CHUNK_TIMEOUT = 3.0 # chunks must be received AT MAX 3 seconds apart from each other


# -------------------- INTERNAL PACKETS IDS

PACKID_IDENT_RQST = 200
PACKID_IDENT_RESP = 201
PACKID_DIAGNOSTIC = 202
PACKID_PING = 203
PACKID_DEV_INFO_RQST = 209
PACKID_DEV_INFO_RESP = 210

# packets for large transfer
PACKID_LARGETX_BEGIN = 204
PACKID_LARGETX_CHUNK = 205
PACKID_LARGETX_BEGIN_RESP = 206
PACKID_LARGETX_ACK = 207
PACKID_LARGETX_END = 208

# ------------------------ PACKETS STRUCTURE:
# LARGE TRANSFER BEGIN:     uint32_t (tot_size)
# LARGE TRANSFER CHUNK:     uint32_t (offset) + remaining bytes (payload)
# LARGE TRANSFER END:       uint8_t (pack_id)

class LargeRxState(Enum):
    READY = 0
    RECVING = 1

# debug hooks
PACKID_DEBUG_TRIGGER_IDENT_RQST = 220
PACKID_DEBUG_TRIGGER_LARGE_TX = 221


@dataclass(slots=True, frozen=True)
class Packet:
    """
    Packet dataclass for data received from a SerialDevice
    """
    id: int
    size: int
    data: bytes

@dataclass
class SerialTransferInitConfig:
    """
    Class used as an optional argument to SerialDevice to 
    have full access on the constructor of the underlying
    SerialTransfer object (advanced use).
    """

    port: str
    baud: int = 115200
    restrict_ports: bool = True
    debug: bool = True
    byte_format: str = BYTE_FORMATS['little-endian']
    timeout: float = 0.05
    write_timeout: float | None = None

# ---------------------- UTILITY

def validate_pack_id(id: int) -> bool:
    #XXX TODO
    return True


# ---------------------- INTERNAL PACK IDS HANDLERS

def _ident_rqst_handler(dev: SerialDevice, pck: Packet):
    # sends an ident response
    dev.send_object(dev.device_name, PACKID_IDENT_RESP)
    print("GOT IDENT RQST: ", pck)

def _ping_handler(dev: SerialDevice, pck: Packet):
    respond = bool(pck.data[0])
    print(f"GOT PING {'REQUEST' if respond else 'RESPONSE'}")
    if respond:
        dev.send_object(False, PACKID_PING)
        return False
    
    return True

def _on_large_txf_chunk(dev: SerialDevice, pck: Packet):

    if dev._large_rx_state != LargeRxState.RECVING: return
    
    # if too much time has passed sice latest chuck
    if dev._large_rx_timer.timed_out():
        dev._large_rx_state = LargeRxState.READY
        print("TIMED OUT")
        return

    mv = memoryview(pck.data)
    offset = int.from_bytes(mv[:4], byteorder="little", signed=False)
    chunk_size = len(mv[4:])
    # we could use offset here, but it should be the same
    dev._large_rx_buff[offset:offset + chunk_size] = mv[4:]   # mv[4:] is the rest of the chunk
    dev._large_rx_timer.start() # restart timer, so we can recv next chunk

    dev.send_object(chunk_size, PACKID_LARGETX_ACK) # sends received size, this is not used as of now by the large transfer sender
    print("GOT LARGE TXF CHUNK: offset:", offset, "chunk_size:", chunk_size, pck)

def _on_large_txf_begin(dev: SerialDevice, pck: Packet):

    if dev._large_rx_state != LargeRxState.READY: return; print("LARGE TXG BEGIN RQST FAILED")
    
    tot_size = int.from_bytes(pck.data[:4], byteorder="little", signed=False)
    # initializes bytearray
    dev._large_rx_buff = bytearray(tot_size)
    dev._large_rx_state = LargeRxState.RECVING
    dev.send_object(True, PACKID_LARGETX_BEGIN_RESP)    # sends respond packet
    dev._large_rx_timer.start()
    print("GOT LARGE TXF BEGIN: size:", tot_size)

def _on_large_txf_end(dev: SerialDevice, pck: Packet):

    if dev._large_rx_state != LargeRxState.RECVING: return

    original_pack_id = int.from_bytes(pck.data[:4], byteorder="little", signed=False)
    dev._add_pack_to_buff(dev._large_rx_buff, original_pack_id)
    print("GOT LARGE TXF END: pack id:", original_pack_id)

class SerialDevice:
    """
    Docstring for SerialDevice
    """

    def __init__(self, 
            device_name: str,
            port: str,
            baud: int,
            full_config: SerialTransferInitConfig | None = None
        ) -> None:
        """
        Create a Serial Device Object.
        
        :param device_name: name of the device (used for identification requests)
        :type device_name: str
        :param port: Serial port name
        :type port: str
        :param baud: Serial baud rate
        :type baud: int
        :param full_config: Optional configuration object, provides an interface to the full constructor
                of the underlying SerialTransfer object. This might be used for more advanced fine tuning
        :type full_config: SerialTransferInitConfig | None
        """
        self.device_name = device_name
        self.pack_buff: list[Packet] = []
        self._tx_buff_idx = 0
        self.pack_handlers: Dict[int, Callable[[SerialDevice, Packet], Any]] = {}
        self.peer_name: str | None = None

        # large transfer
        self._large_rx_buff = bytearray(1)
        self._large_rx_state: LargeRxState = LargeRxState.READY
        self._large_rx_timer: Timer = Timer(LARGERX_CHUNK_TIMEOUT)

        # handler for handling indent requests / response from peer device
        self.bind_cb(PACKID_IDENT_RQST, _ident_rqst_handler)
        self.bind_cb(PACKID_PING, _ping_handler)
        # handlers for large transfer protocol
        self.bind_cb(PACKID_LARGETX_BEGIN, _on_large_txf_begin)
        self.bind_cb(PACKID_LARGETX_CHUNK, _on_large_txf_chunk)
        self.bind_cb(PACKID_LARGETX_END, _on_large_txf_end)

        if not full_config:
            self.txf = txfer.SerialTransfer(port, baud=baud)
        else:
            self.txf = txfer.SerialTransfer(
                port=full_config.port,
                baud=full_config.baud,
                restrict_ports=full_config.restrict_ports,
                debug=full_config.debug,
                byte_format=full_config.byte_format,
                timeout=full_config.timeout,
                write_timeout=full_config.write_timeout
            )

    ### ------------- API METHODS -----------------

    def request_info(self, timeout: float = 5.0) -> dict[str, Any] | None:
        """
        Request in depth information about the device (build info, board info, date/time info, etc..)
        
        :param timeout: maximum time this function will block and wait for a response
        :type timeout: float
        :return: Returns a json python dictionary containing the device info.
        :rtype: dict[Any, Any] | None
        """
        self.send(PACKID_DEV_INFO_RQST, 1)
        # we poll the device and check for packets
        for _ in poll(timeout, 0.001):
            p = self.poll()
            if p and p.id == PACKID_DEV_INFO_RESP:
                try:
                    json_info_str = p.data[:-1].decode() # we get rid of the null terminator
                    json_data = json.loads(json_info_str)
                    return json_data
                except Exception as e:
                    logging.exception(e)
                    return None
        

    def ping(self, timeout: float = 5.0) -> float | None:
        """
        Attempts pinging the device. This can be used as a hearthbeat,
        to check if device is connected and working properly.
        
        :param timeout: maximum timeout (blocking)
        :type timeout: float
        :return: latency (round trip time) in ms if ping was succesfull, else None
        :rtype: float | None
        """
        self.send_object(True, PACKID_PING)
        start = perf_counter_ns()
        # we poll the device and check for packets
        for _ in poll(timeout, 0.00001):
            p = self.poll()
            if p and p.id == PACKID_PING:
                end = perf_counter_ns()
                return (end - start) / 1000000
        
        return None

    def request_peername(self, timeout: float = 5.0) -> str | None:
        """
        Sends an identification request to peer; if peer is active and polling,
        it should respond with it's device name. All other packets are discarded 
        while this is executing. Callbacks are still active.
        
        :param timeout: maximum timeout (blocking)
        :type timeout: float
        :return: self.peer_name (None if not set)
        :rtype: str | None
        """
        self.send_object(self.device_name, PACKID_IDENT_RQST)
        # we poll the device and check for packets
        for _ in poll(timeout, 0.01):
            p = self.poll()
            if not p:
                # if no packet received
                continue
            
            if p.id == PACKID_IDENT_RESP:
                try:
                    self.peer_name = p.data.decode()
                    return self.peer_name
                except Exception as e:
                    logging.exception(e)
                    return None
                    
    
    ### ------------- SERIAL MANAGEMENT ---------------------
    
    def open(self, timeout: float = 0) -> bool:
        """
        Connects to the serial device. If timeout is > 0,
        tries until timeout expires.
        
        :param self: Description
        :param timeout: Maximum wait time in seconds for the connection to open 
                        (value is in seconds but is snapped no nearest increment of 100ms)
        :type timeout: float
        :return: If True, the serial connection is enstablished; False if otherwise.
        :rtype: bool
        """
        if self.txf.open(): return True
        # timeout is in seconds, each second is 10 loops of 100ms sleep
        assert timeout >= 0

        for _ in poll(timeout, 0.1):
            if self.txf.open(): return True

        # if still has not opened, return false
        return False

    def close(self):
        self.txf.close()

    ### ------------------- LARGE TRANSFER -------------------
    


    
    ### ------------------- SENDING -------------------

    def send_object(self, obj: SerializableObj | bytes, pack_id: int) -> bool:
        """
        Sends an object to the peer device (equivalent to 
        queue_object(obj) and send()).
        
        :param obj: object to send (must be of type SerializableObj)
        :type obj: SerializableObj
        :param pack_id: Id of the sent packet
        :type pack_id: int
        :return: Wheter or not the operation ws succesfull
        :rtype: bool
        """
        if isinstance(obj, (bytes, bytearray, memoryview)):
            size = self.txf.tx_bytes(obj)
        else:
            size = self.txf.tx_obj(obj)
        
        if isinstance(size, int):
            return self.txf.send(size, pack_id)
        return False

    def send(self, pack_id: int, size: int | None = None) -> bool:
        """
        Sends all the binary data accumulated in the buffer using queue_object 
        (uses internal size counter by default).   
        Size can be overwritten to send a custom amount of data.
        
        :return: Wheter or not the operation was succesfull
        :rtype: int
        """
        if size:
           self._tx_buff_idx = size 
        suc = self.txf.send(self._tx_buff_idx, pack_id) 
        self._tx_buff_idx = 0   # clear the tx buffer index
        return suc

    def queue_object(self, obj: SerializableObj | bytes) -> int:
        """
        Accumulate object in the rx buffer. Multiple calls to this method will automatically
        serialize and stack up objects in the rx buffer. Call send() to send all of them
        and clear the buffer.
        
        :param obj: Object to send (must be of type SerializableObj)
        :type obj: SerializableObj
        :return: Returns the idx in the tx buffer at which the object has written the last byte + 1
        :rtype: int
        """
        if isinstance(obj, (bytes, bytearray, memoryview)):
            next_idx = self.txf.tx_bytes(obj)
        else:
            next_idx = self.txf.tx_obj(obj)

        if isinstance(next_idx, int):
            self._tx_buff_idx = next_idx
        # else:
        #   serialization has failed (invalid object has been passed)

        return self._tx_buff_idx
    
    ### --------------- RECVING ---------------

    def _add_pack_to_buff(self, data: bytes, pid: int):
        self.pack_buff.append(Packet(pid, len(data), data))

    def recv(self) -> bool:
        """
        Receives packets into internal packet buffer. To be called as frequently
        as possible. Calls available()

        :return: True if a packet
        has been received, False otherwise.
        :rtype: bool
        """
        if self.available():
            bb = self.txf.rx_bytes()
            pid = self.txf.get_current_packed_id()
            self._add_pack_to_buff(bb, pid)
            return True
        return False

    def available(self) -> int:
        """
        Process the serial stream and parses incoming packets.
        
        :return: 0 if no packet has been received, otherwise
            the received packet payload size.
        :rtype: int
        """
        return self.txf.available()
    
    def get_oldest_packet(self) -> Packet | None:
        """
        Returns oldest received packet from internal packet buffer.
        
        :return: Packet object or None if no packets are available
        :rtype: Packet | None
        """
        if len(self.pack_buff) > 0:
            return self.pack_buff.pop(0)

    def wait_packet(self, timeout: float = 1, polling_period: float = 0.2) -> Packet | None:
        """
        Block until a packet arrives and returns it. Internally calls poll()
        
        :param timeout: maximum wait time
        :type timeout: float
        :param polling_period: Period at which the serial stream is checked for packets
        :type polling_period: float
        :return: A Packet object if a packet was received, else None if timeout expires
        :rtype: Packet | None
        """
        assert timeout > 0 and polling_period > 0.001

        for _ in poll(timeout, polling_period):
            if pck := self.poll():
                return pck

        return None


    ### ------------ PACKET HANDLING

    def bind_cb(self, pack_id: int, cb: Callable[[SerialDevice, Packet], Any]) -> bool:
        """
        If packet id is valid, binds the cb callable to that packet id.
        This is called automatically when using poll()
        
        :param pack_id: integer byte id of packet
        :type pack_id: int
        :param cb: Callable handler function / method
        :type cb: Callable[[Packet], Any]
        :return: True if handler was binded, else False
        :rtype: bool
        """
        if validate_pack_id(pack_id):
            self.pack_handlers[pack_id] = cb
            return True
        return False


    def poll(self) -> Packet | None:
        """
        Processes the serial streams, parses packets and processes them
        (calls callbacks if set). If no callbacks are set, packet is left
        unprocessed and is returned, otherwise None is returned.  
        Internally, this calls recv() and process_packet().
        
        :param self: Description
        :return: A Packet object if a packet was received, else None if timeout expires
        :rtype: bool
        """
        self.recv()

        # this structure allows processing of packets injected in the buffer internally from 
        # more sources (not just recv; for example, used in large transfers)
        while pck := self.get_oldest_packet():
            if not self.process_packet(pck):
                return pck
        
        return None

    def process_packet(self, packet: Packet) -> bool:
        """
        Calls respective packet handler callback if set.
        
        :param packet: received packet
        :type packet: Packet
        :return: True if handler was found, False if not
        :rtype: bool
        """
        if packet.id in self.pack_handlers:
            # if packet handler returns true, packet can be consumed by poll even after handler ends
            keep = self.pack_handlers[packet.id](self, packet)
            return True and not keep
        return False

    def get_transport_status(self) -> Tuple[State, Status]:
        """
        This exposes an interface to the low level status and state of
        the undelying serial transfer object.

        :return: tuple of (State, Status), where state is the state of type State(Enum) of the SerialTransfer finite state machine, and Status is the status of type Status(Enum) of the SerialTransfer reception.
        :rtype: tuple[State, Status]
        """
        
        return (self.txf.state, self.txf.status)


    def __enter__(self):
        # setup code goes here
        return self

    def __exit__(self, exc_type, exc, tb):
        # teardown code goes here
        # return True to suppress exceptions, False to propagate
        self.close()
        return False