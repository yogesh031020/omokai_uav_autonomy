#!/usr/bin/env python3
"""
ROS 2 Closed-Loop Vision AI Target Tracking Node.
Challenge 3: Vision AI target detection and proportional tracking.

Subscribes to:
    - /camera/image_raw (sensor_msgs/msg/Image)
Publishes:
    - /cmd_vel (geometry_msgs/msg/Twist)
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
import numpy as np

# In a real setup, we would import cv_bridge and ultralytics YOLO:
# from cv_bridge import CvBridge
# from ultralytics import YOLO

class VisionTargetTrackerNode(Node):
    def __init__(self):
        super().__init__('vision_target_tracker')
        
        # Subscriptions & Publishers
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        self.cmd_vel_pub = self.create_publisher(
            Twist,
            '/cmd_vel',
            10
        )
        
        # PID / Proportional Controller Gains
        self.kp_yaw = 0.005       # Control gain for yaw rate based on X error
        self.kp_vertical = 0.003  # Control gain for vertical velocity based on Y error
        self.kp_forward = 0.01    # Control gain for forward/backward speed based on size error
        
        # Target specs
        self.target_class = "person"
        self.desired_bbox_area = 20000.0  # Desired target bounding box area (in pixels) for distance control
        self.min_confidence = 0.5
        
        self.get_logger().info("Vision AI Target Tracker Node Initialized.")
        self.get_logger().info(f"Targeting class: '{self.target_class}' (Min confidence: {self.min_confidence})")

    def image_callback(self, msg: Image):
        # 1. Image Conversion: In a real simulation, we convert ROS Image to OpenCV:
        # cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        
        # 2. YOLOv8 Inference:
        # results = self.model(cv_image)
        # For demonstration and validation, we simulate a target detection event:
        simulated_detection = self.simulate_yolo_detection(msg.width, msg.height)
        
        if simulated_detection is not None:
            cx, cy, bbox_width, bbox_height = simulated_detection
            bbox_area = bbox_width * bbox_height
            
            # Calculate offset errors relative to the image frame center
            center_x = msg.width / 2.0
            center_y = msg.height / 2.0
            
            error_x = cx - center_x
            error_y = cy - center_y
            error_area = self.desired_bbox_area - bbox_area
            
            self.get_logger().info(
                f"[Target Locked] Centroid: ({cx:.1f}, {cy:.1f}) | Offset: (X={error_x:.1f}px, Y={error_y:.1f}px)"
            )
            
            # 3. Closed-Loop Proportional Controller (P-control)
            twist_cmd = Twist()
            
            # Yaw velocity (yaw rate): Rotate to center target horizontally
            twist_cmd.angular.z = -self.kp_yaw * error_x
            
            # Vertical velocity: Adjust altitude to center target vertically
            twist_cmd.linear.z = -self.kp_vertical * error_y
            
            # Forward velocity: Adjust distance (go closer/back away based on bounding box size)
            twist_cmd.linear.x = self.kp_forward * error_area
            
            # Apply velocity safety bounds
            twist_cmd.linear.x = np.clip(twist_cmd.linear.x, -2.0, 2.0)
            twist_cmd.linear.z = np.clip(twist_cmd.linear.z, -1.0, 1.0)
            twist_cmd.angular.z = np.clip(twist_cmd.angular.z, -0.5, 0.5)
            
            # Publish control inputs to drone autopilot
            self.cmd_vel_pub.publish(twist_cmd)
            
        else:
            # No target found: Stop command (or hold hover position)
            twist_cmd = Twist()
            self.cmd_vel_pub.publish(twist_cmd)
            
    def simulate_yolo_detection(self, img_w, img_h):
        """
        Helper method simulating a visual lock on a target person.
        Returns (cx, cy, width, height) of bounding box or None.
        """
        # For simulation demo, assume a target is located slightly off-center (offset X=20px, Y=-15px)
        # with a bounding box of 120x150 pixels.
        cx = (img_w / 2.0) + 20.0
        cy = (img_h / 2.0) - 15.0
        width = 120.0
        height = 150.0
        return (cx, cy, width, height)

def main(args=None):
    rclpy.init(args=args)
    node = VisionTargetTrackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
