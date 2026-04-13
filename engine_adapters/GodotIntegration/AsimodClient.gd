extends Node

## ASIMOD Core Client for Godot (GDScript)
## Attach this script to a Node or add it to your Autoloads (Singleton)

signal chat_received(response_data)
signal request_failed(error_message)

@export var api_base_url: String = "http://localhost:8000/v1"

# Internal HTTPRequest node
var http_request: HTTPRequest

func _ready():
	http_request = HTTPRequest.new()
	add_child(http_request)
	http_request.request_completed.connect(_on_request_completed)

## --- Public Methods ---

## Sends a message to the AI
func send_chat(text: String, model: String = ""):
	var payload = {"text": text}
	if model != "":
		payload["model"] = model
	
	_make_post_request("/chat", payload)

## Gets the current system status
func get_status():
	_make_get_request("/status")

## Updates the remote configuration
func update_config(config_data: Dictionary):
	_make_post_request("/config", config_data)

## Stops any audio playing on the Core PC
func stop_audio():
	_make_post_request("/audio/stop", {})

## Toggles the microphone on/off
func toggle_microphone(enabled: bool):
	var mode = "micro" if enabled else "none"
	update_config({"stt_mode": mode})

## --- Private Helpers ---

func _make_get_request(endpoint: String):
	var url = api_base_url + endpoint
	http_request.request(url)

func _make_post_request(endpoint: String, payload: Dictionary):
	var url = api_base_url + endpoint
	var json_query = JSON.stringify(payload)
	var headers = ["Content-Type: application/json"]
	http_request.request(url, headers, HTTPClient.METHOD_POST, json_query)

func _on_request_completed(result, response_code, headers, body):
	if result != HTTPRequest.RESULT_SUCCESS:
		request_failed.emit("Network Error")
		return

	var json = JSON.parse_string(body.get_string_from_utf8())
	if json == null:
		request_failed.emit("Invalid JSON Response")
		return

	# If it's a chat response, we might want to emit a specific signal
	if json.has("response"):
		chat_received.emit(json)
	else:
		# For generic status or config updates
		print("[Asimod] Received: ", json)
