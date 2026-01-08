"""
Run this after starting testA.py in another terminal.
"""

from pysafeudp import SafeUdpSock
import pysafeudp
import time
import threading
import json

import logging

# Configure the logger
logging.basicConfig(
    level=logging.INFO,              # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s"
)


OWN_PORT = 8000
PEER_PORT = 8080




# TEST WITH WRONG KEY

with SafeUdpSock(b'wrong key', OWN_PORT) as sock:
    sock.set_peer(("localhost", PEER_PORT))

    print("sending to localhost:8080")
    sock.safesend(f"WRONG KEY".encode())
    try:
        resp = sock.saferecv(timeout=1, recv_from=pysafeudp.RCV_EVERYONE)
    except Exception as e:
        print("no response received (as expected with wrong key)", e)


def spam_socket():
    with SafeUdpSock(b'wrong key', OWN_PORT + 1) as sock:
        print(f"spamming localhost:{PEER_PORT} with wrong key")
        while True:
            sock.safesend(f"WRONG KEY SPAM".encode(), to=("localhost", PEER_PORT))
            #time.sleep(0.1)

# to test if system is robust to spamming
#threading.Thread(target=spam_socket, daemon=True).start()
time.sleep(1)

# TEST WITH CORRECT KEY

with SafeUdpSock(b'ciccio', OWN_PORT) as sock:
    print(f"sending to localhost:{PEER_PORT}")
    i = 0

    #sock.set_peer(("localhost", 8080))

    # we are adding persistance between multiple runs of the outbound seq number; this
    # means that even if this script is stopped and restarted, the "session" with the other
    # peer is restarted immediately (the other peer is expecting a seqnum of prev + 1, but
    # we saved the prev + 1 value in the json file, so we know it and we can override it, 
    # it would normally start at 0)

    with open("B_session.json", "r") as f:
        sess = json.load(f)
    sock.override_outbound_seqnum(("127.0.0.1", PEER_PORT), sess["outbound"])
    
    while True:
        sock.safesend(f"porcoddio {i}".encode(), to=("localhost", PEER_PORT))
        print("sent:", f"porcoddio {i}")
        try:
            resp = sock.saferecv(timeout=0.2, recv_from=("localhost", PEER_PORT))
            print("received:", resp)    
        except Exception as e:
            print("no response received", e)
        
        sess["outbound"] = sock._get_outbound_seqnum(("127.0.0.1", PEER_PORT))
        with open("B_session.json", "w") as f:
            json.dump(sess, f)

        print(sock._seq_num_map, "\n")
        time.sleep(1)
        i += 1
