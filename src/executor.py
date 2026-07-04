"""
Deterministic Flight Executor for the Omokai UAV Autonomy Stack.

Reads a validated mission JSON and issues concrete MAVSDK commands
to the ArduPilot/PX4 SITL autopilot. The same JSON always produces
the same behaviour -- the LLM is never in this control loop.
"""
import asyncio
import sys
import json
import math
import config

try:
    from mavsdk import System
    from mavsdk.mission import MissionItem, MissionPlan
    MAVSDK_AVAILABLE = True
except ImportError:
    print("[Warning] MAVSDK not installed. Dry-run mode only.")
    MAVSDK_AVAILABLE = False

    class System:
        pass
    class MissionItem:
        class CameraAction:
            NONE = 0
        class VehicleAction:
            NONE = 0
        def __init__(self, *args, **kwargs):
            pass
    class MissionPlan:
        def __init__(self, *args, **kwargs):
            pass


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------
# At 0° latitude  1 degree ≈ 111 320 m.
# We fetch the real home position from the autopilot telemetry so these
# offsets are always relative to wherever SITL spawned.
METERS_PER_DEG_LAT = 111320.0

def meters_to_lat_offset(dy_meters):
    return dy_meters / METERS_PER_DEG_LAT

def meters_to_lon_offset(dx_meters, ref_lat_deg):
    return dx_meters / (METERS_PER_DEG_LAT * math.cos(math.radians(ref_lat_deg)))

def get_distance_meters(lat1, lon1, lat2, lon2):
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    mean_lat = math.radians((lat1 + lat2) / 2.0)
    dy = dlat * METERS_PER_DEG_LAT
    dx = dlon * METERS_PER_DEG_LAT * math.cos(mean_lat)
    return math.sqrt(dx*dx + dy*dy)


class DroneExecutor:
    """Deterministic executor: validated JSON in -> autopilot commands out."""

    def __init__(self, system_address="udpin://0.0.0.0:14540", dry_run=False):
        self.system_address = system_address
        self.dry_run = dry_run
        self.drone = None
        self.home_lat = None
        self.home_lon = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    async def connect(self):
        if self.dry_run:
            print(f"[Dry-Run] Simulating connection to {self.system_address}")
            return

        print(f"Connecting to drone at {self.system_address} ...")
        self.drone = System()
        await self.drone.connect(system_address=self.system_address)

        # Wait for physical link
        print("Waiting for drone heartbeat ...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                print("Heartbeat received -- drone connected!")
                break

    # ------------------------------------------------------------------
    # Pre-flight: wait until the autopilot says it is safe to arm
    # ------------------------------------------------------------------
    async def wait_for_ready(self):
        if self.dry_run:
            return

        print("Waiting for drone to be ready to arm (GPS lock + EKF) ...")
        async for health in self.drone.telemetry.health():
            if health.is_global_position_ok and health.is_home_position_ok:
                print("GPS lock acquired & home position set -- ready to arm!")
                break

        # Grab the home position so we can convert local X/Y -> lat/lon
        async for pos in self.drone.telemetry.home():
            self.home_lat = pos.latitude_deg
            self.home_lon = pos.longitude_deg
            print(f"Home position: lat={self.home_lat:.6f}  lon={self.home_lon:.6f}")
            break

    # ------------------------------------------------------------------
    # Build MAVSDK MissionItems from the validated JSON
    # ------------------------------------------------------------------
    def build_mission_items(self, mission_steps):
        mission_items = []
        takeoff_alt = 10.0
        should_land = False

        # In ArduPilot, mission index 0 is reserved for the Home Position.
        # We must insert a dummy waypoint at index 0, otherwise ArduPilot will overwrite
        # our first actual waypoint as the home position and ignore it.
        if not self.dry_run:
            ref_lat = self.home_lat if self.home_lat is not None else -35.363262
            ref_lon = self.home_lon if self.home_lon is not None else 149.165237
            dummy_item = MissionItem(
                ref_lat, ref_lon, 0.0, 0.0,
                True,
                float('nan'), float('nan'),
                MissionItem.CameraAction.NONE,
                float('nan'), float('nan'),
                1.0,
                float('nan'), float('nan'),
                MissionItem.VehicleAction.NONE,
            )
            mission_items.append(dummy_item)

        for step in mission_steps:
            cmd = step["command"]

            if cmd == "takeoff":
                takeoff_alt = step["altitude"]

            elif cmd == "waypoint":
                x_m  = step["x"]
                y_m  = step["y"]
                alt  = step["z"]
                spd  = step.get("speed", 5.0)

                if self.dry_run or self.home_lat is None:
                    # Use default ArduPilot SITL home (Canberra, AU)
                    ref_lat, ref_lon = -35.363261, 149.165230
                else:
                    ref_lat, ref_lon = self.home_lat, self.home_lon

                lat = ref_lat + meters_to_lat_offset(y_m)
                lon = ref_lon + meters_to_lon_offset(x_m, ref_lat)

                if self.dry_run:
                    print(f"  [Dry-Run] Waypoint -> lat={lat:.6f}  lon={lon:.6f}  alt={alt}m  speed={spd}m/s")
                else:
                    item = MissionItem(
                        lat, lon, alt, spd,
                        True,                             # is_fly_through
                        float('nan'), float('nan'),       # gimbal pitch/yaw
                        MissionItem.CameraAction.NONE,
                        float('nan'), float('nan'),       # loiter / photo interval
                        1.0,                              # acceptance_radius_m
                        float('nan'), float('nan'),       # yaw / photo distance
                        MissionItem.VehicleAction.NONE,
                    )
                    mission_items.append(item)

            elif cmd == "land":
                should_land = True

        return mission_items, takeoff_alt, should_land

    # ------------------------------------------------------------------
    # Execute the mission
    # ------------------------------------------------------------------
    async def execute_mission(self, mission_plan_dict):
        steps = mission_plan_dict["mission"]
        print(f"\n{'='*50}")
        print(f"Mission contains {len(steps)} commands")
        for i, s in enumerate(steps):
            print(f"  Step {i}: {s}")
        print(f"{'='*50}\n")

        items, takeoff_alt, should_land = self.build_mission_items(steps)

        # ---- DRY-RUN path ----
        if self.dry_run:
            print(f"[Dry-Run] ARM -> TAKEOFF to {takeoff_alt}m")
            await asyncio.sleep(1)
            if items:
                print(f"[Dry-Run] Flying {len(items)} waypoints ...")
                await asyncio.sleep(2)
            if should_land:
                print("[Dry-Run] LAND -> DISARM")
                await asyncio.sleep(1)
            print("[Dry-Run] Mission complete.")
            return

        # ---- LIVE path ----
        try:
            # 1. Pre-flight
            await self.wait_for_ready()

            # Disable pre-arm checks to prevent simulator lag failures
            # (Gyros/Accels inconsistent). Try multiple parameter names
            # because different ArduPilot versions use different names.
            for param_name in ["ARMING_CHECK", "BRD_SAFETY_DEFLT", "BRD_SAFETYENABLE"]:
                try:
                    await self.drone.param.set_param_int(param_name, 0)
                    break  # Success — no need to try others
                except Exception:
                    pass

            # Wait for sensors (gyros, accels, EKF) to fully stabilize.
            # In Gazebo SITL the physics engine needs a few seconds after
            # EKF origin is set before sensor readings converge.
            print("Waiting for sensor stabilization ...")
            await asyncio.sleep(5)

            # 2. Arm & takeoff
            print(f"Setting takeoff altitude to {takeoff_alt}m ...")
            await self.drone.action.set_takeoff_altitude(takeoff_alt)

            # Retry arming up to 5 times with 3-second gaps.
            # ArduPilot may reject the first few attempts while
            # accelerometer and gyroscope calibrations converge.
            print("Arming ...")
            armed = False
            for attempt in range(1, 6):
                try:
                    await self.drone.action.arm()
                    armed = True
                    break
                except Exception as arm_err:
                    print(f"  Arm attempt {attempt}/5 failed: {arm_err}")
                    if attempt < 5:
                        print(f"  Retrying in 3 seconds ...")
                        await asyncio.sleep(3)
            if not armed:
                raise RuntimeError("Failed to arm after 5 attempts.")
            print("Armed.")

            print(f"Taking off to {takeoff_alt}m ...")
            await self.drone.action.takeoff()

            # Wait until we are roughly at the target altitude
            print("Climbing ...")
            async for pos in self.drone.telemetry.position():
                alt = pos.relative_altitude_m
                sys.stdout.write(f"\r  Altitude: {alt:.1f}m / {takeoff_alt}m")
                sys.stdout.flush()
                if alt >= takeoff_alt * 0.90:
                    print(f"\n  Reached target altitude.")
                    break
            await asyncio.sleep(2)

            # 3. Waypoint mission
            if items:
                # The last item in the list is our final waypoint
                final_item = items[-1]
                target_lat = final_item.latitude_deg
                target_lon = final_item.longitude_deg
                target_alt = final_item.relative_altitude_m

                print(f"Uploading {len(items)} waypoint(s) to autopilot ...")
                await self.drone.mission.upload_mission(MissionPlan(items))

                print("Starting mission flight ...")
                await self.drone.mission.start_mission()

                # Robust arrival detection: check both mission progress and distance to target
                arrival_event = asyncio.Event()

                async def monitor_progress():
                    try:
                        async for progress in self.drone.mission.mission_progress():
                            print(f"  Progress: waypoint {progress.current}/{progress.total}")
                            if progress.total > 0 and progress.current >= progress.total:
                                print("  Mission progress reports completion.")
                                arrival_event.set()
                                break
                    except Exception as e:
                        print(f"  Progress monitoring error/warning: {e}")

                async def monitor_distance():
                    try:
                        async for pos in self.drone.telemetry.position():
                            dist = get_distance_meters(pos.latitude_deg, pos.longitude_deg, target_lat, target_lon)
                            alt_diff = abs(pos.relative_altitude_m - target_alt)
                            if dist < 2.0 and alt_diff < 2.0:
                                print(f"  Telemetry reports arrival at target (distance={dist:.1f}m, alt_diff={alt_diff:.1f}m).")
                                arrival_event.set()
                                break
                            await asyncio.sleep(1)
                    except Exception as e:
                        print(f"  Distance monitoring error/warning: {e}")

                # Run both monitor tasks in the background
                prog_task = asyncio.create_task(monitor_progress())
                dist_task = asyncio.create_task(monitor_distance())

                await arrival_event.wait()

                prog_task.cancel()
                dist_task.cancel()
                print("  All waypoints reached.")
                await asyncio.sleep(3)

            # 4. Land
            if should_land:
                print("Commanding LAND ...")
                await self.drone.action.land()

                print("Descending ...")
                async for armed_state in self.drone.telemetry.armed():
                    if not armed_state:
                        print("Landed and disarmed.")
                        break

            print("\n=== MISSION COMPLETE ===")

        except Exception as err:
            print(f"\nExecution error: {err}")
            print("  Attempting emergency land ...")
            try:
                await self.drone.action.land()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
async def _self_test():
    plan = {
        "mission": [
            {"command": "takeoff", "altitude": 15.0},
            {"command": "waypoint", "x": 10.0, "y": 20.0, "z": 15.0, "speed": 4.0},
            {"command": "waypoint", "x": -20.0, "y": 10.0, "z": 12.0, "speed": 6.0},
            {"command": "land"},
        ]
    }
    ex = DroneExecutor(dry_run=True)
    await ex.connect()
    await ex.execute_mission(plan)

if __name__ == "__main__":
    asyncio.run(_self_test())
