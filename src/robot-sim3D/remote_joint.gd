extends Generic6DOFJoint3D

enum InputFormat {
	ANGLE, # pure agle in degrees
	NORMALIZED_SYMMETRIC, # [-1,1]
	NORMALIZED_POSITIVE # [0,1]
}

@export_group("X Axis")
@export var axis_x_name: String = "/"
@export_range(-180.0, 180.0, 0.1) var x_min_angle: float = -45.0
@export_range(-180.0, 180.0, 0.1) var x_max_angle: float = 45.0
@export var input_format_x: InputFormat
@export var negate_input_x: bool = false


@export_group("Y Axis")
@export var axis_y_name: String = "/"
@export_range(-180.0, 180.0, 0.1) var y_min_angle: float = -45.0
@export_range(-180.0, 180.0, 0.1) var y_max_angle: float = 45.0
@export var input_format_y: InputFormat
@export var negate_input_y: bool = false

@export_group("Z Axis")
@export var axis_z_name: String = "/"
@export_range(-180.0, 180.0, 0.1) var z_min_angle: float = -45.0
@export_range(-180.0, 180.0, 0.1) var z_max_angle: float = 45.0
@export var input_format_z: InputFormat
@export var negate_input_z: bool = false

# gets a reference of the server so we can autoconnect signals
@onready var udpserver = $%udpserver

func transform_value(value: float, min_v: float, max_v: float, format: InputFormat, neg: bool) -> float:
	var angle_deg = 0
	if format == InputFormat.ANGLE:
		angle_deg = clamp(value, min_v, max_v) # value is an angle
	elif format == InputFormat.NORMALIZED_POSITIVE:
		angle_deg = lerp(min_v, max_v, clamp(value, 0, 1))
	elif format == InputFormat.NORMALIZED_SYMMETRIC:
		var t = (value + 1) / 2 
		angle_deg = lerp(min_v, max_v, clamp(t, 0, 1))
	
	if neg:
		angle_deg = -angle_deg
	return deg_to_rad(angle_deg)

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	if axis_x_name in Utils.table:
		udpserver.received_packet.connect(_control_x)
	if axis_y_name in Utils.table:
		udpserver.received_packet.connect(_control_y)	
	if axis_z_name in Utils.table:
		udpserver.received_packet.connect(_control_z)

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	pass


func _control_x(id: int, value: float) -> void:
	print("got x")
	if id == Utils.table[axis_x_name]:
		set_param_x(Generic6DOFJoint3D.PARAM_ANGULAR_SPRING_EQUILIBRIUM_POINT, 
		transform_value(value, x_min_angle, x_max_angle, input_format_x, negate_input_x))
	
func _control_y(id: int, value: float) -> void:
	print("got y")
	if id == Utils.table[axis_y_name]:
		set_param_y(Generic6DOFJoint3D.PARAM_ANGULAR_SPRING_EQUILIBRIUM_POINT, 
		transform_value(value, y_min_angle, y_max_angle, input_format_y, negate_input_y))
		
func _control_z(id: int, value: float) -> void:
	print("got z")
	if id == Utils.table[axis_z_name]:
		set_param_z(Generic6DOFJoint3D.PARAM_ANGULAR_SPRING_EQUILIBRIUM_POINT, 
		transform_value(value, z_min_angle, z_max_angle, input_format_z, negate_input_z))
