extends Node

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
@export var negate_output_x: bool = false
@export var invert_input_x: bool = false

@export_group("Y Axis")
@export var axis_y_name: String = "/"
@export_range(-180.0, 180.0, 0.1) var y_min_angle: float = -45.0
@export_range(-180.0, 180.0, 0.1) var y_max_angle: float = 45.0
@export var input_format_y: InputFormat
@export var negate_output_y: bool = false
@export var invert_input_y: bool = false

@export_group("Z Axis")
@export var axis_z_name: String = "/"
@export_range(-180.0, 180.0, 0.1) var z_min_angle: float = -45.0
@export_range(-180.0, 180.0, 0.1) var z_max_angle: float = 45.0
@export var input_format_z: InputFormat
@export var negate_output_z: bool = false
@export var invert_input_z: bool = false

# gets a reference of the server so we can autoconnect signals
@onready var udpserver = $%udpserver
@onready var lid_tr = $%eyelid_tr/link2
@onready var lid_br = $%eyelid_br/link2
@onready var lid_tl = $%eyelid_tl/link2
@onready var lid_bl = $%eyelid_bl/link2

func transform_value(value: float, min_v: float, max_v: float, format: InputFormat, inv_in: bool, neg_out: bool) -> float:
	var angle_deg = 0
	if format == InputFormat.ANGLE:
		value = -value if inv_in else value
		angle_deg = clamp(value, min_v, max_v) # value is an angle
	elif format == InputFormat.NORMALIZED_POSITIVE:
		value = (1 - value) if inv_in else value 
		angle_deg = lerp(min_v, max_v, clamp(value, 0, 1))
	elif format == InputFormat.NORMALIZED_SYMMETRIC:
		value = -value if inv_in else value
		var t = (value + 1) / 2 
		angle_deg = lerp(min_v, max_v, clamp(t, 0, 1))
	
	if neg_out:
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

var wid_l = deg_to_rad(30)
var wid_r = deg_to_rad(30)

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	var horizontal_ref = Utils.get_oldest_val(1) * -.8
	set_lid_wideness(lid_bl, lid_tl, horizontal_ref, wid_l)
	set_lid_wideness(lid_br, lid_tr, horizontal_ref, wid_r)

func set_lid_wideness(bottom: Generic6DOFJoint3D, top: Generic6DOFJoint3D, ref: float, val: float):
	bottom.set_param_y(Generic6DOFJoint3D.PARAM_ANGULAR_SPRING_EQUILIBRIUM_POINT, deg_to_rad(ref) - val)
	top.set_param_y(Generic6DOFJoint3D.PARAM_ANGULAR_SPRING_EQUILIBRIUM_POINT, deg_to_rad(ref) + val)


# this is for wideness Right
func _control_x(id: int, value: float) -> void:
	if id == Utils.table[axis_x_name]:
		print("executed cmd on x: ", id, " ", value, "")
		wid_r = transform_value(
			value, x_min_angle, x_max_angle, input_format_x, invert_input_x, negate_output_x
			)
			
		
# this is for wideness Left
func _control_y(id: int, value: float) -> void:
	if id == Utils.table[axis_y_name]:
		print("executed cmd on y: ", id, " ", value, "")
		wid_l = transform_value(
			value, y_min_angle, y_max_angle, input_format_y, invert_input_y, negate_output_y
			)
		
func _control_z(id: int, value: float) -> void:
	if id == Utils.table[axis_z_name]:
		print("executed cmd on z: ", id, " ", value, "")
		var val = transform_value(
			value, z_min_angle, z_max_angle, input_format_z, invert_input_z, negate_output_z
			)
