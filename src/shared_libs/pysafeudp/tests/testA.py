"""
Run this first in a terminal, then run testB.py in another terminal to see the echo.
"""


from pysafeudp import SafeUdpSock
import pysafeudp

import logging

# Configure the logger
logging.basicConfig(
    level=logging.INFO,              # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s"
)


print("listening on port 8080")
with SafeUdpSock(b'ciccio', 8080) as sock:
    sock.set_peer(("localhost", 8000))

    while True:
        resp = sock.recv()
        if not resp:
            print("timed")
            continue
        addr = sock.get_latest_sender_address()
        print("received:", resp, "from", addr)
        #out = sock.send(resp + b" echo", to=addr)
        #print("sent echo:", out)
        print(sock._seq_num_map)
