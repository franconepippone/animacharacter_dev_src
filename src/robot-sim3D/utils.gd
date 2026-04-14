extends Node

func load_servo_csv(path: String) -> Dictionary:
	var result: Dictionary = {}

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("Failed to open CSV: " + path)
		return result

	while not file.eof_reached():
		var line := file.get_line().strip_edges()

		# skip empty lines
		if line == "":
			continue

		# skip comments
		if line.begins_with("#"):
			continue

		# split csv
		var parts := line.split(",")

		if parts.size() < 2:
			continue

		var id_str := parts[0].strip_edges()
		var name := parts[1].strip_edges()

		# ensure id is valid
		if id_str.is_valid_int():
			result[name] = int(id_str)

	return result

var table := load_servo_csv("id_mapping.csv")

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	print(table)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass
