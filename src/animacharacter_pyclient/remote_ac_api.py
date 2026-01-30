from __future__ import annotations
from typing import Iterable, Tuple, List, Literal
from enum import Enum
import socket as s
import time
import os
import logging
logger = logging.getLogger("remote_animacharacter")

from sesscli.client import ACRemoteClient
from animadummies.teodore import create_dummy
from animadummies.base_components import ActuatorGroup


class RECEPTION_STRATEGY(Enum):
    QUEUE = 1   # executes ALL animation packets in the order they arrive (server might lag behind if sender frequency > server frequency)
    LATEST = 2  # only executes latest animation packet

# port on which the pi server is hosting on
DEFAULT_PORT = 7000
CWD = os.getcwd()

class RemoteAnimacharacter:
    """
    Interface to a (remote) animacharacter.
    """

    def __init__(self, host_port=DEFAULT_PORT):
        self.client = ACRemoteClient()
        self.host_port = host_port
        self.mech: ActuatorGroup = create_dummy()

    def connect(self, ip: str, apikey: str) -> bool:
        """
        Attempts to connect and gain api access to an animatronic server.
        
        Params:
            ip (str) : ip address of the animatronic server.
            apikey (str) : password to gain access to the API. Unique to each animatronic.
        """
        success, msg = self.client.attempt_connection(ip, apikey: str, self.host_port)
        if not success:
            logger.warning(msg)
            return False

        if not authenticate(self.client, apikey):
            self.client.terminate_connection()
            logger.warning(f"Connection to server on {ip}:{self.host_port} was rejected: wrong api key.")
            return False
        
        self._finish_connection_init()
        logger.info(f"Connection to server on {ip}:{self.host_port} successfull.")
        return True

    def _finish_connection_init(self):
        """After client is connected and granted access to the api, this method initializes the final things.\n
        (calls pnpdev.begin())"""
        self.pnpdev.begin()

    def update_from(self, source: ActuatorGroup | Actuator):
        """
        Updates harware directly from source, internal 'mech' object is left unmodified (Less overhead).
        
        Call this method if you are performing lots of updates rapidly or if you don't want to alter the
        mech object interal to the class.
        """
        ...
    
    def switch_to_UDP(self):
        """
        Starts using udp for animation packets (default).
        
        Generally this is the best and only option for streaming animation data; switch to TCP only if frequency of
        updates is low and network is highly congested.
        """
        ...
    
    def switch_to_TCP(self):
        """
        Starts using tcp for animation packets.
        
        This is not recomended if you are streaming animation data. Only use tcp if you are performing low frequency
        updates (hardware response tests) or sending updates from a far away network. 
        """
        ...

    def _send_anim_packet(self, data: List[Tuple[int, int]]):
        """
        Sends animation packet to control the animatronic hardware.

        Data must be in the format: [(id_mask_1, value_1), (id_mask_2, value_2), ..., (id_mask_n, value_n)]
        where *id_mask* is the bitmask for that specific actuator, and *value* is the desired actuation value.
        """
        ...
    
    def _send_config_packet(self, data):
        """
        Sends hardware configuration packet.
        
        Used for exchanging low frequency informations such as motor control schemes or other options.
        """
        ...
    
    def _send_record_packet(self, data):
        """
        Sends 'record' packet. 

        Used for interfacing with the input stream capture and playback functionality of the animatronic.
        """
        ...

    
    def set_reception_strategy(self, type: RECEPTION_STRATEGY):
        """
        Chooses reception method (defaults to LATEST)
        
        type can be:
        - **RECEPTION_STRATEGY.LATEST** : only executes last received animation packet (default)
        - **RECEPTION_STRATEGY.QUEUE**  : executes ALL animation packets in the order they arrive (server might lag behind if sender frequency is
        higher than server frequency);
        
        Only use QUEUE for animation playback from client side (allthought ideally you would use the builtin record feature for this application)
        
        """
        ...
    
    def recorder_begin(self):
        """
        Starts recording incoming animation data and starting configurations.
        """
        ...
    
    def recorder_stop(self, filename: str):
        """
        Saves recording as "filename.rc"
        """
        ...
    
    def recording_rename(self, filename: str, newname: str):
        """
        Renames recording file.
        """
        ...
    
    def playback_recording(self, filename: str, loop: bool = True):
        """
        Begins playback of specified recording. 
        
        From the server's point of view, playback is an emulation of an input source. User inputs can still be
        sent and will be processed, although this might result in inconsistent playback if two actuators are trying to be moved at the 
        same time by both sources. Mainly use this feature to control smaller harware components such as LEDs, ears, etc...
        or make sure that two recordings playing at the same time do not have overlapping actuators.
        """
        ...
    
    def playback_stop(self):
        """
        Stops playback of current recording.
        """
        ...
    
    def get_available_recordings(self) -> Tuple[str]:
        """
        Returns a list of all the saved recordings in the server.
        """
        ...

    def download_recording(self, filename: str, destpath: str = CWD):
        """Downloads specified recording and saves it under 'destpath'"""
        ...
    
    def delete_recording(self, filename: str):
        """Deletes specified recording"""
        ...
    
    def upload_recording(self, localpath: str):
        """
        Uploads recording from 'localpath' to server.
        """

    def get_available_logs(self) -> Tuple[str]:
        """
        Returns a tuple containing all the saved logs on the server.
        """
        ...

    def download_logs(self, *log_names: str, folder: str = CWD):
        """
        Download all specified logs inside the given folder (defaults to current working directory)
        """
        ...
    
    def _file_transfer(self, request: Literal["upload", "download"], srcpath: str, dstpath: str):
        """
        Transfers file from src to dst. Allows transfer of ALL types of files.
        """
    
    def _file_operation(self, request: Literal["rename", "delete", "create"], path: str, *args, **kwargs):
        """
        Performs common file operations such as rename, delete, create
        """