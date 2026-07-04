# Study Guide: Omokai UAV Autonomy Stack (Core Task)

This document is your **study guide** and **interview cheat sheet**. It explains exactly how our codebase works, why the architecture is designed this way, and how to explain it to the Omokai technical team.

---

## 1. System Architecture: How It Works (Step-by-Step)

When the operator inputs a command (e.g., *"Takeoff to 12 meters, go to coordinates 10,20,12, and land"*):

### **Step 1: The Input & Translation (`llm_parser.py`)**
* The user prompt is sent to the parser.
* The parser converts the plain English command into a **Structured JSON Plan**.
* *Example Output:*
  ```json
  {"mission": [{"command": "takeoff", "altitude": 12.0}, {"command": "waypoint", "x": 10.0, "y": 20.0, "z": 12.0, "speed": 5.0}, {"command": "land"}]}
  ```

### **Step 2: The Safety Guardrails (`validator.py`)**
* Before the JSON plan is executed, it must be validated.
* The validator checks the coordinates against our 2D Geofence bounds (e.g. within -100m to +100m) and checks if the altitude is safe (2m to 50m).
* *Why:* If the LLM hallucinates or makes a mistake, the validator blocks the script and prevents a drone crash.

### **Step 3: The Flight Execution (`executor.py`)**
* The validated JSON plan is sent to the executor.
* The executor parses the local 3D Cartesian coordinates ($X, Y, Z$ in meters) and converts them into global GPS coordinates (Latitude, Longitude, Altitude) using a reference Home position.
* It uses **MAVSDK-Python** to connect to the autopilot (ArduPilot/PX4 SITL), uploads the waypoints as a standard mission, and commands the drone to execute it.

---

## 2. Key Code Files and What They Do

### **`config.py` (The Settings Panel)**
* Contains all the global parameters: `MAX_ALTITUDE = 50.0`, `MAX_SPEED = 15.0`, `GEOFENCE_X_MAX = 100.0`.
* **Interview Tip:** If the interviewer asks you to change the safety limits live, **this is the only file you edit.** Change the value, save, and re-run.

### **`llm_parser.py` (The Translator)**
* Implements a **Rule-Based Regex Fallback**. If there is no internet connection or Ollama server running, it parses commands locally using pattern matching. This ensures the demo is 100% reliable.
* Can connect to Ollama (local model) or OpenAI via HTTP requests.

### **`validator.py` (The Police Officer)**
* Uses standard python dictionary checks to validate the JSON schema.
* Raises a clear `ValueError` if a coordinate is outside the geofence or if a command is unrecognized.

### **`executor.py` (The Pilot)**
* Connects to the virtual drone autopilot using MAVSDK via UDP port 14540.
* Implements a **`--dry-run` fallback mode** that mocks MAVSDK. If MAVSDK is not installed, the script still runs and demonstrates the execution logic in the terminal.

---

## 3. Anticipated Interview Questions & Best Answers

### **Q1: "Why did you keep the LLM out of the control loop?"**
* **Your Answer:** *"LLMs are non-deterministic and can hallucinate incorrect values or commands. If an LLM is connected directly to the flight control system, a single wrong output could cause a physical crash or flyaway. By decoupling the LLM, we use the LLM only for planning, validate its output against a deterministic safety validator, and let the autopilot execute it safely."*

### **Q2: "How does your coordinate translation work?"**
* **Your Answer:** *"Operators think in local meters (e.g., 'fly 10m forward'), but the autopilot flies using global GPS coordinates. In `executor.py`, we take a reference Home position (defaulting to the standard Gazebo home lat/lon) and translate the local X and Y offsets into Latitude and Longitude coordinates ($1\text{ meter} \approx 0.000009\text{ degrees}$) before creating the `MissionItem`."*

### **Q3: "How is your code structured for portability?"**
* **Your Answer:** *"We have a `Dockerfile` and a `docker-compose.yml` that package ROS 2, MAVSDK, and our Python scripts. The examiner does not need to install anything on their system—they can run the entire autonomy stack with a single command: `docker-compose up --build`."*
