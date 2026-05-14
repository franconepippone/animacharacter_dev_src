"""
In this files all abstract classes from "session_mng/session" package are subclasses,
implementing the specific session logic for an animacharacter session.
"""


from dataclasses import dataclass
from typing import Callable
import secrets
import asyncio
import time
from interfaces.msg import MotionframeArray
from std_msgs.msg import String

from authmsg import PeerTCP, PeerUDP
from packetcodec import PacketDecoder, UnknownPacket

from commons.network.udp_motionframe_schema import decode_motionframe_packet_into_arrays
from commons.network.packet_schemas import (
    HeartBeatPacket,
    ConfigurationPacket,
    SessionEndRequestPacket,
)


from .session import SessionResourceManager, SessionRunner, SessionManager
from .session.resource_manager import LoggerLike, SessionDestructionError, SessionCreationError



# ====================
# SESSION CONTEXT
# ====================

@dataclass(frozen=True)
class ACSessionCreationArguments:
    client_ip: str
    client_udp_port: int


@dataclass
class ACSessionContext:
    """
    Container class for a session's data: includes open sockets, ports, secret keys/tokens.
    This is a pure data container and does not implement session lifecycle logic.
    """
    tcp_sock: PeerTCP
    tcp_port: int
    stream_sock: PeerUDP
    stream_port: int
    codec: PacketDecoder
    session_secret: str


# ====================
# SESSION RESOURCE MANAGER IMPLEMENTATION
# ====================

class ACSessResourceMng(SessionResourceManager[ACSessionContext]):
    """Create and destroy a AC session context. This object creates and safely destroys all resources
    necessary to run a AC session, such as two data channels (TCP and UDP) for reception of
    data from the client.
    """

    def destroy(self, context: ACSessionContext):
        """Release all resources held by a session context."""
        try:
            context.tcp_sock.close()
            context.stream_sock.close()
        except Exception as exc:
            raise SessionDestructionError() from exc

    def create(self, args: ACSessionCreationArguments) -> ACSessionContext:
        """Allocate resources and return a session context."""
        sess_sock = None
        stream_sock = None

        try:
            session_secret = secrets.token_urlsafe(64)

            sess_sock = PeerTCP(session_secret)
            sess_sock.listen(0)
            sess_port = sess_sock.local_address[1]
            
            stream_sock = PeerUDP(0, psk=session_secret)
            stream_sock.dial(args.client_ip, args.client_udp_port)
            stream_port = stream_sock.local_address[1]

            codec = PacketDecoder()
            codec.register_packets(
                HeartBeatPacket,
                SessionEndRequestPacket,
                ConfigurationPacket
            )

            ctx = ACSessionContext(
                tcp_sock=sess_sock,
                tcp_port=sess_port,
                stream_sock=stream_sock,
                stream_port=stream_port,
                codec = codec,
                session_secret=session_secret
            )
            self.logger.info(f"Session created successfully, ctx={ctx}")
            return ctx

        except Exception as exc:
            try:
                if sess_sock: sess_sock.close()
            except Exception:
                pass
            try:
                if stream_sock: stream_sock.close()
            except Exception:
                pass
            raise SessionCreationError() from exc


# ====================
# SESSION RUNNER IMPLEMENTATION
# ====================

from rclpy.publisher import Publisher


@dataclass
class MetricsTracker:
    rec_tcp: int = 0
    rec_udp: int = 0
    motion_cmds: int = 0

    def reset(self):
        self.rec_tcp = 0
        self.rec_udp = 0
        self.motion_cmds = 0

class ACSessionRunner(SessionRunner[ACSessionContext]):
    
    class params:
        HEARTBEAT_TIMEOUT_SEC = 10

    def __init__(self, motionframe_publisher: Publisher, config_publisher: Publisher, logger: LoggerLike | None = None) -> None:
        super().__init__(logger=logger)
        self.motionframe_publisher = motionframe_publisher
        self.config_publisher = config_publisher
        self.metrics = MetricsTracker()

    def run(self, ctx: ACSessionContext) -> None:
        """Core session logic, runs in a background thread. Should return when session ends."""
        asyncio.run(self._run_main(ctx), debug=True)

    ####
    #### --------------------------- SESSION IMPLEMENTATION ---------------------------
    ####                              asyncio - based

    # entrypoint
    async def _run_main(self, ctx: ACSessionContext):
        # once this returns, session ends.
        all_stop = asyncio.Event()

        self.heartbeat_deadline = time.time() + self.params.HEARTBEAT_TIMEOUT_SEC

        loop = asyncio.get_running_loop()

        await asyncio.gather(
            loop.create_task(self._motionframe_forwarder(ctx, all_stop)),
            loop.create_task(self._main_packet_handler(ctx, all_stop)),
            loop.create_task(self._brackground_session_controller(all_stop))
        )
    
    async def _brackground_session_controller(self, stop_event: asyncio.Event):
        while not stop_event.is_set():
            last_time = time.time()
            await asyncio.sleep(1.0)
            delta_time = time.time() - last_time # exact computation

            # compute metrics
            rec_tcp_per_second = self.metrics.rec_tcp / delta_time
            rec_udp_per_second = self.metrics.rec_udp / delta_time
            motion_cmds_per_second = self.metrics.motion_cmds / delta_time
            self.metrics.reset()
            self.logger.info(f"Metrics: {rec_tcp_per_second:.2f} tcp/s  {rec_udp_per_second:.2f} udp/s {motion_cmds_per_second} cmd/s") # eventually we will publish this on /diagnostics

            # check for heartbeat
            if time.time() > self.heartbeat_deadline:
                stop_event.set()
                self.logger.warning("Missed heartbeat, assuming client is dead. Terminating session...")

    async def _main_packet_handler(self, ctx: ACSessionContext, stop_event: asyncio.Event):
        
        metrics = self.metrics
        peer_tcp = ctx.tcp_sock
        peer_tcp.set_timeout(5.0, 1.0)

        while not stop_event.is_set():
            # should never raise, only return on regular intervals
            msg = await peer_tcp.arecv()
            if msg == b"": 
                continue

            metrics.rec_tcp += 1 # track stat
            packet = ctx.codec.parse_bytes(msg)
            match packet:
                case ConfigurationPacket():
                    if not packet.valid:
                        self.logger.warning(f"Got config packet containing invalid json: {packet.json_str}")
                        continue

                    self.logger.info(f"Got valid config packet")
                    msg = String()
                    msg.data = packet.json_str
                    self.config_publisher.publish(msg)

                case SessionEndRequestPacket():
                    self.logger.warning("Client requested session termination. Terminating session...")
                    stop_event.set()

                case HeartBeatPacket():
                    now = time.time()
                    last_heartbeat = self.heartbeat_deadline - self.params.HEARTBEAT_TIMEOUT_SEC
                    time_since_last = now - last_heartbeat             
                    self.heartbeat_deadline = time.time() + self.params.HEARTBEAT_TIMEOUT_SEC
                    self.logger.info(f'Got heartbeat, time since last was {time_since_last:.2f} seconds.')
                
                case UnknownPacket():
                    self.logger.warning(f'Unknown packet received, data = {packet._raw_bytes}')
                
                case _:
                    self.logger.warning(f'Handler missing for packet: {packet}')



    async def _motionframe_forwarder(self, ctx: ACSessionContext, stop_event: asyncio.Event):
        """Receive motionframes from the stream socket and republish them in ros2 topics."""

        metrics = self.metrics
        peer = ctx.stream_sock
        peer.set_timeout(2.0)

        while not stop_event.is_set():
            try:
                motionframe_raw = await peer.arecv()
            except Exception as exc:
                self.logger.error(f"Error receiving motionframes: {exc}")
                continue
            
            if motionframe_raw == b"":
                continue # either timeout or invalid message
            

            # uses arrays because python rosldi expects them
            motionframe_message = MotionframeArray()
            arr_ids, arr_values = decode_motionframe_packet_into_arrays(motionframe_raw)
            motionframe_message.ids = arr_ids
            motionframe_message.values = arr_values
            self.motionframe_publisher.publish(motionframe_message)

            metrics.rec_udp += 1 # track stat
            metrics.motion_cmds += len(arr_ids)

        stop_event.set()

    ###### --------------------------------------




def create_session_manager(
        motionframe_publisher: Publisher, 
        config_publisher: Publisher,
        check_session_creation_criteria: Callable[[], bool],
        logger_resource_manager: LoggerLike, 
        logger_session_runner: LoggerLike
    ):
    """Utility method to build a configured session manager to run AC sessions."""
    return SessionManager(
        sess_resource_manager=ACSessResourceMng(logger=logger_resource_manager),
        sess_runner=ACSessionRunner(
            motionframe_publisher, 
            config_publisher,
            logger=logger_session_runner
        ),
        session_creation_criteria=check_session_creation_criteria
    )