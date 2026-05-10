from dataclasses import dataclass
import secrets
import asyncio

from interfaces.msg import MotionframeArray

from .session import SessionResourceManager, SessionRunner
from .session.resource_manager import LoggerLike, LoggerLike, SessionDestructionError, SessionCreationError
from .packet_formats import *

from authmsg import PeerTCP, PeerUDP
from packetcodec import PacketDecoder, UnknownPacket

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
    """Create and destroy session transport resources."""

    def destroy(self, context: ACSessionContext):
        """Release all resources held by a session context."""
        try:
            context.tcp_sock.close()
            context.stream_sock.close()
        except Exception as exc:
            raise SessionDestructionError() from exc

    def create(self, args: ACSessionCreationArguments) -> ACSessionContext:
        """Allocate transport resources and return a session context."""
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
            codec.register_packet(MyPacket)
            # TODO configure this..

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

class ACSessionRunner(SessionRunner[ACSessionContext]):
    def __init__(self, motionframe_publisher: Publisher, config_publisher: Publisher, logger: LoggerLike | None = None) -> None:
        super().__init__(logger=logger)
        self.motionframe_publisher = motionframe_publisher
        self.config_publisher = config_publisher

    def run(self, ctx: ACSessionContext) -> None:
        """Core session logic, runs in a background thread. Should return when session ends."""
        asyncio.run(self._run_main(ctx))

    ####
    #### --------------------------- SESSION IMPLEMENTATION ---------------------------
    ####                              asyncio - based

    # entrypoint
    async def _run_main(self, ctx: ACSessionContext):
        # once this returns, session ends.
        all_stop = asyncio.Event()

        loop = asyncio.get_running_loop()
        t1 = loop.create_task(self._motionframe_forwarder(ctx, all_stop))
        t2 = loop.create_task(self._main_session_receiver(ctx, all_stop))
        
        await asyncio.gather(t1, t2)
    
    async def _main_session_receiver(self, ctx: ACSessionContext, stop_event: asyncio.Event):
        
        peer_tcp = ctx.tcp_sock
        peer_tcp.set_timeout(1.0, 1.0)

        while not stop_event.is_set():
            # should never raise
            msg = await peer_tcp.arecv()

            self.logger.info(f"got {msg}")

            packet = ctx.codec.parse_bytes(msg)
            match packet:
                case MyPacket():
                    ...
                case UnknownPacket():
                    self.logger.warning('Unknown packet received')

            # handle packets



    async def _motionframe_forwarder(self, ctx: ACSessionContext, stop_event: asyncio.Event):
        """Receive motionframes from the stream socket and republish them in ros2 topics."""

        peer = ctx.stream_sock
        peer.set_timeout(1.0)

        while not stop_event.is_set():
            try:
                motionframes_raw = await peer.arecv()
            except Exception as exc:
                self.logger.error(f"Error receiving motionframes: {exc}")
                continue
            
            if motionframes_raw == b"":
                continue # either timeout or invalid message
            
            self.logger.info(f"got {motionframes_raw}")

            # TODO convert motionframes raw 
            motionframe_message = MotionframeArray()
            self.motionframe_publisher.publish(motionframe_message)

        stop_event.set()

    ###### --------------------------------------
