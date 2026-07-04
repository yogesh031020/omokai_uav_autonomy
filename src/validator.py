import json
import config

def validate_mission_json(json_str):
    """
    Validates a mission JSON string against the schema and safety geofence/flight rules.
    Raises ValueError if validation fails.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
        
    if "mission" not in data or not isinstance(data["mission"], list):
        raise ValueError("Missing or invalid 'mission' key. Must contain a list of commands.")
        
    validated_steps = []
    
    for idx, step in enumerate(data["mission"]):
        if not isinstance(step, dict):
            raise ValueError(f"Step {idx} must be a JSON object.")
            
        if "command" not in step:
            raise ValueError(f"Step {idx} is missing the 'command' field.")
            
        cmd = step["command"]
        
        # 1. Takeoff command validation
        if cmd == "takeoff":
            if "altitude" not in step:
                raise ValueError(f"Step {idx}: Takeoff command is missing the 'altitude' field.")
            alt = float(step["altitude"])
            if alt < config.MIN_ALTITUDE or alt > config.MAX_ALTITUDE:
                raise ValueError(f"Step {idx}: Takeoff altitude {alt}m is out of bounds [{config.MIN_ALTITUDE}m - {config.MAX_ALTITUDE}m].")
            validated_steps.append({"command": "takeoff", "altitude": alt})
            
        # 2. Land command validation
        elif cmd == "land":
            validated_steps.append({"command": "land"})
            
        # 3. Waypoint command validation
        elif cmd == "waypoint":
            for field in ["x", "y", "z"]:
                if field not in step:
                    raise ValueError(f"Step {idx}: Waypoint is missing the '{field}' field.")
                    
            x = float(step["x"])
            y = float(step["y"])
            z = float(step["z"])
            speed = float(step.get("speed", 5.0))
            
            # Check 2D Geofence
            if x < config.GEOFENCE_X_MIN or x > config.GEOFENCE_X_MAX:
                raise ValueError(f"Step {idx}: Waypoint X coordinate {x}m violates the geofence boundary [{config.GEOFENCE_X_MIN}m to {config.GEOFENCE_X_MAX}m].")
            if y < config.GEOFENCE_Y_MIN or y > config.GEOFENCE_Y_MAX:
                raise ValueError(f"Step {idx}: Waypoint Y coordinate {y}m violates the geofence boundary [{config.GEOFENCE_Y_MIN}m to {config.GEOFENCE_Y_MAX}m].")
                
            # Check altitude limits (z coordinate)
            if z < config.MIN_ALTITUDE or z > config.MAX_ALTITUDE:
                raise ValueError(f"Step {idx}: Waypoint altitude {z}m is out of bounds [{config.MIN_ALTITUDE}m - {config.MAX_ALTITUDE}m].")
                
            # Check speed limit
            if speed <= 0 or speed > config.MAX_SPEED:
                raise ValueError(f"Step {idx}: Waypoint speed {speed} m/s is out of bounds [0.1m/s - {config.MAX_SPEED}m/s].")
                
            validated_steps.append({
                "command": "waypoint",
                "x": x,
                "y": y,
                "z": z,
                "speed": speed
            })
            
        # 4. Swarm Formation command validation
        elif cmd == "formation":
            if "shape" not in step:
                raise ValueError(f"Step {idx}: Formation is missing the 'shape' field.")
            shape = step["shape"]
            if shape not in ["wedge", "line", "column"]:
                raise ValueError(f"Step {idx}: Unknown formation shape '{shape}'. Must be wedge, line, or column.")
            spacing = float(step.get("spacing", config.SWARM_SPACING))
            validated_steps.append({
                "command": "formation",
                "shape": shape,
                "spacing": spacing
            })
            
        # 5. Follow Target command validation
        elif cmd == "follow":
            if "target" not in step:
                raise ValueError(f"Step {idx}: Follow command is missing the 'target' field.")
            target = step["target"]
            validated_steps.append({
                "command": "follow",
                "target": target
            })
            
        else:
            raise ValueError(f"Step {idx}: Unrecognized command '{cmd}'.")
            
    return {"mission": validated_steps}
