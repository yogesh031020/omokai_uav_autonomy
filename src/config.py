# Configuration and Safety Limits for Omokai Autonomy Stack
# Modify these parameters during the live interview to change system behavior.

# --- LLM Settings ---
LLM_API_KEY = "mock_mode"  # Set to "openai" or "ollama" depending on the LLM backend
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "llama3"

# --- Safety Geofence & Flight Limits ---
MAX_ALTITUDE = 50.0   # Maximum allowed altitude in meters
MIN_ALTITUDE = 2.0    # Minimum allowed altitude in meters
MAX_SPEED = 15.0      # Maximum allowed speed in m/s

# 2D Bounding Box Geofence limits (in meters from start home position)
GEOFENCE_X_MIN = -100.0
GEOFENCE_X_MAX = 100.0
GEOFENCE_Y_MIN = -100.0
GEOFENCE_Y_MAX = 100.0

# --- Swarm Settings (Challenge 1) ---
DEFAULT_FORMATION = "wedge"
SWARM_SPACING = 5.0   # Horizontal distance between drones in meters

# --- Vision AI Settings (Challenge 3) ---
YOLO_TARGET_CLASS = "person"  # Target to detect and follow
DETECTION_CONFIDENCE = 0.5    # Minimum probability threshold
