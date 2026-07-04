# Technical Approach & Core Task Resolutions

This document outlines the architecture, design choices, and engineering workarounds implemented for the Omokai Autonomy Stack.

---

## Core Task: Gazebo Synchronization & GUI Freeze Resolution

### **1. The Challenge: Simulation Deadlock on GUI Connection**
During live execution of the flight mission, the autonomy stack would hang indefinitely at the `Waiting for drone to be ready to arm` pre-flight stage. The user was forced to manually click the pause/play button in the Gazebo 3D GUI window to trigger arming.

* **The Root Cause:** When Gazebo GUI loads, its 3D rendering engine (`ogre`/`ogre2`) performs heavy graphics initialization and shader compilation. In single-process mode (`gz sim -r`), this blocks the main physics loop thread. Furthermore, when the GUI connects to the physics server, it sends a handshake that automatically pauses the physics world. Since ArduPilot SITL requires the physics clock to step in order to broadcast telemetry, this pause blocks all incoming MAVLink streams (such as `health` and `home`).

### **2. The Resolution: Asynchronous Execution & Programmatic Control**
To resolve this permanently and ensure one-touch autonomous flight without any manual GUI interaction, we implemented a three-tier synchronization system:

1. **Separated Process Execution:** The Gazebo simulator is launched in two separate processes:
   * A headless physics server (`gz sim -s -r`) starts first and runs the physics engine immediately.
   * The 3D GUI (`gz sim -g`) connects later as a passive visual client, which prevents graphics loading from blocking physics ticks.
2. **Active Unpause Spammer:** In [executor.py](src/executor.py), we spawned a background asynchronous task (`spam_unpause`) that continuously queries the Gazebo world service API (`/world/<world_name>/control`) and commands `pause: false` at 1 Hz during pre-flight. If the GUI pauses the world on connect, the script instantly overrides it.
3. **Stream Timeout Fail-Safe:** MAVSDK's `telemetry.home()` stream can occasionally miss the initial MAVLink home broadcast when physics frames are dropped. We wrapped the stream in a 5-second `asyncio.wait_for` timeout. If a timeout occurs, the executor gracefully falls back to the current position stream (`telemetry.position()`), preventing an infinite block.

---

## Challenge 1: Multi-Agent Swarm Formations

### **1. Architecture & Multi-SITL Setup**
To control a swarm of 3 drones, we will run **3 independent instances of ArduPilot/PX4 SITL** inside Docker, exposed on separate UDP ports:
* **Drone 1 (Leader):** UDP port `14540`
* **Drone 2 (Follower 1):** UDP port `14541`
* **Drone 3 (Follower 2):** UDP port `14542`

Our deterministic `swarm_executor.py` will instantiate 3 separate MAVSDK `System` connections.

### **2. Formation Coordinate Offsets**
When the operator commands a formation path (e.g. waypoint $P = (X, Y, Z)$), the executor calculates offset positions relative to the heading angle ($\psi$) of the leader:

* **Wedge Formation (V-Shape):**
  * Leader ($D_1$): $P_1 = (X, Y, Z)$
  * Left Follower ($D_2$): $P_2 = (X - d \cdot \cos(\psi + 135^\circ), Y - d \cdot \sin(\psi + 135^\circ), Z)$
  * Right Follower ($D_3$): $P_3 = (X - d \cdot \cos(\psi - 135^\circ), Y - d \cdot \sin(\psi - 135^\circ), Z)$
  *(where $d$ is the swarm spacing, e.g. 5 meters)*

* **Line Formation:**
  * Leader ($D_1$): $P_1 = (X, Y, Z)$
  * Left Follower ($D_2$): $P_2 = (X - d \cdot \sin(\psi), Y + d \cdot \cos(\psi), Z)$
  * Right Follower ($D_3$): $P_3 = (X + d \cdot \sin(\psi), Y - d \cdot \cos(\psi), Z)$

Commands are sent in parallel using python's `asyncio.gather()` to ensure all drones initiate trajectory changes simultaneously.

---

## Challenge 2: SLAM & Autonomous Navigation

### **1. Integration with ROS 2 and Nav2**
For navigating unknown or complex indoor environments, we will transition control from pre-determined GPS waypoints to a **ROS 2 Navigation2 (Nav2)** stack:
* **Sensors:** The simulated drone in Gazebo is equipped with a 2D LiDAR (sensor ranges up to 10m) and a 3D depth camera.
* **Mapping (SLAM):** We run the **`slam_toolbox`** node to generate a 2D occupancy grid map of the environment in real time as the drone flies.
* **Localization:** AMCL (Adaptive Monte Carlo Localization) localizes the drone within the mapped space.

### **2. Obstacle-Aware Path Planning**
Instead of sending coordinates directly to the autopilot, the `swarm_executor` publishes waypoints to the `/goal_pose` ROS 2 topic. The **Nav2 Controller** calculates collision-free paths around detected obstacles using local costmaps and commands the autopilot via offboard velocity messages.

---

## Challenge 3: Vision AI Target Detection & Tracking

### **1. YOLOv8 Inference Node**
We will implement an image processing node (`vision_tracker.py`):
* Subscribes to the camera topic (e.g. `/drone/camera/image_raw`) in ROS 2.
* Passes the video frame to the **Ultralytics YOLOv8** model.
* The target class (e.g. "person") is loaded dynamically from `config.py`.

### **2. Bounding Box & Target Locking**
When the target is detected with a confidence above `0.5`:
1. The frame is saved locally, and a notification is logged.
2. The bounding box centroid $(c_x, c_y)$ is calculated relative to the frame center $(f_x, f_y)$.

### **3. Closed-Loop Proportional (P) Tracking**
We compute the pixel errors:
$$\Delta x = c_x - f_x, \quad \Delta y = c_y - f_y$$

These errors are passed through a Proportional controller to generate velocity commands:
* **Yaw rate command:** $r = -k_p \cdot \Delta x$ (yaw to center the target horizontally).
* **Pitch velocity command:** $v_x = k_p \cdot (\text{Desired Area} - \text{Bbox Area})$ (forward/backward to maintain distance).
* **Vertical velocity command:** $v_z = -k_p \cdot \Delta y$ (adjust altitude to center vertically).

Velocity commands are sent to the drone via MAVSDK Offboard mode at 20 Hz to execute smooth tracking.

---

## 📈 Scaling to Harder, Real-World Problems

To scale this simulator prototype into a reliable, commercial-grade autonomous deployment system, the following core architecture enhancements would be implemented:

### 1. Behavior Trees for Error Recovery & Fail-safes
*   **Challenge:** Python asynchronous scripts are prone to crash on unexpected runtime errors or sensor dropouts.
*   **Scale:** Transition the deterministic executor from a linear script to a formal **Behavior Tree (using BehaviorTree.CPP)**. This allows the system to handle complex recovery sequences (e.g. low battery, signal loss, sensor drift, motor failure) with clean, auditable fallback branches.

### 2. Telemetry Loss & Link Interruption Robustness
*   **Challenge:** RF or LTE connection loss will interrupt high-frequency offboard velocity setpoints.
*   **Scale:** Instead of streaming commands continuously, the executor will upload the entire mission plan directly to the autopilot's physical EEPROM memory as standard MAVLink waypoints. If the connection drops, the autopilot takes over and executes the path autonomously or initiates a hardware-level Return-To-Launch (RTL).

### 3. Hardware-in-the-Loop (HITL) Simulation
*   **Challenge:** SITL does not capture hardware latency or CPU limitations of real flight controllers.
*   **Scale:** Set up a Hardware-in-the-Loop test bench where the companion computer running our autonomy stack connects to a physical Pixhawk flight controller over a serial UART link. The Pixhawk is connected to Gazebo, allowing us to evaluate processing constraints and physical serial data lag.

### 4. Dynamic Path Planning via Costmap Integration
*   **Challenge:** Static coordinates do not handle moving obstacles (e.g., humans or other drones).
*   **Scale:** Fully integrate the executor with the **Navigation2 (Nav2) costmap pipeline**. The executor publishes the final target destination, but local obstacle avoidance nodes dynamically modify the trajectory in real-time, returning to the global plan once clear.

---

## Cited Sources & Licenses

As required by the take-home task guidelines, the following open-source frameworks and libraries were utilized as the foundational building blocks of this project:

1. **MAVSDK (MAVSDK-Python)**
   * **URL:** [github.com/mavlink/MAVSDK-Python](https://github.com/mavlink/MAVSDK-Python)
   * **License:** BSD 3-Clause "New" or "Revised" License
   * **Usage:** Core connection, telemetry subscription, takeoff/landing execution, and waypoint mission uploading.

2. **ArduPilot SITL / MAVProxy**
   * **URL:** [github.com/ArduPilot/ardupilot](https://github.com/ArduPilot/ardupilot)
   * **License:** GNU General Public License v3.0 (GPL-3.0)
   * **Usage:** Provides the Software In The Loop (SITL) autopilot simulation engine and ground command routing.

3. **ardupilot_gazebo (plugin)**
   * **URL:** [github.com/ArduPilot/ardupilot_gazebo](https://github.com/ArduPilot/ardupilot_gazebo)
   * **License:** GNU General Public License v3.0 (GPL-3.0)
   * **Usage:** Bridges sensor state and motor outputs between the SITL autopilot and Gazebo Harmonic physics.

4. **ROS 2 Navigation2 (Nav2)**
   * **URL:** [github.com/ros-navigation/navigation2](https://github.com/ros-navigation/navigation2)
   * **License:** Apache License 2.0 (Apache-2.0)
   * **Usage:** Serves as the blueprint architectural reference for the `/navigate_to_pose` client-server action bridge pattern implemented in `src/ros2_nav2_executor.py`.

5. **Yogesh's Past Work: warehouse-drone-v2**
   * **URL:** [github.com/yogesh031020/warehouse-drone-v2](https://github.com/yogesh031020/warehouse-drone-v2)
   * **License:** MIT License
   * **Usage:** Serves as the foundational codebase reference for structuring ArduPilot waypoint structures, home launch sequence definitions, and initial SITL Canberra runway coordinate testing.
