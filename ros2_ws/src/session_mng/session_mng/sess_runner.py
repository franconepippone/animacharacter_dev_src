
import threading
import time
from sess_creator import SessionContext
import logging

SESS_CREATE_SERVER_PORT = 9000


class SessionRunner:
    def __init__(self, logger):
        self.logger = logger
        self.crnt_ctx: SessionContext | None = None
    
    def run(self, ctx: SessionContext):
        self.crnt_ctx = ctx
        thread = threading.Thread(target=self._run_session, args=(ctx,))
        thread.start()
        # also start the stream (udp) packet forwarder here?

    def _run_session(self, ctx: SessionContext):
        
        

        # implement session running logic here


        








def main():
    logger = logging.getLogger(__name__)



    # INITIALIZE HARDWARE CONNECTION ========================================================================

    hardware_server = hwmng.create_connection("ipc url", "key (a che cazzo serve)")   # blocks until connection is acquired. The hwmng process is spawned separately
    logger.info("Hardware connection established")



    # INITIALIZE RECORDING SERVER ==============================================================================

    rec_server = rec_server.start()  # spawn a subprocess
    ok = rec_server.wait_boot()  # waits until a boot ok signal is received (op)
    if not ok:
        # signal to leds ?
        logger.warning("Recording server failed to start, moving on for now...")
    else:
        logger.info("Recording server started successfully")



    # INITIALIZE SESSION MANAGER AND HTTP IPC SERVER FOR SESSION CREATION REQUESTS =============================
    
    ssmng = SessionManager(max_sessions=1)

    sess_creation_rqst_handler = HTTPSessionCreationServer(ssmng)
    t = sess_creation_rqst_handler.run_threaded(port=SESS_CREATE_SERVER_PORT)  # runs in background thread
    t.join(1)  # makes sure thread started properly

    if t.is_alive():
        logger.info("Session creation HTTP IPC server started on port %d", SESS_CREATE_SERVER_PORT)
    else:
        logger.error("Session creation HTTP IPC server failed to start")
        return
    


    # ===================================================================================================

    # BELOW IS THE MAIN LOOP OF THE WHOLE CONTROL SYSTEM
    # this loop waits for new sessions to be created, and runs them until they end

    # ===================================================================================================

    while True:
        sess_ctx = ssmng.wait_for_session()    # blocks until a new session is created
        if sess_ctx is None:
            logger.info("no new session created - timeout expired")
            continue

        time.sleep(0.5)   # give time for the auth server to send the session creation request to the user, and for the user to setup a new session on their end

        outcome = run_session(sess_ctx, ssmng)   # returns when session ends or crashes  

        logger.info(outcome)    # logs outcome or brief summary of the session (duration, address, etc...)

        #sess_ctx = session_queue.get(block=True)   # blocks until a new session is created


#@threaded
def bin_packet_forwader(conn, session_running: threading.Event):
    """Forwards binary motionframe packets directly to the hardware unit
    """
    hardware_server = hwmng.get_current_connection()
    
    while session_running.is_set():
        motionframe = conn.recv(block=True) # wrap in try/except for timeout error

        # maybe perform some very basic checks to ensure data is valid and is a motion frame

        # in ros just publish the message here
        hardware_server.control(motionframe)
        if rec_server.is_recording():
            rec_server.record(motionframe)

def run_session(ctx: SessionContext, SM: SessionManager):

    dev = ctx.pnp_dev   # maybe create this here, to decouple the session manager 
    bin_conn = ctx.udp_sock

    session_running = threading.Event()
    t = bin_packet_forwader(bin_conn, session_running) # runs threaded

    while session_running.is_set():
        packet = dev.recv_packet(block=True)
        status = process_packet(packet)

        # client has requested end of session
        if status.end:
            session_running.clear()
            break
    
    SM.close_session(sess_id=ctx.sess_id)   # terminates connections

def process_packet(packet) -> bool:
    match packet:
        case SessionEnd():
            return True




if __name__ == "__main__":
    #main()

    ssmng = SessionManager(max_sessions=1)

    sess_creation_rqst_handler = HTTPSessionCreationServer(ssmng)
    t = sess_creation_rqst_handler.run_threaded(port=SESS_CREATE_SERVER_PORT)  # runs in background thread
    t.join()