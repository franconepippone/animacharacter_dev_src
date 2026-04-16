# Use this to talk to this simulator from python

```python
class PeerUDP:
	"""Simple UDP peer class to send packets to a peer
	"""

	def __init__(self, peer_addr: Tuple[str, int]):
		self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.s.bind(("", 0))
		#self.s.setblocking(True)

		self.host_addr = self.s.getsockname()
		self.peer_addr = peer_addr

	def send(self, packet: bytes) -> None:
		#print("sending", packet, "to", self.peer_addr)
		self.s.sendto(packet, self.peer_addr)

	def recv(self, timeout: float = 0) -> Optional[bytes]:
		# Wait for readability
		ready, _, _ = select.select([self.s], [], [], timeout)
		if not ready:
			return None

		try:
			packet, addr = self.s.recvfrom(2048)
		except BlockingIOError:
			return None

		if addr == self.peer_addr:
			return packet

		return None


SIMULATOR_ADDRESS = "127.0.0.1", 500

# OR ON WSL -> WIN:
# >>> ip route show | grep -i default | awk '{ print $3}'
# SIMULATOR_ADDRESS = "172.26.32.1", 500

PACKID_MOTION = b'\x00'
PACKID_PING = b'\x01'

def send_motion_packet(self, axis_id: int, value: float):
		# packets structure: uint8 (packid) | uint8 (axis_id) | float32 (value) 
		encoded = PACKID_MOTION + struct.pack("!Bf", axis_id, value)
		self.peer.send(encoded)

```
