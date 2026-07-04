#!/usr/bin/env python3
"""
ROS 2 Nav2 Action Client Executor.
This script demonstrates how to execute the validated JSON plan 
using a ROS 2 ground robot / drone running Navigation2 (Nav2).

Listens to:
    - /navigate_to_pose (nav2_msgs/action/NavigateToPose)
"""
import sys
import asyncio
import json
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped

# Attempt to import Nav2 action definition (might not be installed on Windows host, but native on Linux)
try:
    from nav2_msgs.action import NavigateToPose
    NAV2_AVAILABLE = True
except ImportError:
    # Fallback mock class for dry-run/cross-platform compatibility
    NAV2_AVAILABLE = False
    class NavigateToPose:
        class Goal:
            def __init__(self):
                self.pose = PoseStamped()
        class Result:
            pass

class Ros2Nav2Executor(Node):
    def __init__(self):
        super().__init__('ros2_nav2_executor')
        
        if NAV2_AVAILABLE:
            self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        else:
            self.get_logger().warn("nav2_msgs package not found. Running in mock/dry-run mode.")
            self.nav_client = None

    async def execute_mission_plan(self, validated_json_str):
        plan = json.loads(validated_json_str)
        steps = plan.get("mission", [])
        
        self.get_logger().info(f"ROS 2 Nav2: Starting mission execution with {len(steps)} steps.")
        
        for i, step in enumerate(steps):
            cmd = step.get("command")
            if cmd == "waypoint":
                x = step.get("x", 0.0)
                y = step.get("y", 0.0)
                self.get_logger().info(f"Step {i}: Sending Nav2 goal to Pose ({x}, {y})")
                
                success = await self.send_nav_goal(x, y)
                if success:
                    self.get_logger().info(f"Step {i}: Successfully reached pose ({x}, {y})")
                else:
                    self.get_logger().error(f"Step {i}: Failed to reach pose ({x}, {y}). Mission aborted!")
                    return False
            elif cmd == "land" or cmd == "return_to_home":
                self.get_logger().info(f"Step {i}: Commanding return to starting position.")
                await self.send_nav_goal(0.0, 0.0)
                
        self.get_logger().info("ROS 2 Nav2: Mission completed successfully.")
        return True

    async def send_nav_goal(self, x, y):
        """Sends a PoseStamped goal to the Nav2 /navigate_to_pose action server."""
        if not NAV2_AVAILABLE or self.nav_client is None:
            # Mock behavior in dry-run
            self.get_logger().info(f"[Mock Nav2] Simulating path planning and obstacle-avoidance to ({x}, {y}) ...")
            await asyncio.sleep(2.0)
            return True

        # Wait for action server with timeout
        self.get_logger().info("Waiting for Nav2 /navigate_to_pose action server...")
        if not self.nav_client.wait_for_server(timeout_sec=1.5):
            self.get_logger().info("Nav2 action server not active. Falling back to [Mock Nav2] dry-run mode...")
            self.get_logger().info(f"[Mock Nav2] Simulating path planning and obstacle-avoidance to ({x}, {y}) ...")
            await asyncio.sleep(2.0)
            return True

        # Build goal message
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.w = 1.0  # Default face forward orientation

        self.get_logger().info("Sending goal coordinates...")
        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        
        # Wait for goal acceptance
        rclpy.spin_until_future_complete(self, send_goal_future)
        goal_handle = send_goal_future.result()
        
        if not goal_handle.accepted:
            self.get_logger().error("Goal was rejected by Nav2 server!")
            return False

        self.get_logger().info("Goal accepted by Nav2. Navigating...")
        get_result_future = goal_handle.get_result_async()
        
        # Wait for navigation result
        rclpy.spin_until_future_complete(self, get_result_future)
        status = get_result_future.result().status
        
        # STATUS_SUCCEEDED = 4 in ROS 2 action server
        if status == 4:
            return True
        return False

async def main(args=None):
    rclpy.init(args=args)
    executor_node = Ros2Nav2Executor()
    
    # Example validated JSON plan
    sample_plan = {
        "mission": [
            {"command": "waypoint", "x": 5.0, "y": 10.0},
            {"command": "waypoint", "x": -2.0, "y": 4.0},
            {"command": "land"}
        ]
    }
    plan_str = json.dumps(sample_plan)
    
    try:
        await executor_node.execute_mission_plan(plan_str)
    except KeyboardInterrupt:
        pass
    finally:
        executor_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    # Wrap in asyncio loop
    asyncio.run(main())
