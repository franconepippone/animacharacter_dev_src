extends Node

var udp: PacketPeerUDP = PacketPeerUDP.new()
const PORT: int = 500

const PACKID_MOTION: int = 0x00
const PACKID_PING: int = 0x01

func _ready() -> void:
	var err = udp.bind(PORT)
	if err != OK:
		push_error("Failed to bind on UDP port %d" % PORT)
		return
	
	print("Listening on UDP port %d" % PORT)


func _process(_delta: float) -> void:
	while udp.get_available_packet_count() > 0:
		var packet: PackedByteArray = udp.get_packet()
		var ip: String = udp.get_packet_ip()
		var port: int = udp.get_packet_port()
		_handle_packet(packet, ip, port)


func _handle_packet(packet: PackedByteArray, ip: String, port: int) -> void:
	if packet.is_empty():
		return

	var packid: int = packet[0]

	match packid:
		PACKID_MOTION:
			_decode_motion(packet)
		PACKID_PING:
			_handle_ping(ip, port)
		_:
			print("Unknown packet ID: %d" % packid)


func _decode_motion(packet: PackedByteArray) -> void:
	# Layout:
	# [0] packid (u8)
	# [1] axisid (u8)
	# [2..5] float32 big-endian

	if packet.size() < 6:
		print("Invalid motion packet size")
		return

	var axis_id: int = packet[1]

	var value_bytes: PackedByteArray = packet.slice(2, 6)
	value_bytes.reverse() # only if incoming data is big-endian
	var value := value_bytes.decode_float(0)

	print("Motion:", axis_id, value)


func _handle_ping(ip: String, port: int) -> void:
	print("Received ping from %s:%d" % [ip, port])

	# Set destination before replying
	udp.set_dest_address(ip, port)

	var reply := PackedByteArray([PACKID_PING])
	udp.put_packet(reply)
