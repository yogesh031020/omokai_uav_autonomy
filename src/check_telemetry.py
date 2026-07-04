import asyncio
import sys
from mavsdk import System

async def run():
    drone = System()
    print("Connecting to drone...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")
    
    # Wait for connection
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Drone connected!")
            break
            
    # Print current flight mode
    async for flight_mode in drone.telemetry.flight_mode():
        print(f"Current Flight Mode: {flight_mode}")
        break
        
    # Print position
    async for pos in drone.telemetry.position():
        print(f"Position: Lat={pos.latitude_deg:.6f}, Lon={pos.longitude_deg:.6f}, Rel_Alt={pos.relative_altitude_m:.2f}m")
        break
        
    # Print land/armed status
    async for armed in drone.telemetry.armed():
        print(f"Armed: {armed}")
        break
        
    async for in_air in drone.telemetry.in_air():
        print(f"In Air: {in_air}")
        break

if __name__ == "__main__":
    asyncio.run(run())
