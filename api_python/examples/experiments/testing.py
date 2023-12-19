#! /usr/bin/env python3

import sys
import os
import time
import threading
from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.messages import Base_pb2, BaseCyclic_pb2, Common_pb2

TIMEOUT_DURATION = 30

def check_for_end_or_abort(e):
    def check(notification, e=e):
        print("EVENT : " + Base_pb2.ActionEvent.Name(notification.action_event))
        if notification.action_event in (Base_pb2.ACTION_END, Base_pb2.ACTION_ABORT):
            e.set()
    return check

def move_to_waypoint(base, waypoint_info):
    waypoint = Base_pb2.CartesianWaypoint()
    waypoint.pose.x, waypoint.pose.y, waypoint.pose.z = waypoint_info[:3]
    waypoint.blending_radius = waypoint_info[3]
    waypoint.pose.theta_x, waypoint.pose.theta_y, waypoint.pose.theta_z = waypoint_info[4:]
    waypoint.reference_frame = Base_pb2.CARTESIAN_REFERENCE_FRAME_BASE
    return waypoint

def execute_waypoint_trajectory(base, waypoints):
    waypoints_list = Base_pb2.WaypointList()
    waypoints_list.duration = 0.0
    waypoints_list.use_optimal_blending = False
    for index, waypoint_info in enumerate(waypoints):
        waypoint = waypoints_list.waypoints.add()
        waypoint.name = "waypoint_" + str(index)
        waypoint.cartesian_waypoint.CopyFrom(move_to_waypoint(base, waypoint_info))

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(check_for_end_or_abort(e), Base_pb2.NotificationOptions())
    base.ExecuteWaypointTrajectory(waypoints_list)
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)
    return finished

def rotate_joint(base, joint_id):
    action = Base_pb2.Action()
    action.name = "Rotate Joint by 90 Degrees"
    joint_angle = action.reach_joint_angles.joint_angles.joint_angles.add()
    joint_angle.joint_identifier = joint_id
    joint_angle.value = 90  # Rotate by 90 degrees

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(check_for_end_or_abort(e), Base_pb2.NotificationOptions())
    base.ExecuteAction(action)
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)
    return finished


def example_angular_action_movement(base):
    
    print("Starting angular action movement ...")
    action = Base_pb2.Action()
    action.name = "Example angular action movement"
    action.application_data = ""

    actuator_count = base.GetActuatorCount()

    # Place arm straight up
    joint_angles = [357, 37, 172, 238, 350, 70, 0]
    for joint_id in range(actuator_count.count):
        joint_angle = action.reach_joint_angles.joint_angles.joint_angles.add()
        joint_angle.joint_identifier = joint_id
        joint_angle.value = joint_angles[joint_id]

    e = threading.Event()
    notification_handle = base.OnNotificationActionTopic(
        check_for_end_or_abort(e),
        Base_pb2.NotificationOptions()
    )
    
    print("Executing action")
    base.ExecuteAction(action)

    print("Waiting for movement to finish ...")
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(notification_handle)

    if finished:
        print("Angular movement completed")
    else:
        print("Timeout on action notification wait")
    return finished

def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import utilities
    args = utilities.parseConnectionArguments()
    with utilities.DeviceConnection.createTcpConnection(args) as router:
        base = BaseClient(router)
        base_cyclic = BaseCyclicClient(router)

        success = True
        kTheta_x = 90.0
        kTheta_y = 0.0
        kTheta_z = 90.0
        waypoints = ( (0.7,   0.0,  0.5,  0.0, kTheta_x, kTheta_y, kTheta_z),
                    (0.7,   0.0,  0.33, 0.1, kTheta_x, kTheta_y, kTheta_z),
                    (0.7,   0.48, 0.33, 0.1, kTheta_x, kTheta_y, kTheta_z),
                    (0.61,  0.22, 0.4,  0.1, kTheta_x, kTheta_y, kTheta_z),
                    (0.7,   0.48, 0.33, 0.1, kTheta_x, kTheta_y, kTheta_z),
                    (0.63, -0.22, 0.45, 0.1, kTheta_x, kTheta_y, kTheta_z),
                    (0.65,  0.05, 0.33, 0.0, kTheta_x, kTheta_y, kTheta_z))
        success &= execute_waypoint_trajectory(base, waypoints)

        print('rotating joint')
        success &= example_angular_action_movement(base)  # Specify the joint ID to rotate

        return 0 if success else 1

if __name__ == "__main__":
    exit(main())