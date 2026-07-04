# Omokai UAV Autonomy Stack

A highly portable, decoupled, and validated UAV Autonomy Stack that translates natural language operator prompts into deterministic drone actions. 

This repository implements the **Core Task** and the **Vision AI Target Tracking Challenge (Challenge 3)** for the Omokai Robotics Engineer Take-Home Task.

---

## 🏗️ System Architecture

To ensure flight safety and prevent autopilot overrides, the system separates planning from control in a **decoupled, non-agentic loop**:

```
[Operator Prompt] ──> [LLM Parser] ──> [Raw JSON Plan] ──> [Safety Validator] ──> [MAVSDK Executor] ──> [SITL/Autopilot]
```

1. **LLM Parser (`src/llm_parser.py`)**: Zero-dependency offline regex parser (default fallback) or local Ollama LLM endpoint to translate English prompts into a structured JSON mission.
2. **Safety Validator (`src/validator.py`)**: Checks coordinates against geofence bounds ($\pm 100m$), max speed ($15 m/s$), and safe altitude limits ($2m - 50m$). Rejects invalid prompts immediately.
3. **Deterministic Flight Executor (`src/executor.py`)**: Translates 3D Cartesian meter offsets relative to Home into global GPS coordinates, prepends the mandatory ArduPilot index 0 Home waypoint, handles EKF alignment, and executes the trajectory via MAVSDK.
4. **Vision AI Tracker (`src/ros2_tracker_node.py`)**: A ROS 2 Humble node that subscribes to the drone's camera feed, runs target lock estimation, and commands proportional velocity tracking inputs.

---

## 📁 File Structure

* `src/config.py`: High-level system settings (geofences, speeds, target class).
* `src/llm_parser.py`: Zero-dependency regex translator & Ollama wrapper.
* `src/validator.py`: Evaluates JSON plans against safety limits.
* `src/executor.py`: Translates Cartesian waypoints and commands MAVSDK.
* `src/ros2_tracker_node.py`: ROS 2 Node for camera perception & tracking control.
* `src/ros2_nav2_executor.py`: ROS 2 Node executing navigation plans via Nav2 Action Client.
* `src/cli.py`: Unified event loop CLI entrypoint.
* `Dockerfile` / `docker-compose.yml`: Containerized runtime environment.
* `LICENSE`: MIT License file.

---

## 🚀 How to Run

### **1. Dry-Run Mode (Offline / Sandbox)**
You can test the parser and safety validator immediately without any simulator setup:
```bash
python3 src/cli.py "Takeoff to 15m, fly to 10,20,15, and land"
```

### **2. Live Simulation Mode (WSL / Native Linux)**
To execute the flight plan live in the Gazebo simulator:

1. **Start Headless Gazebo (Terminal 1):**
   ```bash
   export GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/ardupilot_gazebo/build
   gz sim -s -r /home/yogesh_e_s/ardupilot_gazebo/worlds/iris_runway.sdf
   ```
2. **Start ArduPilot SITL (Terminal 2):**
   *(Note: `--model JSON` is required to communicate with Gazebo Harmonic)*
   ```bash
   cd ~/ardupilot/ArduCopter && sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --console --out=udp:127.0.0.1:14540
   ```
3. **Open QGroundControl:**
   Open QGroundControl on your desktop and select the **UDP** connection. It will connect to port `14550` and display the map and HUD.
4. **Run Autonomy Stack (Terminal 3):**
   ```bash
   cd /mnt/d/Antigravity_Storage/scratch/omokai_uav_autonomy
   python3 src/cli.py "Takeoff to 15m, go to 10,20,15, and land" --live
   ```

---

## 🐳 Docker Containerization

To run the autonomy validation pipeline inside a portable Linux container (perfect for the examiner's laptop):

```bash
# Start Docker Desktop and run:
docker-compose up --build
```
This mounts the workspace, compiles dependencies, parses a default squad-level instructions prompt, executes a validation test check, and exits cleanly.

---

## 📺 ROS 2 Vision Tracking (Challenge 3)

The repository includes a ready-to-deploy ROS 2 python node representing the **Vision AI Target Tracker** (`src/ros2_tracker_node.py`). 

To launch the node in your ROS 2 Humble workspace:
```bash
source /opt/ros/humble/setup.bash
python3 src/ros2_tracker_node.py
```
This node subscribes to `/camera/image_raw`, calculates the visual target offset centroid, and publishes reactive velocity commands to `/cmd_vel`.

---

## 🤖 ROS 2 Navigation2 (Challenge 2)

The repository includes a **ROS 2 Nav2 Action Client** (`src/ros2_nav2_executor.py`) demonstrating how the pipeline executes validated JSON plans using ground robots or drones on a ROS 2 + Nav2 stack.

To launch the Nav2 executor node:
```bash
source /opt/ros/humble/setup.bash
python3 src/ros2_nav2_executor.py
```
This node establishes an action client to the Nav2 `/navigate_to_pose` server, plans path goals dynamically around obstacles, and coordinates navigation waypoints.

---

## 📝 Submission Checklist

* **Code Repository:** ZIP archive of the `omokai_uav_autonomy` directory.
* **Flight Demo Recordings:**
  1. **Gazebo 3D Simulation:** Located at `D:\Drone_Projects\Project_ICARUS\Project_TRINITY\docs\Core Task Gazebo 1.mp4` (showing the 3D drone trajectory).
  2. **QGroundControl Telemetry Map:** Located at `D:\Drone_Projects\Project_ICARUS\Project_TRINITY\docs\Core Task QGC.mp4` (showing the live HUD and map path).
* **Write-up Documentation:** `APPROACH.md` (Senior Challenge solutions).
