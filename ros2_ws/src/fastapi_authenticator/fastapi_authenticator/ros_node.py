# ros_node.py
import threading
import rclpy
from rclpy.node import Node
from interfaces.srv import CreateSession  # replace with your service type
from rclpy.executors import SingleThreadedExecutor
import yaml

SERVICE_NAME = "some_topic"

class RosServiceNode(Node):
    def __init__(self):
        super().__init__('fastapi_ros_node')
        self.cli = self.create_client(CreateSession, SERVICE_NAME)

        while not self.cli.wait_for_service(timeout_sec=5.0):
            self.get_logger().info('Waiting for service to become available...')

    def make_session_creation_request(self) -> CreateSession.Response: 
        """
        Create a session by making an asynchronous ROS2 service call.
        This method sends a CreateSession request to the ROS2 service and waits
        for the response to complete before returning.
        Returns:
            CreateSession.Response: The response object from the CreateSession service,
                                   containing the session creation result.
        """
        request = CreateSession.Request()
        future = self.cli.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        result = future.result()
        
        if result is None:
            return CreateSession.Response(success=False)

        return result


ros_node: RosServiceNode | None = None

def get_node() -> RosServiceNode:
    global ros_node
    if ros_node is None:
        ros_node = RosServiceNode()
    return ros_node

def spin():
    rclpy.init()  # only once in your process
    global ros_node
    ros_node = get_node()
    executor = SingleThreadedExecutor()
    executor.add_node(ros_node)
    rclpy.shutdown()

def spin_threaded():
    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    return thread
